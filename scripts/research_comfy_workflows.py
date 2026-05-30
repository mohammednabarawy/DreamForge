"""Download and analyze public ComfyUI workflows for DreamForge research.

This script is intentionally read/analyze only:
- downloads artifacts into .research/ (gitignored)
- extracts Comfy workflow/prompt metadata from JSON/PNG/WebP where possible
- classifies node patterns
- never executes downloaded workflows or installs custom nodes
"""

from __future__ import annotations

import argparse
import hashlib
import html.parser
import json
import os
import re
import struct
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESEARCH_ROOT = PROJECT_ROOT / ".research" / "comfy_workflow_research"
ALLOWED_RESEARCH_ROOT = (PROJECT_ROOT / ".research").resolve()
USER_AGENT = "DreamForge-ComfyWorkflowResearch/0.1"

SEED_PAGES = [
    "https://comfyanonymous.github.io/ComfyUI_examples/",
    "https://comfyanonymous.github.io/ComfyUI_examples/img2img/",
    "https://comfyanonymous.github.io/ComfyUI_examples/inpaint/",
    "https://comfyanonymous.github.io/ComfyUI_examples/upscale_models/",
    "https://comfyanonymous.github.io/ComfyUI_examples/controlnet/",
    "https://comfyanonymous.github.io/ComfyUI_examples/flux/",
    "https://docs.comfy.org/development/core-concepts/workflow",
    "https://www.comfyvault.app/",
    "https://comfyui-wiki.com/en/workflows",
]

GITHUB_REPOS = [
    ("Comfy-Org", "workflow_templates"),
    ("comfyanonymous", "ComfyUI_examples"),
    ("aimpowerment", "comfyui-workflows"),
    ("ltdrdata", "ComfyUI-Inspire-Pack"),
    ("cubiq", "ComfyUI_essentials"),
]

SOURCE_CATALOG: list[tuple[str, str, str]] = [
    ("comfyanonymous.github.io", "official_examples", "Upstream ComfyUI examples; verify license on the ComfyUI repository."),
    ("docs.comfy.org", "official_docs", "ComfyUI documentation; pattern evidence only."),
    ("github.com/Comfy-Org", "github_repo", "Check the repository LICENSE before copying patterns."),
    ("github.com/comfyanonymous", "github_repo", "Check the ComfyUI repository LICENSE before copying patterns."),
    ("github.com/", "github_repo", "Third-party GitHub artifact; review repository LICENSE and attribution."),
    ("huggingface.co", "huggingface_repo", "Review Hugging Face model/card license before reuse."),
    ("comfyvault.app", "public_gallery", "Public gallery artifact; verify uploader terms and workflow license."),
    ("comfyui-wiki.com", "tutorial_evidence", "Tutorial/gallery evidence only; do not copy prose or assets verbatim."),
]

ARTIFACT_EXTENSIONS = {".json", ".png", ".webp"}

TASK_RULES = {
    "txt2img": {
        "EmptyLatentImage",
        "EmptySD3LatentImage",
        "KSampler",
        "SamplerCustom",
        "SamplerCustomAdvanced",
    },
    "img2img": {"LoadImage", "VAEEncode", "KSampler"},
    "inpaint": {
        "LoadImageMask",
        "VAEEncodeForInpaint",
        "SetLatentNoiseMask",
        "InpaintModelConditioning",
        "GrowMask",
        "MaskComposite",
    },
    "upscale": {
        "LoadUpscaleModel",
        "UpscaleModelLoader",
        "ImageUpscaleWithModel",
        "ImageScale",
        "ImageScaleBy",
        "LatentUpscale",
        "UltimateSDUpscale",
    },
    "controlnet": {"ControlNetLoader", "ApplyControlNet", "ControlNetApply", "ControlNetApplyAdvanced"},
    "reference_ipadapter": {"IPAdapter", "IPAdapterApply", "ApplyIPAdapter", "CLIPVisionLoader", "LoadImage"},
    "face_detail": {"FaceDetailer", "DetailerForEach", "UltralyticsDetectorProvider", "SAMLoader", "ImpactDetector"},
    "flux": {"FluxGuidance", "DualCLIPLoader", "UNETLoader", "UnetLoaderGGUF", "EmptySD3LatentImage"},
    "sdxl": {"CheckpointLoaderSimple", "CLIPTextEncodeSDXL", "SDXLPromptStyler"},
    "compositing": {
        "ImageComposite",
        "ImageCompositeMasked",
        "ImageBlend",
        "ImageCrop",
        "ImagePadForOutpaint",
        "MaskToImage",
        "SolidMask",
        "InvertMask",
    },
    "video": {"VHS_LoadVideo", "VHS_VideoCombine", "AnimateDiffLoader", "ADE_AnimateDiffLoader"},
}

