"""Modern identity preservation: Kontext/Qwen primary, optional IP-Adapter FaceID."""

from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any

VALID_IDENTITY_MODES = frozenset(
    {"preserve_face", "kontext", "qwen_edit", "ipadapter_faceid", "auto"}
)
LEGACY_IDENTITY_ALIASES = frozenset({"face", "faceid", "face_id", "preserve_face"})

KONTEXT_IDENTITY_STRENGTH = 0.92
QWEN_IDENTITY_STRENGTH = 1.0
FACEID_DEFAULT_WEIGHT = 0.75
IDENTITY_SIMILARITY_THRESHOLD = 0.35


def analyze_reference_faces(path: str) -> dict[str, Any]:
    """Detect selectable faces locally; no pixels or embeddings are retained."""
    try:
        import cv2

        from dreamforge_paths import resolve_image_path_or_raise

        resolved = resolve_image_path_or_raise(path)
        image = cv2.imread(str(resolved))
        if image is None:
            raise ValueError("image could not be decoded")
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        cascade = cv2.CascadeClassifier(
            str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml")
        )
        detected = cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(40, 40),
        )
        boxes = sorted(
            ((int(x), int(y), int(w), int(h)) for x, y, w, h in detected),
            key=lambda item: item[0],
        )
        largest = max(range(len(boxes)), key=lambda i: boxes[i][2] * boxes[i][3]) if boxes else None
        return {
            "ok": True,
            "count": len(boxes),
            "detector": "opencv",
            "faces": [
                {
                    "index": index,
                    "x": x,
                    "y": y,
                    "width": width,
                    "height": height,
                    "recommended": index == largest,
                }
                for index, (x, y, width, height) in enumerate(boxes)
            ],
        }
    except Exception as exc:
        return {"ok": False, "count": 0, "faces": [], "error": str(exc)}


def _selected_face_index(job) -> int | None:
    explicit = getattr(job, "identity_face_index", None)
    references = getattr(job, "references", None)
    if explicit is None and isinstance(references, list):
        for slot in references:
            if isinstance(slot, dict) and slot.get("face_index") is not None:
                explicit = slot.get("face_index")
                break
    try:
        index = int(explicit)
    except (TypeError, ValueError):
        return None
    return index if index >= 0 else None


