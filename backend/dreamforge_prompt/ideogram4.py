"""Ideogram 4 structured JSON prompt helpers (magic prompt via DreamForge brain)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

IDEOGRAM4_PROMPT_MODES = frozenset({"natural", "structured", "auto"})

_TEMPLATE_PATH = Path(__file__).with_name("ideogram4_magic_prompt_template.txt")
_MAGIC_PROMPT_VERSION = "v18-schema+oss-v1"
# Full template system is ~27k chars — exceeds embedded brain n_ctx=4096. Use slim for local LLMs.
_IDEOGRAM4_SLIM_SYSTEM = """You convert a natural-language user idea into a structured JSON caption for Ideogram 4 (merged oss v1 + style_description).

Emit exactly ONE minified JSON object. Top-level keys in this order when present:
aspect_ratio, high_level_description, style_description (optional), compositional_deconstruction

Minimum v1 shape (omit style_description when medium/lighting are obvious from HLD):
aspect_ratio, high_level_description, compositional_deconstruction

Rules:
- No markdown fences, no commentary.
- aspect_ratio: concrete positive integers W:H; never emit the literal string auto.
- high_level_description: one observational sentence (50 words max); start with subject, no "this image shows".
- style_description (optional): photos {"aesthetics":"","lighting":"","photo":"","medium":"photograph","color_palette":["#RRGGBB"]}; non-photos {"aesthetics":"","lighting":"","medium":"illustration|3d_render|painting|graphic_design","art_style":"","color_palette":["#RRGGBB"]}. Use exactly one of photo/art_style.
- compositional_deconstruction is required: background first, then elements.
- background = scene SHELL only (walls, sky, floor, horizon, distant crowd). Floor/ground/turf/pavement/sky NEVER as obj elements — prevents figures clipped half into the ground.
- One coherent subject (person, animal, vehicle, building) = ONE obj; never split body parts into multiple objs.
- Shell-affixed walls (chalkboard, fireplace, mounted TV): mention in background AND emit as first obj with "primary background element" in desc.
- elements: {"type":"obj","bbox":[y1,x1,y2,x2],"desc":"..."} or {"type":"text","text":"verbatim","desc":"..."}. bbox optional for full scenes; integers 0-1000, format [y1,x1,y2,x2].
- Every user-quoted string and overlay/credit line = its own text element with verbatim text (preserve Arabic/CJK). desc fields English; text field uses user language.
- Banned hedges in desc/background: or, might be, various, such as, implied, suggested, things like. Pick ONE concrete value.
- No shadows, bokeh, or render jargon inside obj descs. No negative_prompt or safety-bypass fields.
- Transparent cutout: background exactly "transparent background"; HLD includes "on a transparent background".