COMMON_NEEDS = {
    "txt2img": "Text-to-image creation from prompt, model, size, sampler, and seed.",
    "img2img": "Restyle or transform an existing image with denoise control.",
    "inpaint": "Remove/replace objects, fix regions, expand canvas, or preserve unmasked pixels.",
    "upscale": "Increase resolution, sharpen details, or run a second pass/tiled upscale.",
    "controlnet": "Preserve pose, depth, edges, line art, layout, or structure.",
    "reference_ipadapter": "Use reference images for style, identity, composition, or product consistency.",
    "face_detail": "Repair faces/hands/subject details after a base generation or edit.",
    "flux": "Modern Flux text-to-image/editing with split UNET/CLIP/VAE loaders and guidance.",
    "sdxl": "General checkpoint-based generation and editing with broad community model support.",
    "compositing": "Layer/mask blending, deterministic text integration, product/poster assembly.",
    "video": "Animate or combine frames; keep separate from image-first v1 unless explicitly enabled.",
}


class LinkParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for key, value in attrs:
            if key.lower() in {"href", "src"} and value:
                self.links.append(value)


@dataclass
class Artifact:
    url: str
    path: str
    kind: str
    source: str
    source_class: str = ""
    license_note: str = ""
    workflow_count: int = 0
    tasks: list[str] = field(default_factory=list)
    top_nodes: list[tuple[str, int]] = field(default_factory=list)
    custom_nodes: list[str] = field(default_factory=list)
    error: str = ""


def source_metadata(url: str, source: str) -> tuple[str, str]:
    haystack = f"{url} {source}".lower()
    for needle, source_class, license_note in SOURCE_CATALOG:
        if needle in haystack:
            return source_class, license_note
    if source == "public-web":
        return "public_web", "Unknown public source; verify license before reuse."
    return "unknown", "Review source license before copying any workflow pattern."


def fetch_bytes(url: str, timeout: float = 30.0) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def safe_filename(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    name = Path(parsed.path).name or "index.html"
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return f"{digest}_{stem}"


def discover_links_from_page(url: str) -> list[str]:
    try:
        text = fetch_bytes(url).decode("utf-8", errors="replace")
    except Exception:
        return []
    parser = LinkParser()
    parser.feed(text)
    out: list[str] = []
    for link in parser.links:
        absolute = urllib.parse.urljoin(url, link)
        parsed = urllib.parse.urlparse(absolute)
        suffix = Path(parsed.path).suffix.lower()
        if suffix in ARTIFACT_EXTENSIONS:
            out.append(absolute)
    return sorted(set(out))


def github_contents(owner: str, repo: str, path: str = "") -> list[dict[str, Any]]:
    api = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}".rstrip("/")
    try:
        data = json.loads(fetch_bytes(api).decode("utf-8"))
    except Exception:
        return []
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    return []


def discover_github_artifacts(max_items: int) -> list[str]:
    found: list[str] = []
    queue = [(owner, repo, "") for owner, repo in GITHUB_REPOS]
    while queue and len(found) < max_items:
        owner, repo, path = queue.pop(0)
        for item in github_contents(owner, repo, path):
            item_type = item.get("type")
            item_path = str(item.get("path") or "")
            if item_type == "dir":
                queue.append((owner, repo, item_path))
                continue
            suffix = Path(item_path).suffix.lower()
            if item_type == "file" and suffix in ARTIFACT_EXTENSIONS:
                download_url = item.get("download_url")
                if download_url:
                    found.append(str(download_url))
                    if len(found) >= max_items:
                        break
    return found


def png_text_chunks(data: bytes) -> dict[str, str]:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return {}
    pos = 8
    chunks: dict[str, str] = {}
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        chunk_type = data[pos + 4 : pos + 8]
        chunk_data = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if chunk_type == b"tEXt" and b"\x00" in chunk_data:
            key, value = chunk_data.split(b"\x00", 1)
            chunks[key.decode("latin-1", errors="replace")] = value.decode("utf-8", errors="replace")
        elif chunk_type == b"iTXt":
            parts = chunk_data.split(b"\x00", 5)
            if len(parts) == 6:
                key = parts[0].decode("latin-1", errors="replace")
                value = parts[5].decode("utf-8", errors="replace")
                chunks[key] = value
    return chunks


