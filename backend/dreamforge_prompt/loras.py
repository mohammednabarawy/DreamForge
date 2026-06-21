"""Normalize and merge LoRA selections for the Comfy generation path."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class ComfyLoraSpec:
    name: str
    weight: float

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "weight": self.weight}


def _parse_cli_lora_item(item: str) -> ComfyLoraSpec | None:
    text = str(item or "").strip()
    if not text:
        return None
    if ":" in text:
        name, weight_text = text.rsplit(":", 1)
        try:
            weight = float(weight_text)
        except ValueError:
            weight = 1.0
        name = name.strip()
    else:
        name = text
        weight = 1.0
    if not name:
        return None
    return ComfyLoraSpec(name=_ensure_lora_filename(name), weight=weight)


def _parse_legacy_gallery_entry(entry: Any) -> ComfyLoraSpec | None:
    if isinstance(entry, dict):
        name = str(entry.get("name") or "").strip()
        if not name:
            return None
        try:
            weight = float(entry.get("weight", 1.0))
        except (TypeError, ValueError):
            weight = 1.0
        return ComfyLoraSpec(name=_ensure_lora_filename(name), weight=weight)

    if isinstance(entry, (list, tuple)) and len(entry) >= 2:
        payload = str(entry[1] or "").strip()
        if " - " in payload:
            weight_text, name = payload.split(" - ", 1)
            try:
                weight = float(weight_text)
            except ValueError:
                weight = 1.0
        else:
            name = payload
            weight = 1.0
        name = name.strip()
        if not name or name.lower() == "none":
            return None
        return ComfyLoraSpec(name=_ensure_lora_filename(name), weight=weight)
    return None


def _ensure_lora_filename(name: str) -> str:
    cleaned = name.strip().replace("\\", "/")
    if cleaned.lower().endswith((".safetensors", ".gguf", ".pt")):
        return Path(cleaned).name
    return f"{Path(cleaned).name}.safetensors"


def resolve_lora_on_disk(name: str) -> str | None:
    """Resolve a LoRA filename against ``models/loras`` (case-insensitive)."""
    filename = _ensure_lora_filename(name)
    try:
        from dreamforge_paths import MODELS_ROOT

        lora_dir = MODELS_ROOT / "loras"
        if not lora_dir.is_dir():
            return filename
        wanted = filename.lower()
        for path in lora_dir.iterdir():
            if path.suffix.lower() not in (".safetensors", ".gguf", ".pt"):
                continue
            if path.name.lower() == wanted:
                return path.name
        stem = Path(filename).stem.lower()
        for path in lora_dir.iterdir():
            if path.suffix.lower() not in (".safetensors", ".gguf", ".pt"):
                continue
            if path.stem.lower() == stem:
                return path.name
    except Exception:
        return filename
    return filename


def normalize_lora_entries(entries: Iterable[Any] | None) -> list[ComfyLoraSpec]:
    specs: list[ComfyLoraSpec] = []
    for entry in entries or []:
        if isinstance(entry, str):
            spec = _parse_cli_lora_item(entry)
        else:
            spec = _parse_legacy_gallery_entry(entry)
        if spec:
            specs.append(spec)
    return specs


def merge_generation_loras(job, parsed_from_prompt: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Merge explicit job LoRAs with ``<lora:name:weight>`` tags (RuinedFooocus order)."""
    merged: dict[str, ComfyLoraSpec] = {}

    for spec in normalize_lora_entries(getattr(job, "lora", None) or []):
        resolved = resolve_lora_on_disk(spec.name)
        if resolved:
            merged[resolved.lower()] = ComfyLoraSpec(resolved, spec.weight)

    for raw in parsed_from_prompt or []:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        if not name:
            continue
        try:
            weight = float(raw.get("weight", 1.0))
        except (TypeError, ValueError):
            weight = 1.0
        resolved = resolve_lora_on_disk(name)
        if resolved:
            merged[resolved.lower()] = ComfyLoraSpec(resolved, weight)

    return [spec.as_dict() for spec in merged.values()]