Output ONLY the JSON object on one line."""

_SECTION_HEADER = re.compile(r"^\[([^\]]+)\]\s*$", re.MULTILINE)
_QUOTED_LINE = re.compile(r'"([^"\n]+)"|\'([^\'\n]+)\'')
_ARABIC_SCRIPT = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")
_CREDIT_HINT = re.compile(
    r"(?:كلمات|من ديوان|الألحان|words?\s*by|lyrics|credits?|written by|composed by|author|by\s*:)",
    re.IGNORECASE,
)
_OVERLAY_SECTION_HINT = re.compile(
    r"(?:text\s*overlay|overlay|credit|title|headline|caption|subtitle|tagline|name|typography|calligraphy)",
    re.IGNORECASE,
)
_SKIP_SECTION_HINT = re.compile(
    r"(?:^scene$|^subject$|environment|symbolism|mood|^style$|color\s*grading|camera|composition|quality)",
    re.IGNORECASE,
)
_CUTOUT_HINT_RE = re.compile(
    r"(?i)(?:\b(?:cutout|cut-out|isolated|sticker|alpha\s*channel|no\s+background|"
    r"remove\s+background|png\s+with\s+alpha)\b|on\s+a\s+transparent\s+background)"
)
_CUTOUT_HLD_HINT_RE = re.compile(
    r"(?i)(?:\b(?:cutout|cut-out|isolated|sticker|alpha\s*channel|compositing)\b|"
    r"on\s+a\s+transparent\s+background)"
)
_LAYOUT_BBOX_HINT_RE = re.compile(
    r"(?i)(?:\b(?:poster|flyer|banner|mockup|ui\s+layout|layout|infographic|"
    r"magazine\s+spread|title\s+card|album\s+cover|social\s+media\s+post|grid\s+layout|"
    r"collage|typography\s+poster|multi-panel|split\s+screen|app\s+screen)\b)"
)
_SHELL_OBJ_DESC_RE = re.compile(
    r"(?i)(?:^|\b)(?:the )?(?:"
    r"sky(?:line)?|horizon|clouds?|atmosphere|fog|mist|haze|"
    r"(?:glass )?windows?|cityscape|distant (?:city|crowd|mountains?|towers|buildings|skyline)|"
    r"(?:office )?interior walls?|studio backdrop|wall(?:paper)?(?: behind)?|"
    r"(?:wooden |polished |concrete |marble )?(?:floor|ground|turf|pavement|asphalt|sidewalk|"
    r"deck|grass field|ceiling|bookshelf(?:es)?(?: behind)?|neon reflections)"
    r")(?:\b|[.,;]|$)"
)
_TRANSPARENT_BG = "transparent background"

IDEOGRAM4_QUALITY_MODES: dict[str, dict[str, float | int]] = {
    "default": {"steps": 20, "mu": 0.0, "std": 1.75},
    "quality": {"steps": 48, "mu": 0.0, "std": 1.5},
    "turbo": {"steps": 12, "mu": 0.5, "std": 1.75},
}

_IDEOGRAM4_DUAL_CFG = 7.0
_IDEOGRAM4_POLISH_CFG = 3.0
# Official V4_* presets: main steps @ gw=7, then polish steps @ gw=3.
_IDEOGRAM4_POLISH_STEPS: dict[str, int] = {"turbo": 1, "default": 2, "quality": 3}
_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_STYLE_KEYS_PHOTO = ("aesthetics", "lighting", "photo", "medium", "color_palette")
_STYLE_KEYS_ART = ("aesthetics", "lighting", "medium", "art_style", "color_palette")


def _snap_dim(value: int) -> int:
    return max(((int(value) + 15) // 16) * 16, 256)


def _normalize_aspect_ratio_value(
    value: str,
    *,
    width: int = 1024,
    height: int = 1024,
) -> str:
    """Coerce aspect_ratio to W:H (Ideogram expects concrete ratio strings)."""
    raw = str(value or "").strip()
    if re.fullmatch(r"\d+:\d+", raw):
        return raw
    if re.fullmatch(r"\d+", raw):
        side = int(raw)
        return f"{side}:{side}"
    w = _snap_dim(width)
    h = _snap_dim(height)

    def _gcd(a: int, b: int) -> int:
        x, y = abs(a), abs(b)
        while y:
            x, y = y, x % y
        return x or 1

    divisor = _gcd(w, h)
    return f"{max(1, w // divisor)}:{max(1, h // divisor)}"


def ideogram4_cfg_override_schedule(mode: str, steps: int) -> dict[str, float]:
    """Map official polish-step counts to CFGOverride start/end on the cond UNet."""
    polish = _IDEOGRAM4_POLISH_STEPS.get(str(mode or "default").lower(), 2)
    total = max(int(steps), 1)
    main_steps = max(total - polish, 1)
    start = round(main_steps / total, 4)
    return {
        "cfg_override": _IDEOGRAM4_POLISH_CFG,
        "cfg_override_start": min(max(start, 0.0), 0.99),
        "cfg_override_end": 1.0,
    }


def load_magic_prompt_template() -> str:
    if not _TEMPLATE_PATH.is_file():
        raise FileNotFoundError(f"Ideogram 4 magic prompt template missing: {_TEMPLATE_PATH}")
    return _TEMPLATE_PATH.read_text(encoding="utf-8")


def _parse_template_sections() -> tuple[str, str]:
    """Split Comfy template into [SYSTEM] and [USER] sections."""
    text = load_magic_prompt_template()
    if "[SYSTEM]" not in text:
        return text.strip(), ""
    after_system = text.split("[SYSTEM]", 1)[1]
    if "[USER]" in after_system:
        system_part, user_part = after_system.split("[USER]", 1)
        return system_part.strip(), user_part.strip()
    return after_system.strip(), ""


def _parse_bracket_sections(text: str) -> list[tuple[str, str]]:
    """Split [SECTION] blocks from structured creative briefs."""
    matches = list(_SECTION_HEADER.finditer(text))
    if not matches:
        return []
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((match.group(1).strip(), text[start:end].strip()))
    return sections


def _quoted_strings(block: str) -> list[str]:
    found: list[str] = []
    for match in _QUOTED_LINE.finditer(block):
        value = (match.group(1) or match.group(2) or "").strip()
        if value:
            found.append(value)
    return found


def extract_required_image_text(user_prompt: str) -> list[str]:
    """Detect verbatim strings that must appear as Ideogram type:text elements."""
    text = str(user_prompt or "")
    if not text.strip():
        return []

    required: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        cleaned = str(value or "").strip()
        if len(cleaned) < 2 or cleaned in seen:
            return
        seen.add(cleaned)
        required.append(cleaned)

    for section_name, body in _parse_bracket_sections(text):
        if _SKIP_SECTION_HINT.search(section_name):
            continue
        if _OVERLAY_SECTION_HINT.search(section_name):
            for quoted in _quoted_strings(body):
                add(quoted)
            for line in body.splitlines():
                line = line.strip()
                if not line or _QUOTED_LINE.search(line):
                    continue
                if re.match(r"^(main line|secondary line|primary|subtitle)\b", line, re.I):
                    continue
                if _ARABIC_SCRIPT.search(line) or _CREDIT_HINT.search(line):
                    if len(line) <= 160:
                        add(line)

    for quoted in _quoted_strings(text):
        if _ARABIC_SCRIPT.search(quoted):
            add(quoted)
        elif _CREDIT_HINT.search(quoted):
            add(quoted)

    return required


def _format_required_text_hint(required: list[str]) -> str:
    if not required:
        return ""
    lines = "\n".join(f'{index + 1}. "{item}"' for index, item in enumerate(required))
    return (
        "\n\nREQUIRED IN-IMAGE TEXT — emit EACH item below as its own JSON element "
        '{"type":"text","text":"<copy verbatim>","desc":"placement and typography in English"}. '
        "Never translate, romanize, or omit any line:\n"
        f"{lines}"
    )


def _ensure_required_text_elements(obj: dict[str, Any], required: list[str]) -> dict[str, Any]:
    """Guarantee user-specified overlay strings survive LLM omissions."""
    if not required:
        return obj
    out = dict(obj)
    comp_raw = out.get("compositional_deconstruction")
    comp: dict[str, Any] = dict(comp_raw) if isinstance(comp_raw, dict) else {}
    elements: list[Any] = list(comp.get("elements") or [])

    existing: set[str] = set()
    for item in elements:
        if isinstance(item, dict) and item.get("type") == "text":
            text_val = str(item.get("text") or item.get("desc") or "").strip()
            if text_val:
                existing.add(text_val)

    for index, line in enumerate(required):
        if line in existing:
            continue
        desc = "User-specified overlay text"
        if _ARABIC_SCRIPT.search(line):
            desc = "Arabic calligraphy overlay integrated with scene lighting"
        elif _CREDIT_HINT.search(line):
            desc = "Credit line typography overlay"
        elements.append({"type": "text", "text": line, "desc": desc})
        existing.add(line)

    comp["elements"] = elements
    out["compositional_deconstruction"] = comp
    return out


def build_magic_prompt_messages(user_prompt: str, width: int, height: int) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the brain — not one giant user blob."""
    system_tpl, user_tpl = _parse_template_sections()
    w = _snap_dim(width)
    h = _snap_dim(height)
    aspect = f"{w}:{h}"
    idea = str(user_prompt or "").strip()
    required_hint = _format_required_text_hint(extract_required_image_text(idea))
    if user_tpl:
        user_msg = user_tpl.replace("{{original_prompt}}", idea)
        user_msg = user_msg.replace("{{aspect_ratio}}", aspect)
        user_msg = user_msg.replace("{{width}}:{{height}}", aspect)
    else:
        user_msg = f"TARGET IMAGE ASPECT RATIO: {aspect} (width:height).\nUser idea: {idea}"
    if required_hint:
        user_msg = f"{user_msg}{required_hint}"
    return system_tpl, user_msg