def parse_workflow_payload(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    payloads: list[dict[str, Any]] = []
    if suffix == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if isinstance(data, dict):
            payloads.append(data)
            if isinstance(data.get("prompt"), dict):
                payloads.append(data["prompt"])
            if isinstance(data.get("workflow"), dict):
                payloads.append(data["workflow"])
        return payloads
    if suffix == ".png":
        chunks = png_text_chunks(path.read_bytes())
        for key in ("workflow", "prompt", "extra_pnginfo"):
            raw = chunks.get(key)
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except Exception:
                continue
            if isinstance(data, dict):
                payloads.append(data)
                if isinstance(data.get("workflow"), dict):
                    payloads.append(data["workflow"])
                if isinstance(data.get("prompt"), dict):
                    payloads.append(data["prompt"])
    return payloads


def node_types_from_payload(data: dict[str, Any]) -> list[str]:
    types: list[str] = []
    if isinstance(data.get("nodes"), list):
        for node in data["nodes"]:
            if isinstance(node, dict):
                node_type = node.get("type") or node.get("class_type")
                if node_type:
                    types.append(str(node_type))
    if data and all(isinstance(v, dict) for v in data.values()):
        for node in data.values():
            node_type = node.get("class_type") or node.get("type")
            if node_type:
                types.append(str(node_type))
    return types


def classify_node_types(node_types: list[str]) -> list[str]:
    node_set = set(node_types)
    tasks: list[str] = []
    for task, required in TASK_RULES.items():
        overlap = node_set.intersection(required)
        if task == "txt2img":
            if ("KSampler" in node_set or "SamplerCustomAdvanced" in node_set) and (
                "EmptyLatentImage" in node_set or "EmptySD3LatentImage" in node_set
            ):
                tasks.append(task)
        elif task == "img2img":
            if {"LoadImage", "VAEEncode"}.issubset(node_set):
                tasks.append(task)
        elif overlap:
            tasks.append(task)
    return tasks or ["unknown"]


def likely_custom_nodes(node_types: list[str]) -> list[str]:
    core_prefixes = (
        "KSampler",
        "CheckpointLoader",
        "CLIP",
        "VAE",
        "LoadImage",
        "SaveImage",
        "Empty",
        "Image",
        "Latent",
        "ControlNet",
        "UNET",
        "DualCLIP",
        "Flux",
        "Primitive",
        "Reroute",
        "Note",
    )
    out = []
    for node in sorted(set(node_types)):
        if not node.startswith(core_prefixes):
            out.append(node)
    return out[:40]


def analyze_artifact(path: Path, url: str, source: str) -> Artifact:
    source_class, license_note = source_metadata(url, source)
    artifact = Artifact(
        url=url,
        path=str(path),
        kind=path.suffix.lower().lstrip("."),
        source=source,
        source_class=source_class,
        license_note=license_note,
    )
    try:
        payloads = parse_workflow_payload(path)
        all_nodes: list[str] = []
        for payload in payloads:
            all_nodes.extend(node_types_from_payload(payload))
        counts = Counter(all_nodes)
        artifact.workflow_count = len(payloads)
        artifact.top_nodes = counts.most_common(20)
        artifact.tasks = classify_node_types(all_nodes) if all_nodes else ["no_workflow_metadata"]
        artifact.custom_nodes = likely_custom_nodes(all_nodes)
    except Exception as exc:
        artifact.error = str(exc)
    return artifact


def download_artifacts(urls: list[str], out_dir: Path, max_downloads: int) -> list[tuple[Path, str]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[tuple[Path, str]] = []
    for url in urls[:max_downloads]:
        target = out_dir / safe_filename(url)
        if target.exists():
            paths.append((target, url))
            continue
        try:
            target.write_bytes(fetch_bytes(url))
            paths.append((target, url))
        except urllib.error.HTTPError as exc:
            print(f"[skip] {url}: HTTP {exc.code}", file=sys.stderr)
        except Exception as exc:
            print(f"[skip] {url}: {exc}", file=sys.stderr)
    return paths


def write_report(artifacts: list[Artifact], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    index = [artifact.__dict__ for artifact in artifacts]
    (out_dir / "workflow_index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")

    task_counts = Counter(task for artifact in artifacts for task in artifact.tasks)
    node_counts: Counter[str] = Counter()
    custom_counts: Counter[str] = Counter()
    by_task: dict[str, list[Artifact]] = defaultdict(list)
    for artifact in artifacts:
        for node, count in artifact.top_nodes:
            node_counts[node] += count
        for node in artifact.custom_nodes:
            custom_counts[node] += 1
        for task in artifact.tasks:
            by_task[task].append(artifact)

    lines = [
        "# ComfyUI Workflow Research Analysis",
        "",
        "Downloaded artifacts are stored beside this report and are for research only. Do not execute them blindly.",
        "",
        "## Summary",
        "",
        f"- Artifacts analyzed: {len(artifacts)}",
        f"- Artifacts with workflow metadata: {sum(1 for a in artifacts if a.workflow_count > 0)}",
        "",
        "## Source classes",
        "",
    ]
    class_counts = Counter(a.source_class or "unknown" for a in artifacts)
    for source_class, count in class_counts.most_common():
        lines.append(f"- `{source_class}`: {count} artifact(s)")
    lines += [
        "",
        "## License reminder",
        "",
        "- Patterns may be copied into DreamForge builders only after source/license review.",
        "",
        "## Common User Needs",
        "",
    ]
    for task, count in task_counts.most_common():
        lines.append(f"- `{task}` ({count}): {COMMON_NEEDS.get(task, 'Unclassified workflow pattern.')}")
    lines += ["", "## Common Node Building Blocks", ""]
    for node, count in node_counts.most_common(30):
        lines.append(f"- `{node}`: {count}")
    lines += ["", "## Custom Node Caution List", ""]
    if custom_counts:
        for node, count in custom_counts.most_common(40):
            lines.append(f"- `{node}`: seen in {count} artifact(s)")
    else:
        lines.append("- No likely custom nodes detected in parsed artifacts.")
    lines += ["", "## Recommended DreamForge Template Categories", ""]
    for task in [
        "txt2img",
        "img2img",
        "inpaint",
        "upscale",
        "controlnet",
        "reference_ipadapter",
        "face_detail",
        "flux",
        "sdxl",
        "compositing",
    ]:
        examples = by_task.get(task, [])
        lines.append(f"- `{task}`: encode as first-party builder/template; examples found: {len(examples)}")
    lines += ["", "## Source Artifacts", ""]
    for artifact in artifacts:
        task_text = ", ".join(artifact.tasks)
        lines.append(
            f"- `{task_text}` - [{Path(artifact.path).name}]({artifact.url}) "
            f"({artifact.source_class}: {artifact.license_note})"
        )
    (out_dir / "ANALYSIS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def validate_research_output_dir(out_dir: Path, *, force: bool = False) -> Path:
    """Keep research artifacts under gitignored .research/ unless explicitly overridden."""
    resolved = out_dir.resolve()
    if force:
        return resolved
    try:
        resolved.relative_to(ALLOWED_RESEARCH_ROOT)
    except ValueError as exc:
        raise SystemExit(
            f"Refusing to write research output outside {ALLOWED_RESEARCH_ROOT}. "
            "Pass --force-out to override."
        ) from exc
    return resolved


def collect_urls(max_downloads: int) -> list[str]:
    urls: list[str] = []
    for page in SEED_PAGES:
        urls.extend(discover_links_from_page(page))
    urls.extend(discover_github_artifacts(max_items=max_downloads))
    seen = set()
    deduped = []
    for url in urls:
        suffix = Path(urllib.parse.urlparse(url).path).suffix.lower()
        if suffix not in ARTIFACT_EXTENSIONS:
            continue
        if url not in seen:
            seen.add(url)
            deduped.append(url)
    return deduped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Research public ComfyUI workflow artifacts.")
    parser.add_argument("--out", default=str(RESEARCH_ROOT), help="Research output directory")
    parser.add_argument("--max-downloads", type=int, default=80, help="Maximum artifacts to download")
    parser.add_argument("--no-network", action="store_true", help="Analyze existing downloaded artifacts only")
    parser.add_argument(
        "--force-out",
        action="store_true",
        help="Allow writing reports outside .research/ (not recommended)",
    )
    args = parser.parse_args(argv)

    out_dir = validate_research_output_dir(Path(args.out), force=bool(args.force_out))
    artifacts_dir = out_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    url_by_path: dict[Path, str] = {}
    if not args.no_network:
        urls = collect_urls(max_downloads=max(10, args.max_downloads))
        downloaded = download_artifacts(urls, artifacts_dir, args.max_downloads)
        for path, url in downloaded:
            paths.append(path)
            url_by_path[path] = url
    paths.extend(sorted(artifacts_dir.glob("*")))

    artifacts: list[Artifact] = []
    seen_paths = set()
    for path in paths:
        if path in seen_paths or not path.is_file():
            continue
        seen_paths.add(path)
        artifacts.append(analyze_artifact(path, url_by_path.get(path, path.as_uri()), "public-web"))

    write_report(artifacts, out_dir)
    print(json.dumps({"status": "success", "artifacts": len(artifacts), "out": str(out_dir)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
