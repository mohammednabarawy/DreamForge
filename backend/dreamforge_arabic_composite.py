"""Route Arabic poster / text-integrate jobs through arabic_poster_pipeline."""

from __future__ import annotations

import os
import re
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from _paths import PROJECT_ROOT

_ARABIC_BLOCK = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]+(?:[^\n]{0,80})?")
_QUOTED = re.compile(r"""['"]([^'"]+)['"]""")


def extract_arabic_text(text: str | None) -> str | None:
    """Best-effort extraction of Arabic headline text from user intent."""
    if not text:
        return None
    for match in _QUOTED.finditer(text):
        candidate = match.group(1).strip()
        if _ARABIC_BLOCK.search(candidate):
            return candidate
    block = _ARABIC_BLOCK.search(text)
    if block:
        return block.group(0).strip()
    return None


def _pick_value(*values: Any, default: Any = None) -> Any:
    for value in values:
        if value is not None:
            return value
    return default


def resolve_arabic_text(job: Any) -> str | None:
    for attr in ("arabic_text", "headline", "text"):
        value = getattr(job, attr, None)
        if value is not None and str(value).strip():
            return str(value).strip()
    return extract_arabic_text(getattr(job, "prompt", None))


def arabic_composite_requested(job: Any) -> bool:
    mode = str(getattr(job, "workflow_mode", "") or "").strip().lower()
    use_case = str(getattr(job, "use_case", "") or "").strip().lower()
    edit_type = str(getattr(job, "edit_type", "") or "").strip().lower()
    if mode in {"arabic_text_composite", "text_integrate", "arabic_poster"}:
        return True
    if edit_type in {"text_integrate", "arabic_text_composite"}:
        return True
    if use_case == "arabic_poster" and resolve_arabic_text(job):
        return True
    return False


def _pipeline_args(
    *,
    job: Any,
    base_args: Any,
    model: dict,
    prompt: str,
    negative: str,
    width: int,
    height: int,
    seed: int,
) -> Namespace:
    arabic_text = resolve_arabic_text(job)
    scene_prompt = getattr(job, "scene_prompt", None) or prompt
    output = getattr(job, "output", None) or getattr(base_args, "output", None)
    if not output:
        output = str(PROJECT_ROOT / "outputs" / "arabic_poster.png")
    elif not Path(str(output)).is_absolute():
        output = str(PROJECT_ROOT / output)

    payload = {
        "arabic_text": arabic_text,
        "scene_prompt": scene_prompt,
        "subject": getattr(job, "subject", None),
        "prompt": prompt,
        "negative_prompt": negative,
        "output": output,
        "width": width,
        "height": height,
        "seed": seed,
        "performance": _pick_value(
            getattr(job, "performance", None),
            getattr(base_args, "performance", None),
            default="Speed",
        ),
        "steps": _pick_value(getattr(job, "steps", None), getattr(base_args, "steps", None)),
        "styles": _pick_value(getattr(job, "styles", None), getattr(base_args, "styles", None)),
        "base_model": model.get("name") or getattr(job, "model", None),
        "cfg_scale": _pick_value(
            getattr(job, "cfg_scale", None),
            getattr(base_args, "cfg_scale", None),
            default=7.0,
        ),
        "image_number": _pick_value(getattr(job, "image_number", None), default=1) or 1,
        "lora": _pick_value(getattr(job, "lora", None), getattr(base_args, "lora", None), default=[]) or [],
        "harmonize": getattr(job, "harmonize", None),
        "font_style": getattr(job, "font_style", "default"),
        "font": getattr(job, "font", None),
        "text_position": getattr(job, "text_position", "center"),
        "text_effect": getattr(job, "text_effect", "shadow"),
        "preset": getattr(job, "preset", "balanced"),
        "text_guide": getattr(job, "text_guide", "none"),
        "font_size": getattr(job, "font_size", None),
        "padding": getattr(job, "padding", 60),
        "opacity": getattr(job, "opacity", 1.0),
        "darken": getattr(job, "darken", 0.0),
        "text_color": getattr(job, "text_color", "255,255,255"),
        "line_spacing": getattr(job, "line_spacing", 1.4),
        "max_lines": getattr(job, "max_lines", None),
        "random_font": bool(getattr(job, "random_font", False)),
        "use_case": getattr(job, "use_case", "arabic_poster"),
        "brand_kit": getattr(job, "brand_kit", None),
        "validate_output": bool(getattr(job, "validate_output", False)),
        "no_manifest": bool(getattr(job, "no_manifest", False)),
        "json": False,
    }
    if payload["harmonize"] is None:
        payload["harmonize"] = 0.35
    return Namespace(**payload)


def run_arabic_text_composite_job(
    *,
    job: Any,
    base_args: Any,
    model: dict,
    prompt: str,
    negative: str,
    width: int,
    height: int,
    seed: int,
    stream_sink=None,
    job_id: str | None = None,
) -> dict:
    from dreamforge_generation import emit_event
    from dreamforge_errors import invalid_input_image

    arabic_text = resolve_arabic_text(job)
    if not arabic_text:
        err = invalid_input_image(
            "Arabic text composite requires arabic_text (or Arabic text in the prompt)",
            job_id=job_id,
        )
        emit_event(stream_sink, err)
        return {"status": "error", **err}

    if stream_sink is not None:
        emit_event(
            stream_sink,
            {
                "type": "progress",
                "job_id": job_id,
                "phase": "sampling",
                "progress": 0,
                "message": "Running Arabic poster pipeline (scene → composite → harmonize)…",
            },
        )

    pipeline_args = _pipeline_args(
        job=job,
        base_args=base_args,
        model=model,
        prompt=prompt,
        negative=negative,
        width=width,
        height=height,
        seed=seed,
    )

    prev_flag = os.environ.get("DREAMFORGE_IN_ARABIC_PIPELINE")
    os.environ["DREAMFORGE_IN_ARABIC_PIPELINE"] = "1"
    try:
        from arabic_poster_pipeline import run_full_pipeline

        final_paths = run_full_pipeline(pipeline_args)
    except SystemExit as exc:
        code = int(exc.code) if isinstance(exc.code, int) else 1
        err = {
            "type": "error",
            "code": "arabic_pipeline_failed",
            "message": f"Arabic poster pipeline failed (exit {code})",
            "job_id": job_id,
            "recoverable": True,
        }
        emit_event(stream_sink, err)
        return {"status": "error", **err}
    except Exception as exc:
        err = {
            "type": "error",
            "code": "arabic_pipeline_failed",
            "message": str(exc),
            "job_id": job_id,
            "recoverable": True,
        }
        emit_event(stream_sink, err)
        return {"status": "error", **err}
    finally:
        if prev_flag is None:
            os.environ.pop("DREAMFORGE_IN_ARABIC_PIPELINE", None)
        else:
            os.environ["DREAMFORGE_IN_ARABIC_PIPELINE"] = prev_flag

    if not final_paths:
        err = {
            "type": "error",
            "code": "arabic_pipeline_failed",
            "message": "Arabic poster pipeline produced no images",
            "job_id": job_id,
            "recoverable": True,
        }
        emit_event(stream_sink, err)
        return {"status": "error", **err}

    if stream_sink is not None:
        emit_event(
            stream_sink,
            {
                "type": "results",
                "job_id": job_id,
                "paths": list(final_paths),
            },
        )

    return {
        "status": "success",
        "images": [{"path": path} for path in final_paths],
        "output_paths": list(final_paths),
        "seed": seed,
        "model": model,
        "routing": {"workflow_mode": "arabic_text_composite", "arabic_text": arabic_text},
    }