def _brain_system_prompt(provider_id: str, full_system: str, user_msg: str) -> str:
    """Local embedded brains cannot fit the full Comfy template in context."""
    pid = (provider_id or "").lower()
    if pid in ("embedded", "llamacpp", "llama.cpp"):
        return _IDEOGRAM4_SLIM_SYSTEM
    if len(full_system) + len(user_msg) > 12000:
        return _IDEOGRAM4_SLIM_SYSTEM
    return full_system or _IDEOGRAM4_SLIM_SYSTEM


def build_magic_prompt_instruction(user_prompt: str, width: int, height: int) -> str:
    """Legacy single-string instruction (debug/logging). Prefer build_magic_prompt_messages."""
    system_tpl, user_msg = build_magic_prompt_messages(user_prompt, width, height)
    if system_tpl:
        return f"{system_tpl}\n\n{user_msg}"
    return user_msg


def _extract_json_object(text: str) -> str:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        return raw[start : end + 1].strip()
    return raw


def _sanitize_json_text(text: str) -> str:
    s = str(text or "")
    s = s.replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'")
    s = re.sub(r",\s*([}\]])", r"\1", s)
    return s.strip()


def _close_truncated_json_object(text: str) -> str:
    s = text.strip()
    if not s.startswith("{"):
        return s
    s = re.sub(r",\s*$", "", s)
    open_brackets = s.count("[") - s.count("]")
    open_braces = s.count("{") - s.count("}")
    if open_brackets > 0:
        s += "]" * open_brackets
    if open_braces > 0:
        s += "}" * open_braces
    return s


def _extract_json_string_field(raw: str, field: str) -> str | None:
    pattern = rf'"{re.escape(field)}"\s*:\s*"((?:\\.|[^"\\])*)"'
    match = re.search(pattern, raw, re.DOTALL)
    if match:
        try:
            return bytes(match.group(1), "utf-8").decode("unicode_escape")
        except UnicodeDecodeError:
            return match.group(1)
    relaxed = rf'"{re.escape(field)}"\s*:\s*"([\s\S]*?)"\s*[,}}]'
    match2 = re.search(relaxed, raw)
    if match2:
        return match2.group(1).replace("\\n", " ").replace("\n", " ").strip()
    return None


def _fallback_caption_from_broken_json(raw: str, user_prompt: str = "") -> dict[str, Any] | None:
    hld = _extract_json_string_field(raw, "high_level_description")
    if not hld and user_prompt:
        hld = str(user_prompt).strip()
    if not hld:
        return None
    out: dict[str, Any] = {"high_level_description": hld[:500]}
    aspect = _extract_json_string_field(raw, "aspect_ratio")
    if aspect:
        out["aspect_ratio"] = aspect
    return out


def _loads_ideogram_json_object(text: str, *, user_prompt: str = "") -> dict[str, Any]:
    """Parse LLM JSON with light repair and regex fallback for magic prompt."""
    extracted = _extract_json_object(text)
    candidates: list[str] = []
    seen: set[str] = set()

    def add(candidate: str) -> None:
        cleaned = candidate.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            candidates.append(cleaned)

    add(extracted)
    sanitized = _sanitize_json_text(extracted)
    add(sanitized)
    add(_close_truncated_json_object(sanitized))

    last_exc: json.JSONDecodeError | None = None
    for candidate in candidates:
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError as exc:
            last_exc = exc

    fallback = _fallback_caption_from_broken_json(extracted, user_prompt)
    if fallback:
        return fallback

    msg = str(last_exc) if last_exc else "unknown JSON error"
    raise ValueError(f"invalid JSON: {msg}")


