"""Batch automations for seed/prompt/input folders."""

from __future__ import annotations

import random
import uuid
from pathlib import Path
from typing import Any

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def _emit_automation_progress(
    stream_sink,
    *,
    automation_id: str,
    index: int,
    total: int,
    message: str,
    job_id: str | None = None,
) -> None:
    if stream_sink is None:
        return
    from dreamforge_generation import emit_event

    emit_event(
        stream_sink,
        {
            "type": "progress",
            "progress": int((index - 1) / total * 100),
            "phase": "running",
            "message": message,
            "job_id": job_id,
        },
    )


def _read_prompt_lines(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return [line.strip() for line in text.splitlines() if line.strip()]


def _list_prompt_files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.glob("*.txt") if p.is_file())


def _list_input_images(folder: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(folder.iterdir()):
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
            files.append(path)
    return files


def expand_automation_jobs(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Expand an automation spec into per-job override dicts."""
    automation_type = str(spec.get("type") or spec.get("automation_type") or "seed_batch").strip()
    base = dict(spec.get("base_settings") or spec.get("settings") or {})
    count = max(1, int(spec.get("count") or 4))
    template_id = spec.get("template_id")
    studio_mode = spec.get("studio_mode")

    jobs: list[dict[str, Any]] = []

    if automation_type == "seed_batch":
        for index in range(count):
            job = dict(base)
            job["seed"] = random.randint(0, 2**31 - 1)
            job["image_number"] = 1
            if template_id:
                job["template_id"] = template_id
            if studio_mode:
                job["studio_mode"] = studio_mode
            jobs.append({"index": index + 1, "overrides": job, "label": f"seed-{index + 1}"})

    elif automation_type == "prompt_lines":
        prompt_file = spec.get("prompt_file") or spec.get("input_path")
        if not prompt_file:
            return []
        lines = _read_prompt_lines(Path(str(prompt_file)))
        for index, line in enumerate(lines, start=1):
            job = dict(base)
            job["prompt"] = line
            job["image_number"] = 1
            if template_id:
                job["template_id"] = template_id
            jobs.append({"index": index, "overrides": job, "label": line[:48]})

    elif automation_type == "prompt_folder":
        folder = spec.get("prompt_folder") or spec.get("input_path")
        if not folder:
            return []
        index = 0
        for file_path in _list_prompt_files(Path(str(folder))):
            for line in _read_prompt_lines(file_path):
                index += 1
                job = dict(base)
                job["prompt"] = line
                job["image_number"] = 1
                if template_id:
                    job["template_id"] = template_id
                jobs.append(
                    {
                        "index": index,
                        "overrides": job,
                        "label": f"{file_path.name}:{index}",
                    }
                )

    elif automation_type == "input_folder":
        folder = spec.get("input_folder") or spec.get("input_path")
        if not folder:
            return []
        mode = str(studio_mode or base.get("studio_mode") or "upscale").lower()
        for index, image_path in enumerate(_list_input_images(Path(str(folder))), start=1):
            job = dict(base)
            job["image_number"] = 1
            if mode == "upscale":
                job["upscale_image"] = str(image_path)
                job["cn_type"] = "upscale"
                job["cn_selection"] = "Custom..."
            else:
                job["input_image"] = str(image_path)
            if template_id:
                job["template_id"] = template_id
            jobs.append(
                {
                    "index": index,
                    "overrides": job,
                    "label": image_path.name,
                    "source_image": str(image_path),
                }
            )
    else:
        return []

    return jobs


def preview_automation(spec: dict[str, Any]) -> dict[str, Any]:
    jobs = expand_automation_jobs(spec)
    return {
        "ok": True,
        "type": spec.get("type") or spec.get("automation_type"),
        "job_count": len(jobs),
        "jobs": [{"index": j.get("index"), "label": j.get("label")} for j in jobs[:50]],
    }


def run_automation(
    spec: dict[str, Any],
    *,
    base_args=None,
    stream_sink=None,
    cancel_check=None,
) -> dict:
    """Run automation jobs sequentially; export outputs when output_dir set."""
    from dreamforge_engine import DreamForgeEngine
    from dreamforge_pipeline_chain import first_image_path

    automation_id = str(spec.get("automation_id") or uuid.uuid4())
    jobs = expand_automation_jobs(spec)
    if not jobs:
        return {
            "status": "error",
            "code": "empty_automation",
            "message": "No automation jobs to run",
            "automation_id": automation_id,
        }

    output_dir = spec.get("output_dir")
    out_path = Path(str(output_dir)) if output_dir else None
    if out_path is not None:
        out_path.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    total = len(jobs)

    for job_spec in jobs:
        if cancel_check and cancel_check():
            return {
                "status": "cancelled",
                "automation_id": automation_id,
                "completed": len(results),
                "total": total,
                "results": results,
            }

        index = int(job_spec.get("index") or len(results) + 1)
        label = str(job_spec.get("label") or f"job-{index}")
        _emit_automation_progress(
            stream_sink,
            automation_id=automation_id,
            index=index,
            total=total,
            message=f"Automation {index}/{total}: {label}",
        )

        overrides = dict(job_spec.get("overrides") or {})
        overrides["automation_id"] = automation_id
        overrides["automation_index"] = index
        overrides["automation_total"] = total
        overrides["automation_type"] = spec.get("type") or spec.get("automation_type")
        if stream_sink is not None:
            overrides["stream_file"] = stream_sink

        result = DreamForgeEngine.execute_job(overrides, stream_sink=stream_sink)
        entry = {
            "index": index,
            "label": label,
            "status": result.get("status"),
            "images": result.get("images") or [],
            "manifest": result.get("manifest"),
        }
        if out_path and result.get("status") == "success":
            src = first_image_path(result)
            if src:
                dest = out_path / f"{index:04d}_{Path(label).stem}.png"
                try:
                    import shutil

                    shutil.copy2(src, dest)
                    entry["exported_path"] = str(dest)
                except OSError as exc:
                    entry["export_error"] = str(exc)
        results.append(entry)
        if result.get("status") != "success":
            return {
                "status": "error",
                "automation_id": automation_id,
                "failed_at": index,
                "error": result,
                "completed": len(results),
                "total": total,
                "results": results,
            }

    return {
        "status": "success",
        "automation_id": automation_id,
        "completed": len(results),
        "total": total,
        "results": results,
        "output_dir": str(out_path) if out_path else None,
    }