def identity_reference_image_bytes(path: str, face_index: int | None = None) -> bytes:
    """Crop the chosen face for FaceID; return original bytes if detection fails."""
    from PIL import Image
    from dreamforge_paths import resolve_image_path_or_raise

    resolved = resolve_image_path_or_raise(path)
    analysis = analyze_reference_faces(str(resolved))
    faces = analysis.get("faces") or []
    if not faces:
        return Path(resolved).read_bytes()
    selected = next(
        (face for face in faces if face.get("index") == face_index),
        next((face for face in faces if face.get("recommended")), faces[0]),
    )
    with Image.open(resolved) as source:
        image = source.convert("RGB")
        x = int(selected["x"])
        y = int(selected["y"])
        width = int(selected["width"])
        height = int(selected["height"])
        side = int(max(width, height) * 2.1)
        cx = x + width // 2
        cy = y + height // 2
        left = max(0, cx - side // 2)
        top = max(0, cy - side // 2)
        right = min(image.width, left + side)
        bottom = min(image.height, top + side)
        crop = image.crop((left, top, right, bottom))
        buffer = BytesIO()
        crop.save(buffer, format="PNG")
        return buffer.getvalue()


@lru_cache(maxsize=1)
def _face_analyzer():
    """Load the existing InsightFace install only when verification is requested."""
    import onnxruntime
    from insightface.app import FaceAnalysis
    from _paths import MODELS_ROOT

    pack = _insightface_pack_present()
    if not pack:
        raise RuntimeError("InsightFace model pack is not installed")
    available = set(onnxruntime.get_available_providers())
    providers = (
        ["CUDAExecutionProvider", "CPUExecutionProvider"]
        if "CUDAExecutionProvider" in available
        else ["CPUExecutionProvider"]
    )
    analyzer = FaceAnalysis(
        name=pack,
        root=str(MODELS_ROOT / "insightface"),
        providers=providers,
    )
    analyzer.prepare(ctx_id=0 if "CUDAExecutionProvider" in available else -1, det_size=(640, 640))
    return analyzer


def _face_embeddings(path: str) -> list[Any]:
    import cv2
    import numpy as np

    from dreamforge_paths import resolve_image_path_or_raise

    image = cv2.imread(str(resolve_image_path_or_raise(path)))
    if image is None:
        return []
    faces = sorted(_face_analyzer().get(image), key=lambda face: float(face.bbox[0]))
    embeddings: list[Any] = []
    for face in faces:
        embedding = np.asarray(face.embedding, dtype=np.float32)
        norm = float(np.linalg.norm(embedding))
        if norm > 0:
            x0, y0, x1, y1 = (float(value) for value in face.bbox)
            embeddings.append(
                {
                    "embedding": embedding / norm,
                    "area": max(0.0, x1 - x0) * max(0.0, y1 - y0),
                }
            )
    return embeddings


def verify_identity_outputs(job, images: list[str]) -> dict[str, Any]:
    """Compare the selected reference face with outputs using local embeddings."""
    if not bool(getattr(job, "identity_verify", False)):
        return {"status": "disabled"}
    reference = str(
        getattr(job, "_identity_reference_path", None) or _reference_path(job)
    ).strip()
    if not reference or not images:
        return {"status": "unavailable", "reason": "reference or output image missing"}
    try:
        import numpy as np

        reference_faces = _face_embeddings(reference)
        # Check for multi-reference blending
        refs_list = getattr(job, "references", None) or []
        if len(refs_list) > 1:
            multi_embeddings = []
            for ref_item in refs_list:
                ref_path = ref_item.get("path") if isinstance(ref_item, dict) else str(ref_item)
                if ref_path:
                    faces = _face_embeddings(ref_path)
                    if faces:
                        idx = ref_item.get("face_index") if isinstance(ref_item, dict) else None
                        face_obj = faces[min(idx, len(faces) - 1)] if idx is not None else max(faces, key=lambda i: i["area"])
                        multi_embeddings.append(face_obj["embedding"])
            if multi_embeddings:
                avg_emb = np.mean(multi_embeddings, axis=0)
                norm = float(np.linalg.norm(avg_emb))
                if norm > 0:
                    reference_embedding = avg_emb / norm
                else:
                    reference_embedding = reference_faces[0]["embedding"] if reference_faces else np.zeros(512)
            else:
                reference_face = max(reference_faces, key=lambda item: item["area"]) if reference_faces else None
                reference_embedding = reference_face["embedding"] if reference_face else None
        else:
            if not reference_faces:
                return {"status": "unavailable", "reason": "no face found in the reference image"}
            selected_index = _selected_face_index(job)
            if selected_index is None:
                reference_face = max(reference_faces, key=lambda item: item["area"])
            else:
                reference_face = reference_faces[min(selected_index, len(reference_faces) - 1)]
            reference_embedding = reference_face["embedding"]

        best_score = -1.0
        best_output = None
        for output in images:
            for face in _face_embeddings(output):
                score = float(np.dot(reference_embedding, face["embedding"]))
                if score > best_score:
                    best_score = score
                    best_output = output
        threshold = max(
            0.1,
            min(
                0.9,
                float(
                    getattr(job, "identity_similarity_threshold", None)
                    or IDENTITY_SIMILARITY_THRESHOLD
                ),
            ),
        )
        if best_output is None:
            return {
                "status": "failed",
                "score": None,
                "threshold": threshold,
                "reason": "no face found in generated output",
                "suggestion": "No face was detected in output. Try adding 'close-up portrait of face' to prompt.",
            }
        passed = best_score >= threshold
        rounded_score = round(best_score, 4)
        return {
            "status": "passed" if passed else "failed",
            "score": rounded_score,
            "threshold": threshold,
            "output": best_output,
            "reference": reference,
            "reason": "likeness threshold met" if passed else f"likeness score ({rounded_score}) below threshold ({threshold})",
            "suggestion": "Likeness score met" if passed else f"Likeness score ({rounded_score}) fell below threshold ({threshold}). Try increasing FaceID weight or using a clearer frontal reference photo.",
        }
    except (ImportError, RuntimeError) as exc:
        return {
            "status": "unavailable",
            "reason": f"local InsightFace verification unavailable: {exc}",
        }
    except Exception as exc:
        return {"status": "unavailable", "reason": f"face verification failed: {exc}"}


def _inventory_model(category: str, hints: tuple[str, ...] = ()) -> str | None:
    try:
        from dreamforge_cli_inventory import list_model_inventory

        items = list_model_inventory().get("categories", {}).get(category, [])
        if hints:
            for item in items:
                text = " ".join(
                    str(item.get(key, "")) for key in ("name", "relative_path", "stem")
                ).lower()
                if any(h in text for h in hints):
                    return str(item.get("name") or item.get("relative_path") or "").replace(
                        "\\", "/"
                    )
        if items:
            item = items[0]
            return str(item.get("name") or item.get("relative_path") or "").replace("\\", "/")
    except Exception:
        return None
    return None


def _pick_faceid_model() -> str | None:
    try:
        from dreamforge_cli_inventory import list_model_inventory

        items = list_model_inventory().get("categories", {}).get("ipadapter", [])
        fallback = None
        for item in items:
            text = " ".join(
                str(item.get(key, "")) for key in ("name", "relative_path", "stem")
            ).lower()
            if "faceid" not in text and "face-id" not in text and "face_id" not in text:
                continue
            name = str(item.get("name") or item.get("relative_path") or "").replace("\\", "/")
            fallback = fallback or name
            if "sdxl" in text:
                return name
        return fallback
    except Exception:
        return None


def normalize_identity_mode(value: Any) -> str | None:
    key = str(value or "").strip().lower()
    if key in VALID_IDENTITY_MODES:
        return key
    if key in LEGACY_IDENTITY_ALIASES:
        return "preserve_face"
    return None


def is_identity_preservation_job(job) -> bool:
    return bool(
        getattr(job, "preserve_character", False)
        or getattr(job, "face_preservation", False)
        or normalize_identity_mode(getattr(job, "identity_mode", None))
        or identity_intent_from_prompt(getattr(job, "prompt", None))
    )


def identity_intent_from_prompt(prompt: Any) -> bool:
    text = str(prompt or "").lower()
    if not text.strip():
        return False
    identity_terms = (
        "same person",
        "same face",
        "reference face",
        "use the face",
        "use reference face",
        "maintain facial",
        "facial consistency",
        "face consistency",
        "preserve face",
        "preserve facial",
        "preserve identity",
        "maintain identity",
        "likeness",
    )
    return any(term in text for term in identity_terms)


def _insightface_pack_present() -> str | None:
    """Return buffalo_l / antelopev2 pack name when InsightFace ONNX weights exist."""
    from _paths import MODELS_ROOT

    root = MODELS_ROOT / "insightface"
    for pack in ("buffalo_l", "antelopev2"):
        folder = root / "models" / pack
        if folder.is_dir() and any(folder.glob("*.onnx")):
            return pack
    return None


def faceid_assets_available() -> dict[str, Any]:
    """Return whether real FaceID weights + insightface stack are on disk."""
    from dreamforge_workflow_planner import custom_node_pack_present

    missing: list[str] = []
    if not custom_node_pack_present("ComfyUI_IPAdapter_plus"):
        missing.append("ComfyUI_IPAdapter_plus")
    faceid_model = _pick_faceid_model()
    if not faceid_model:
        missing.append("ipadapter_faceid_model")
    insightface_pack = _insightface_pack_present()
    if not insightface_pack:
        missing.append("insightface_model")
    return {
        "ok": not missing,
        "ipadapter_faceid_model": faceid_model,
        "insightface_model": insightface_pack,
        "missing": missing,
    }


def _reference_path(job) -> str:
    return str(
        getattr(job, "input_image", None)
        or getattr(job, "reference_image", None)
        or ""
    ).strip()


def _pick_kontext_checkpoint() -> str | None:
    needles = (
        "flux1-dev-kontext_fp8_scaled",
        "flux1-dev-kontext",
        "kontext",
        "flux kontext",
    )
    try:
        from dreamforge_cli_inventory import list_model_inventory

        for item in list_model_inventory().get("categories", {}).get("diffusion_models", []):
            hay = " ".join(
                str(item.get(key, "")) for key in ("name", "relative_path", "stem", "family")
            ).lower()
            if any(n in hay for n in needles) and "fill" not in hay:
                return str(item.get("name") or item.get("relative_path") or "").replace("\\", "/")
    except Exception:
        return None
    return None


def _pick_qwen_edit_checkpoint() -> str | None:
    try:
        from dreamforge_cli_inventory import list_model_inventory, pick_best_qwen_edit_model

        gallery = list_model_inventory().get("gallery", [])
        if isinstance(gallery, list) and gallery:
            picked = pick_best_qwen_edit_model(gallery)
            return picked or None
        for item in list_model_inventory().get("categories", {}).get("diffusion_models", []):
            hay = " ".join(
                str(item.get(key, "")) for key in ("name", "relative_path", "stem", "family")
            ).lower()
            if "qwen" in hay and "edit" in hay:
                return str(item.get("name") or item.get("relative_path") or "").replace("\\", "/")
    except Exception:
        return None
    return None


def _pick_faceid_checkpoint() -> str | None:
    """Pick an installed SDXL checkpoint compatible with the bundled FaceID model.

    The model inventory items have keys: name, stem, relative_path, path, size_mb.
    There is no ``family`` or ``category`` metadata, so we match by filename
    heuristics.  SDXL checkpoints are typically ≥3 GB; we also look for 'sdxl'
    in the name.  Refiners and inpainting-specific variants are excluded.
    """
    SDXL_HINTS = ("sdxl", "sd_xl", "sd-xl")
    EXCLUDE = ("refiner", "inpaint")
    # Minimum plausible size for a full SDXL checkpoint (~3.5 GB fp16).
    MIN_SIZE_MB = 2500

    try:
        from dreamforge_cli_inventory import list_model_inventory

        inventory = list_model_inventory()
        items = list(inventory.get("categories", {}).get("checkpoints", []) or [])
        if not items:
            return None

        # First pass: prefer an explicitly-named SDXL checkpoint.
        for item in items:
            text = " ".join(
                str(item.get(key, ""))
                for key in ("name", "relative_path", "stem")
            ).lower()
            if any(h in text for h in EXCLUDE):
                continue
            # Check for explicit family metadata (future-proof) or name hint.
            family = str(item.get("family") or "").strip().lower()
            if family == "sdxl" or any(h in text for h in SDXL_HINTS):
                return str(
                    item.get("engine_name")
                    or item.get("name")
                    or item.get("relative_path")
                    or ""
                ).replace("\\", "/")

        # Second pass: fall back to any large-enough checkpoint (likely SDXL).
        for item in items:
            text = " ".join(
                str(item.get(key, ""))
                for key in ("name", "relative_path", "stem")
            ).lower()
            if any(h in text for h in EXCLUDE):
                continue
            size = float(item.get("size_mb") or 0)
            if size >= MIN_SIZE_MB:
                return str(
                    item.get("engine_name")
                    or item.get("name")
                    or item.get("relative_path")
                    or ""
                ).replace("\\", "/")
    except Exception:
        return None
    return None


def build_identity_retry_params(
    job,
    data: dict[str, Any] | None,
    verification: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Build one FaceID retry when the first native edit misses the likeness target."""
    if verification.get("status") != "failed":
        return None, {"eligible": False, "reason": "verification did not fail"}
    if not bool(getattr(job, "identity_retry", False)):
        return None, {"eligible": False, "reason": "automatic retry disabled"}
    if bool(getattr(job, "identity_retry_attempted", False)):
        return None, {"eligible": False, "reason": "retry already attempted"}
    if normalize_identity_mode(getattr(job, "identity_mode", None)) == "ipadapter_faceid":
        return None, {"eligible": False, "reason": "FaceID was already used"}
    assets = faceid_assets_available()
    checkpoint = _pick_faceid_checkpoint()
    if not assets.get("ok") or not checkpoint:
        missing = list(assets.get("missing") or [])
        if not checkpoint:
            missing.append("sdxl_checkpoint")
        return None, {"eligible": False, "reason": "FaceID fallback assets missing", "missing": missing}

    reference = str(
        getattr(job, "_identity_reference_path", None) or _reference_path(job)
    ).strip()
    if not reference:
        return None, {"eligible": False, "reason": "reference image missing"}
    params = dict(data or vars(job))
    params.update(
        {
            "model": checkpoint,
            "reference_image": reference,
            "input_image": None,
            "workflow_mode": "ipadapter_faceid",
            "identity_mode": "ipadapter_faceid",
            "preserve_character": True,
            "face_preservation": True,
            "identity_verify": True,
            "identity_retry_attempted": True,
            "_identity_retry_internal": True,
            "ipadapter_model": assets.get("ipadapter_faceid_model"),
        }
    )
    return params, {"eligible": True, "route": "ipadapter_faceid", "model": checkpoint}


def resolve_identity_route(job, *, model_family: str | None = None) -> dict[str, Any]:
    """Decide kontext / qwen_edit / ipadapter_faceid / img2img for identity jobs."""
    if not is_identity_preservation_job(job):
        return {"route": "none"}

    ref = _reference_path(job)
    if not ref:
        return {"route": "invalid", "reason": "reference image required for identity preservation"}

    mode = normalize_identity_mode(getattr(job, "identity_mode", None)) or "preserve_face"
    family = (model_family or "").lower()

    if mode == "ipadapter_faceid":
        assets = faceid_assets_available()
        if assets["ok"]:
            return {
                "route": "ipadapter_faceid",
                "reference_image": ref,
                **assets,
            }
        kontext = _pick_kontext_checkpoint()
        qwen = _pick_qwen_edit_checkpoint()
        fallback = "kontext" if kontext else ("qwen_edit" if qwen else "img2img")
        return {
            "route": fallback,
            "reference_image": ref,
            "model": kontext or qwen,
            "notice": "FaceID assets missing; using Kontext/Qwen identity instead.",
            "faceid_missing": assets["missing"],
        }

    if mode in {"kontext", "preserve_face", "auto"}:
        kontext = _pick_kontext_checkpoint()
        if kontext and mode != "qwen_edit":
            return {
                "route": "kontext",
                "reference_image": ref,
                "model": kontext,
            }

    if mode in {"qwen_edit", "preserve_face", "auto"}:
        qwen = _pick_qwen_edit_checkpoint()
        if qwen:
            return {
                "route": "qwen_edit",
                "reference_image": ref,
                "model": qwen,
            }

    if family == "flux_kontext":
        return {"route": "kontext", "reference_image": ref}
    if family == "qwen_image_edit":
        return {"route": "qwen_edit", "reference_image": ref}

    return {"route": "img2img", "reference_image": ref}


def _studio_mode(job) -> str:
    return str(getattr(job, "studio_mode", None) or "").strip().lower()


def _edit_studio_identity_patch(
    ref: str,
    *,
    edit_type: str,
    edit_strength: float,
    model: str | None = None,
) -> dict[str, Any]:
    """Keep Edit tab routing while enabling identity preservation flags."""
    patch: dict[str, Any] = {
        "reference_role": "source_edit",
        "input_image": ref,
        "reference_image": ref,
        "preserve_character": True,
        "face_preservation": True,
        "identity_mode": "preserve_face",
        "edit_type": edit_type,
        "edit_strength": edit_strength,
        "cn_selection": "None",
        "cn_type": "None",
    }
    if model:
        patch["model"] = model
    return patch


def _kontext_patch(ref: str, model: str | None = None) -> dict[str, Any]:
    patch: dict[str, Any] = {
        "reference_role": "image_prompt",
        "workflow_mode": "generate",
        "input_image": ref,
        "reference_image": ref,
        "preserve_character": True,
        "face_preservation": True,
        "identity_mode": "preserve_face",
        "edit_type": "kontext",
        "edit_strength": KONTEXT_IDENTITY_STRENGTH,
        "cn_selection": "None",
        "cn_type": "None",
        "steps": 20,
    }
    if model:
        patch["model"] = model
    return patch


def _qwen_edit_patch(ref: str, model: str | None = None) -> dict[str, Any]:
    patch: dict[str, Any] = {
        "reference_role": "image_prompt",
        "workflow_mode": "generate",
        "input_image": ref,
        "reference_image": ref,
        "preserve_character": True,
        "face_preservation": True,
        "identity_mode": "preserve_face",
        "edit_type": "qwen_edit",
        "edit_strength": QWEN_IDENTITY_STRENGTH,
        "cn_selection": "None",
        "cn_type": "None",
    }
    if model:
        patch["model"] = model
    return patch


def _faceid_patch(ref: str, assets: dict[str, Any]) -> dict[str, Any]:
    return {
        "reference_role": "image_prompt",
        "workflow_mode": "ipadapter_faceid",
        "reference_image": ref,
        "input_image": None,
        "preserve_character": True,
        "face_preservation": True,
        "identity_mode": "ipadapter_faceid",
        "edit_type": "auto",
        "cn_selection": "None",
        "cn_type": "None",
        "ipadapter_model": assets.get("ipadapter_faceid_model"),
        "ipadapter_weight": FACEID_DEFAULT_WEIGHT,
    }


def apply_identity_to_job(job) -> dict[str, Any]:
    """Route identity-preservation jobs to Kontext/Qwen or gated FaceID."""
    if getattr(job, "vary_amount", None):
        return {}
    if str(getattr(job, "enhance_auto_fix", False)).lower() in {"1", "true"} or getattr(
        job, "enhance_target", None
    ):
        return {}

    plan = resolve_identity_route(
        job,
        model_family=str(getattr(job, "model_family", None) or ""),
    )
    if plan.get("route") == "none":
        return {}
    if plan.get("route") == "invalid":
        return {"identity_error": plan.get("reason")}

    route = plan["route"]
    ref = plan["reference_image"]
    job._identity_reference_path = ref
    studio = _studio_mode(job)
    out: dict[str, Any] = {}

    if route == "ipadapter_faceid":
        out = _faceid_patch(ref, plan)
    elif studio == "edit" and route == "kontext":
        out = _edit_studio_identity_patch(
            ref,
            edit_type="kontext",
            edit_strength=KONTEXT_IDENTITY_STRENGTH,
            model=plan.get("model"),
        )
    elif studio == "edit" and route == "qwen_edit":
        out = _edit_studio_identity_patch(
            ref,
            edit_type="qwen_edit",
            edit_strength=QWEN_IDENTITY_STRENGTH,
            model=plan.get("model"),
        )
    elif route == "kontext":
        out = _kontext_patch(ref, plan.get("model"))
    elif route == "qwen_edit":
        out = _qwen_edit_patch(ref, plan.get("model"))
    elif route == "img2img":
        out = {
            "reference_role": "restyle",
            "workflow_mode": "generate",
            "input_image": ref,
            "reference_image": ref,
            "preserve_character": True,
            "face_preservation": True,
            "identity_mode": "preserve_face",
            "edit_type": "auto",
            "cn_selection": "Custom...",
            "cn_type": "img2img",
        }
    else:
        return {}

    if plan.get("notice"):
        out["_identity_fallback_notice"] = plan["notice"]

    for key, value in out.items():
        if key.startswith("_"):
            setattr(job, key, value)
        else:
            setattr(job, key, value)
    return out