def _normalize_hex(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("empty color")
    if not raw.startswith("#"):
        raw = f"#{raw}"
    if not _HEX_RE.match(raw):
        raise ValueError(f"invalid hex color: {value!r}")
    return raw.upper()


def _normalize_palette(values: Any, *, max_items: int) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in values[:max_items]:
        try:
            hex_val = _normalize_hex(str(item))
        except ValueError:
            continue
        if hex_val not in seen:
            seen.add(hex_val)
            out.append(hex_val)
    return out


def _repair_bbox_coords(raw: Any) -> list[int] | None:
    """Repair LLM bbox output; return None when bbox should be dropped."""
    if raw is None:
        return None
    if not isinstance(raw, list) or len(raw) != 4:
        return None
    try:
        coords = [float(v) for v in raw]
    except (TypeError, ValueError):
        return None
    if not all(v == v and abs(v) != float("inf") for v in coords):  # finite
        return None

    if max(coords) <= 1.0 and min(coords) >= 0:
        coords = [v * 1000.0 for v in coords]
    elif max(coords) <= 100.0 and min(coords) >= 0:
        coords = [v * 10.0 for v in coords]
    elif max(coords) > 1000:
        scale = 1000.0 / max(coords)
        coords = [v * scale for v in coords]

    ints = [max(0, min(1000, int(round(v)))) for v in coords]
    y1, x1, y2, x2 = ints

    if y1 > y2:
        y1, y2 = y2, y1
    if x1 > x2:
        x1, x2 = x2, x1
    if y2 <= y1:
        y2 = min(1000, y1 + 1)
    if x2 <= x1:
        x2 = min(1000, x1 + 1)
    if y2 <= y1 or x2 <= x1:
        return None
    return [y1, x1, y2, x2]


def _normalize_bbox(raw: Any) -> list[int] | None:
    return _repair_bbox_coords(raw)


def _normalize_style_description(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("style_description must be an object")
    out: dict[str, Any] = {}
    medium = str(raw.get("medium") or "").strip().lower()
    has_art = bool(str(raw.get("art_style") or "").strip()) and (
        medium in {"illustration", "3d_render", "painting", "graphic_design"}
        or not bool(str(raw.get("photo") or "").strip())
    )
    keys = _STYLE_KEYS_ART if has_art else _STYLE_KEYS_PHOTO
    for key in keys:
        if key not in raw:
            continue
        if key == "color_palette":
            palette = _normalize_palette(raw[key], max_items=16)
            if palette:
                out[key] = palette
        else:
            text = str(raw[key] or "").strip()
            if text:
                out[key] = text
    return out or None


def _normalize_element(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    kind = str(raw.get("type") or "").strip().lower()
    if kind not in {"obj", "text"}:
        return None
    out: dict[str, Any] = {"type": kind}
    bbox = _normalize_bbox(raw.get("bbox"))
    if bbox is not None:
        out["bbox"] = bbox
    desc = str(raw.get("desc") or "").strip()
    if kind == "text":
        text = raw.get("text")
        if text is None and desc:
            out["text"] = desc
        elif text is not None:
            out["text"] = str(text)
        else:
            return None
        if desc:
            out["desc"] = desc
    elif not desc:
        return None
    else:
        out["desc"] = desc
    palette = _normalize_palette(raw.get("color_palette"), max_items=5)
    if palette:
        out["color_palette"] = palette
    return out


def _is_transparent_background(bg: str) -> bool:
    return str(bg or "").strip().lower() == _TRANSPARENT_BG


def _wants_transparent_background(user_prompt: str, obj: dict[str, Any]) -> bool:
    if _CUTOUT_HINT_RE.search(user_prompt or ""):
        return True
    hld = str(obj.get("high_level_description") or "")
    comp = obj.get("compositional_deconstruction")
    bg = ""
    if isinstance(comp, dict):
        bg = str(comp.get("background") or "")
    if _is_transparent_background(bg) and _CUTOUT_HLD_HINT_RE.search(hld):
        return True
    return False


def _wants_layout_bboxes(user_prompt: str, obj: dict[str, Any]) -> bool:
    hld = str(obj.get("high_level_description") or "")
    hay = f"{user_prompt} {hld}"
    return bool(_LAYOUT_BBOX_HINT_RE.search(hay))


def _is_shell_obj_element(el: dict[str, Any]) -> bool:
    if el.get("type") != "obj":
        return False
    desc = str(el.get("desc") or "").strip()
    return bool(desc and _SHELL_OBJ_DESC_RE.search(desc))


def _synthesize_scene_background(hld: str, shell_fragments: list[str], existing_bg: str) -> str:
    parts: list[str] = []
    existing = str(existing_bg or "").strip()
    if existing and not _is_transparent_background(existing):
        parts.append(existing.rstrip("."))
    for frag in shell_fragments:
        cleaned = str(frag or "").strip().rstrip(".")
        if not cleaned:
            continue
        joined = " ".join(parts).lower()
        if cleaned.lower() not in joined:
            parts.append(cleaned)
    if parts:
        merged = "; ".join(parts)
        base = str(hld or "").strip().rstrip(".")
        if base and base.lower() not in merged.lower():
            return f"{base}. {merged}."
        return merged + ("." if not merged.endswith(".") else "")
    base = str(hld or "").strip()
    if not base:
        return "Detailed scene environment with coherent lighting and depth."
    return base + ("." if not base.endswith(".") else "")


def _apply_bbox_guardrails(comp: dict[str, Any], *, layout_mode: bool) -> None:
    elements = comp.get("elements")
    if not isinstance(elements, list) or layout_mode:
        return
    for el in elements:
        if isinstance(el, dict) and el.get("type") == "obj":
            el.pop("bbox", None)


def apply_ideogram_composition_guardrails(
    obj: dict[str, Any],
    *,
    user_prompt: str = "",
) -> dict[str, Any]:
    """Repair common LLM caption mistakes: wrong transparent bg, shell objs, tight bboxes."""
    if not isinstance(obj, dict):
        return obj
    out = dict(obj)
    comp_raw = out.get("compositional_deconstruction")
    if not isinstance(comp_raw, dict):
        return out

    comp = dict(comp_raw)
    hld = str(out.get("high_level_description") or "").strip()
    bg = str(comp.get("background") or "").strip()
    elements_raw = comp.get("elements")
    elements: list[Any] = list(elements_raw) if isinstance(elements_raw, list) else []

    shell_fragments: list[str] = []
    kept_elements: list[Any] = []
    for item in elements:
        if isinstance(item, dict) and _is_shell_obj_element(item):
            desc = str(item.get("desc") or "").strip()
            if desc:
                shell_fragments.append(desc)
            continue
        kept_elements.append(item)

    if shell_fragments or len(kept_elements) != len(elements):
        comp["elements"] = kept_elements
        elements = kept_elements

    layout_mode = _wants_layout_bboxes(user_prompt, out)
    _apply_bbox_guardrails(comp, layout_mode=layout_mode)

    if _is_transparent_background(bg) and not _wants_transparent_background(user_prompt, out):
        comp["background"] = _synthesize_scene_background(hld, shell_fragments, bg)
    elif shell_fragments and not _is_transparent_background(bg):
        merged_bg = _synthesize_scene_background(hld, shell_fragments, bg)
        if merged_bg:
            comp["background"] = merged_bg
    elif not bg.strip() and (shell_fragments or hld):
        comp["background"] = _synthesize_scene_background(hld, shell_fragments, "")

    out["compositional_deconstruction"] = comp
    return out


def canonicalize_ideogram_caption_obj(obj: dict[str, Any]) -> dict[str, Any]:
    """Normalize and emit stable key order for Ideogram CLIP encode."""
    if not isinstance(obj, dict):
        raise ValueError("Ideogram caption must be a JSON object")

    out: dict[str, Any] = {}
    aspect = str(obj.get("aspect_ratio") or "").strip()
    if aspect:
        out["aspect_ratio"] = aspect

    hld = str(obj.get("high_level_description") or "").strip()
    if hld:
        out["high_level_description"] = hld

    style = _normalize_style_description(obj.get("style_description"))
    if style:
        out["style_description"] = style

    comp_raw = obj.get("compositional_deconstruction")
    if comp_raw is not None:
        if not isinstance(comp_raw, dict):
            raise ValueError("compositional_deconstruction must be an object")
        comp: dict[str, Any] = {}
        bg = str(comp_raw.get("background") or "").strip()
        if not bg and hld:
            bg = hld
        if bg:
            comp["background"] = bg
        elements_raw = comp_raw.get("elements")
        if elements_raw is not None:
            if not isinstance(elements_raw, list):
                raise ValueError("elements must be an array")
            normalized_elements = [
                el for el in (_normalize_element(item) for item in elements_raw) if el
            ]
            if normalized_elements:
                comp["elements"] = normalized_elements
        if comp:
            out["compositional_deconstruction"] = comp

    if not out:
        raise ValueError("Ideogram caption is empty")
    return out


def validate_ideogram_caption(text: str, *, user_prompt: str = "") -> dict[str, Any]:
    """Parse and validate caption; return {ok, errors, normalized}."""
    errors: list[str] = []
    try:
        obj = _loads_ideogram_json_object(text)
        obj = apply_ideogram_composition_guardrails(obj, user_prompt=user_prompt)
        normalized_obj = canonicalize_ideogram_caption_obj(obj)
        normalized = json.dumps(normalized_obj, ensure_ascii=False, separators=(",", ":"))
        return {"ok": True, "errors": [], "normalized": normalized}
    except ValueError as exc:
        errors.append(str(exc))
    return {"ok": False, "errors": errors, "normalized": None}


def looks_like_ideogram_json(text: str) -> bool:
    try:
        obj = _loads_ideogram_json_object(text)
    except ValueError:
        return False
    if not isinstance(obj, dict):
        return False
    return any(
        key in obj
        for key in (
            "high_level_description",
            "compositional_deconstruction",
            "aspect_ratio",
            "style_description",
        )
    )


def normalize_ideogram_caption_obj(obj: dict[str, Any], *, user_prompt: str = "") -> str:
    guarded = apply_ideogram_composition_guardrails(obj, user_prompt=user_prompt)
    return json.dumps(
        canonicalize_ideogram_caption_obj(guarded),
        ensure_ascii=False,
        separators=(",", ":"),
    )


def normalize_ideogram_caption(text: str, *, user_prompt: str = "") -> str:
    """Parse, validate, and re-emit minified JSON for CLIPTextEncode."""
    result = validate_ideogram_caption(text, user_prompt=user_prompt)
    if not result["ok"]:
        raise ValueError("; ".join(result["errors"]))
    return str(result["normalized"])


def _settings_performance(settings: dict[str, Any] | None, job: Any = None) -> str:
    if job is not None:
        perf = getattr(job, "performance", None)
        if perf:
            return str(perf).strip()
    if settings:
        perf = settings.get("performance")
        if perf:
            return str(perf).strip()
    return ""


def _coalesce_steps(settings: dict[str, Any] | None, job: Any = None) -> int | None:
    steps = _optional_numeric(settings, job, "steps")
    if steps is not None:
        return int(steps)
    return None


def resolve_ideogram4_mode(settings: dict[str, Any] | None, job: Any = None) -> str:
    raw = ""
    if job is not None:
        raw = str(getattr(job, "ideogram4_mode", None) or getattr(job, "ideogram4_quality", None) or "")
    if not raw and settings:
        raw = str(settings.get("ideogram4_mode") or settings.get("ideogram4_quality") or "")
    key = raw.strip().lower()
    if key in IDEOGRAM4_QUALITY_MODES:
        return key

    perf = _settings_performance(settings, job).lower()
    if perf == "quality":
        return "quality"
    if perf in {"lightning", "lcm", "extreme speed"}:
        return "turbo"
    if perf == "speed":
        return "default"
    if perf in {"custom...", "custom"}:
        steps = _coalesce_steps(settings, job)
        if steps is not None:
            if steps >= 40:
                return "quality"
            if steps <= 14:
                return "turbo"
        return "default"
    return "default"


def resolve_ideogram4_prompt_mode(settings: dict[str, Any] | None, job: Any = None) -> str:
    raw = ""
    if job is not None:
        raw = str(getattr(job, "ideogram4_prompt_mode", None) or "")
    if not raw and settings:
        raw = str(settings.get("ideogram4_prompt_mode") or "")
    key = raw.strip().lower() or "auto"
    if key not in IDEOGRAM4_PROMPT_MODES:
        return "natural"
    return key


def _enhance_on_generate(settings: dict[str, Any] | None, job: Any = None) -> bool:
    if job is not None and getattr(job, "ideogram4_enhance_on_generate", None) is not None:
        return bool(getattr(job, "ideogram4_enhance_on_generate"))
    if settings and settings.get("ideogram4_enhance_on_generate") is not None:
        return bool(settings.get("ideogram4_enhance_on_generate"))
    return False


def _allow_quality_on_16gb(settings: dict[str, Any] | None, job: Any = None) -> bool:
    if job is not None and getattr(job, "ideogram4_allow_quality_on_16gb", None) is not None:
        return bool(getattr(job, "ideogram4_allow_quality_on_16gb"))
    if settings and settings.get("ideogram4_allow_quality_on_16gb") is not None:
        return bool(settings.get("ideogram4_allow_quality_on_16gb"))
    return _settings_performance(settings, job).lower() == "quality"


def _optional_numeric(settings: dict[str, Any] | None, job: Any, key: str) -> float | int | None:
    if job is not None:
        val = getattr(job, key, None)
        if val is not None:
            return val
    if settings and settings.get(key) is not None:
        return settings[key]
    return None


def _apply_ideogram4_advanced_overrides(
    sched: dict[str, int | float | str | list[str]],
    settings: dict[str, Any] | None,
    job: Any = None,
) -> dict[str, int | float | str | list[str]]:
    """Optional per-run scheduler overrides (advanced UI)."""
    out = dict(sched)
    for src, dst in (
        ("ideogram4_mu_override", "mu"),
        ("ideogram4_std_override", "std"),
        ("ideogram4_dual_cfg_override", "dual_cfg"),
    ):
        val = _optional_numeric(settings, job, src)
        if val is not None:
            out[dst] = float(val)
    steps = _optional_numeric(settings, job, "ideogram4_steps_override")
    if steps is not None:
        out["steps"] = int(steps)
    perf = _settings_performance(settings, job).lower()
    if perf in {"custom...", "custom"} and steps is None:
        user_steps = _coalesce_steps(settings, job)
        if user_steps is not None:
            out["steps"] = int(user_steps)
    return out


def ideogram4_scheduler_params(
    settings: dict[str, Any] | None,
    *,
    job: Any = None,
    width: int = 1024,
    height: int = 1024,
    vram_tier: str | None = None,
) -> dict[str, int | float | str | list[str]]:
    mode = resolve_ideogram4_mode(settings, job)
    preset = IDEOGRAM4_QUALITY_MODES[mode]
    sched: dict[str, int | float | str | list[str]] = {
        "steps": int(preset["steps"]),
        "mu": float(preset["mu"]),
        "std": float(preset["std"]),
        "width": _snap_dim(width),
        "height": _snap_dim(height),
        "dual_cfg": _IDEOGRAM4_DUAL_CFG,
        "mode": mode,
        "warnings": [],
    }
    return apply_ideogram4_vram_caps(
        _apply_ideogram4_advanced_overrides(sched, settings, job),
        vram_tier=vram_tier or "16gb",
        allow_quality_on_16gb=_allow_quality_on_16gb(settings, job),
    )


def apply_ideogram4_vram_caps(
    sched: dict[str, int | float | str | list[str]],
    *,
    vram_tier: str,
    allow_quality_on_16gb: bool = False,
) -> dict[str, int | float | str | list[str]]:
    """Clamp Ideogram 4 resolution/mode for dual-UNet memory pressure."""
    out = dict(sched)
    warnings = list(out.get("warnings") or [])
    tier = (vram_tier or "16gb").lower()
    # Dual-UNet + Qwen3VL CLIP is tight on 16 GB Windows (WDDM reserve ~2 GB).
    max_side = {"16gb": 896, "8gb": 768, "5gb": 512}.get(tier, 896)
    orig_w = int(out.get("width") or 1024)
    orig_h = int(out.get("height") or 1024)
    out["width"] = _snap_dim(min(orig_w, max_side))
    out["height"] = _snap_dim(min(orig_h, max_side))

    mode = str(out.get("mode") or "default")
    if tier in {"8gb", "5gb"} and mode != "turbo":
        preset = IDEOGRAM4_QUALITY_MODES["turbo"]
        out["mode"] = "turbo"
        out["steps"] = int(preset["steps"])
        out["mu"] = float(preset["mu"])
        out["std"] = float(preset["std"])
        warnings.append("Ideogram 4 quality mode capped to Turbo for your VRAM tier.")
    if tier == "16gb" and (orig_w > max_side or orig_h > max_side):
        warnings.append(
            "Ideogram 4 resolution capped to 896 px on 16 GB VRAM (dual-UNet memory). "
            "Use Speed mode or a lower aspect preset if generation still fails."
        )
    if tier == "16gb" and mode == "quality" and not allow_quality_on_16gb:
        preset = IDEOGRAM4_QUALITY_MODES["default"]
        out["mode"] = "default"
        out["steps"] = int(preset["steps"])
        out["mu"] = float(preset["mu"])
        out["std"] = float(preset["std"])
        warnings.append(
            "Ideogram 4 Quality (48 steps) capped to Default (20 steps) on 16 GB VRAM. "
            "Use Speed or Default performance, or upgrade VRAM for full Quality."
        )
    out["warnings"] = warnings
    mode_key = str(out.get("mode") or "default")
    steps = int(out.get("steps") or 20)
    out.update(ideogram4_cfg_override_schedule(mode_key, steps))
    return out


def _configure_brain_from_app_config(brain: Any, params: dict[str, Any] | None = None) -> None:
    from dreamforge_app_config import load_app_config

    cfg = load_app_config(redacted=False)
    agent = dict(cfg.get("agent") or {})
    if params:
        for key in ("brain_provider", "brain_base_url", "brain_model", "brain_api_key"):
            if params.get(key):
                mapped = {
                    "brain_provider": "provider",
                    "brain_base_url": "base_url",
                    "brain_model": "model",
                    "brain_api_key": "api_key",
                }[key]
                agent[mapped] = params[key]
    provider = str(agent.get("provider") or "embedded")
    brain.configure(
        provider,
        base_url=str(agent.get("base_url") or ""),
        model=str(agent.get("model") or ""),
        api_key=str(agent.get("api_key") or ""),
    )


def run_ideogram4_magic_prompt(
    user_prompt: str,
    width: int,
    height: int,
    *,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Expand natural language to structured JSON via configured DreamForge brain."""
    from dreamforge_brain import AiBrain

    full_system, user_msg = build_magic_prompt_messages(user_prompt, width, height)
    required_text = extract_required_image_text(user_prompt)
    brain = AiBrain()
    _configure_brain_from_app_config(brain, params)
    system = _brain_system_prompt(getattr(brain, "provider_id", ""), full_system, user_msg)
    meta = {
        "magic_prompt_instruction": user_msg,
        "magic_prompt_system": "slim" if system == _IDEOGRAM4_SLIM_SYSTEM else "full",
        "magic_prompt_version": _MAGIC_PROMPT_VERSION,
    }
    try:
        raw = brain.think(user_msg, system, max_tokens=8192)
    except Exception as exc:
        return {
            "ok": False,
            "error": f"Brain magic prompt failed: {exc}",
            **meta,
        }

    if not str(raw or "").strip():
        return {
            "ok": False,
            "error": (
                "Brain returned an empty response. Check App Settings → Agent: ensure your "
                "brain provider (embedded GGUF, Ollama, or LM Studio) is running and loaded. "
                "Ideogram Enhance needs a working local LLM."
            ),
            "magic_prompt_raw": raw,
            **meta,
        }

    try:
        obj = _loads_ideogram_json_object(raw, user_prompt=user_prompt)
        obj = _ensure_required_text_elements(obj, required_text)
        obj = apply_ideogram_composition_guardrails(obj, user_prompt=user_prompt)
        obj["aspect_ratio"] = _normalize_aspect_ratio_value(
            str(obj.get("aspect_ratio") or ""),
            width=width,
            height=height,
        )
        try:
            caption = normalize_ideogram_caption_obj(obj, user_prompt=user_prompt)
        except ValueError:
            stripped = dict(obj)
            comp_raw = stripped.get("compositional_deconstruction")
            if isinstance(comp_raw, dict):
                comp = dict(comp_raw)
                comp.pop("elements", None)
                stripped["compositional_deconstruction"] = comp
            caption = normalize_ideogram_caption_obj(stripped, user_prompt=user_prompt)
    except ValueError as exc:
        fallback = _fallback_caption_from_broken_json(_extract_json_object(raw), user_prompt)
        if fallback:
            try:
                aspect = f"{_snap_dim(width)}:{_snap_dim(height)}"
                fallback.setdefault("aspect_ratio", aspect)
                hld = str(fallback.get("high_level_description") or "").strip()
                if len(hld.split()) > 50:
                    fallback["high_level_description"] = " ".join(hld.split()[:50])
                fallback = _ensure_required_text_elements(fallback, required_text)
                fallback = apply_ideogram_composition_guardrails(fallback, user_prompt=user_prompt)
                caption = normalize_ideogram_caption_obj(fallback, user_prompt=user_prompt)
            except ValueError:
                return {
                    "ok": False,
                    "error": f"Ideogram magic prompt returned invalid JSON: {exc}",
                    "magic_prompt_raw": raw,
                    **meta,
                }
        else:
            return {
                "ok": False,
                "error": f"Ideogram magic prompt returned invalid JSON: {exc}",
                "magic_prompt_raw": raw,
                **meta,
            }

    return {
        "ok": True,
        "prompt": caption,
        "prompt_format": "json",
        "magic_prompt_source": "brain",
        **meta,
    }


def is_ideogram_inpaint_job(job: Any) -> bool:
    """True when the job is a masked inpaint edit (image + mask required)."""
    edit = str(getattr(job, "edit_type", "") or "").lower()
    cn = str(getattr(job, "cn_type", "") or "").lower()
    mode = str(
        getattr(job, "workflow_mode", None) or getattr(job, "comfy_workflow_mode", None) or ""
    ).lower()
    has_mask = bool(getattr(job, "inpaint_mask_path", None))
    has_image = bool(getattr(job, "input_image", None))
    if not has_image or not has_mask:
        return False
    return edit == "inpaint" or cn == "inpaint" or mode == "inpaint"


def ideogram_json_to_inpaint_prompt(text: str) -> str:
    """Use only the natural-language slice of a structured caption for inpaint CLIP."""
    if not looks_like_ideogram_json(text):
        return text
    try:
        obj = _loads_ideogram_json_object(text)
    except ValueError:
        return text
    hld = str(obj.get("high_level_description") or "").strip()
    return hld or text


def ideogram_inpaint_prompt(prompt: str, job: Any) -> str:
    """Natural-language inpaint wording for Ideogram CLIP (never full JSON captions)."""
    text = ideogram_json_to_inpaint_prompt(str(prompt or "").strip())
    if not text:
        return (
            "Fill the masked region with content that matches the surrounding image. "
            "Seamless blend, consistent lighting and perspective."
        )
    lower = text.lower()
    if "masked" in lower or "seamless" in lower:
        return text
    return (
        f"In the masked region: {text.rstrip('. ')}. Blend seamlessly with surrounding areas; "
        "preserve lighting, perspective, and unchanged regions."
    )


def is_ideogram_identity_generate_job(job: Any) -> bool:
    """Generate tab with a reference photo — preserve face, new scene (not inpaint/edit)."""
    if is_ideogram_inpaint_job(job):
        return False
    mode = str(
        getattr(job, "workflow_mode", None) or getattr(job, "comfy_workflow_mode", None) or "generate"
    ).lower()
    if mode in {"edit", "inpaint", "upscale", "agent"}:
        return False
    edit = str(getattr(job, "edit_type", "") or "").lower()
    if edit == "inpaint":
        return False
    has_ref = bool(getattr(job, "input_image", None) or getattr(job, "reference_image", None))
    if not has_ref:
        return False
    return bool(
        getattr(job, "face_preservation", False)
        or str(getattr(job, "identity_mode", "") or "").lower()
        in {"face", "faceid", "face_id", "preserve_face", "ipadapter_faceid", "kontext", "qwen_edit", "auto"}
        or getattr(job, "preserve_character", False)
    )


def ideogram_identity_generate_prompt(prompt: str, job: Any) -> str:
    """Natural-language identity-guided scene prompt for Ideogram img2img reference runs."""
    text = ideogram_json_to_inpaint_prompt(str(prompt or "").strip())
    if not text:
        return (
            "Recreate the same person from the reference photo in a new scene. "
            "Preserve facial features, skin tone, and identity; change outfit, pose, and background as described."
        )
    lower = text.lower()
    if "same person" in lower or "preserve" in lower and "identity" in lower:
        return text
    return (
        f"Same person as the reference photo: {text.rstrip('. ')}. "
        "Preserve facial identity, features, and likeness; new scene, outfit, and background as described."
    )


def resolve_input_image_dimensions(job: Any, default_w: int, default_h: int) -> tuple[int, int]:
    """Match Ideogram scheduler dims to the uploaded source image when possible."""
    input_path = getattr(job, "input_image", None)
    if not input_path:
        return int(default_w), int(default_h)
    try:
        from PIL import Image

        from dreamforge_paths import resolve_image_path_or_raise

        with Image.open(resolve_image_path_or_raise(str(input_path))) as img:
            w, h = img.size
        return _snap_dim(w), _snap_dim(h)
    except (OSError, ValueError, ImportError):
        return int(default_w), int(default_h)


def prepare_ideogram4_generation_prompts(
    job: Any,
    prompt: str,
    negative: str,
    settings: dict[str, Any],
    *,
    width: int,
    height: int,
) -> dict[str, Any]:
    """Prepare Ideogram 4 prompt for Comfy (natural, structured JSON, or auto-enhance)."""
    text = str(prompt or "").strip()
    prompt_mode = resolve_ideogram4_prompt_mode(settings, job)
    enhance_on_generate = _enhance_on_generate(settings, job)
    base: dict[str, Any] = {
        "negative": "",
        "loras": [],
        "comfy_loras": list(settings.get("comfy_loras") or []),
        "styles_applied": [],
        "prompt_enhancer": "none",
        "expansion_available": False,
        "shift_attention_distance": None,
        "ideogram4_mode": resolve_ideogram4_mode(settings, job),
        "ideogram4_prompt_mode": prompt_mode,
    }

    if is_ideogram_inpaint_job(job):
        return {
            **base,
            "prompt": ideogram_inpaint_prompt(text, job),
            "prompt_format": "natural",
            "ideogram4_inpaint": True,
        }

    if is_ideogram_identity_generate_job(job):
        return {
            **base,
            "prompt": ideogram_identity_generate_prompt(text, job),
            "prompt_format": "natural",
            "ideogram4_identity_generate": True,
        }

    if prompt_mode == "structured":
        if not looks_like_ideogram_json(text):
            return {
                **base,
                "prompt": text,
                "prompt_format": "natural",
                "prompt_prepare_error": (
                    "Structured JSON mode requires a valid Ideogram caption in the prompt box."
                ),
            }
        try:
            text = normalize_ideogram_caption(text)
        except ValueError as exc:
            return {
                **base,
                "prompt": text,
                "prompt_format": "json",
                "prompt_prepare_error": str(exc),
            }
        return {**base, "prompt": text, "prompt_format": "json"}

    should_magic = prompt_mode == "auto" or (prompt_mode == "natural" and enhance_on_generate)
    if should_magic and text and not looks_like_ideogram_json(text):
        magic = run_ideogram4_magic_prompt(text, width, height, params=None)
        if not magic.get("ok"):
            return {
                **base,
                "prompt": text,
                "prompt_format": "natural",
                "prompt_prepare_error": magic.get("error") or "Ideogram magic prompt failed",
            }
        return {
            **base,
            "prompt": magic.get("prompt") or text,
            "prompt_format": "json",
            "magic_prompt_source": magic.get("magic_prompt_source"),
        }

    if looks_like_ideogram_json(text):
        try:
            text = normalize_ideogram_caption(text)
            prompt_format = "json"
        except ValueError:
            prompt_format = "natural"
    else:
        prompt_format = "natural"

    return {**base, "prompt": text, "prompt_format": prompt_format}
