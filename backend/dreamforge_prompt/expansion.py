"""Flufferizer / Fooocus prompt-expansion model path and download helpers."""

from __future__ import annotations

from pathlib import Path

from _paths import BACKEND_ROOT

EXPANSION_WEIGHT_NAMES = ("pytorch_model.bin", "model.safetensors")
EXPANSION_DOWNLOAD_URL = (
    "https://huggingface.co/lllyasviel/misc/resolve/main/dreamforge_expansion.bin"
)


def resolve_prompt_expansion_dir() -> Path | None:
    """Return the first prompt-expansion folder that has tokenizer + weights."""
    candidates: list[Path] = []

    try:
        from shared import path_manager

        configured = path_manager.paths.get("path_dreamforge_expansion")
        if configured:
            candidates.append(Path(configured))
    except Exception:
        pass

    candidates.append(BACKEND_ROOT / "prompt_expansion")

    for candidate in candidates:
        if not candidate.is_dir():
            continue
        if not (candidate / "config.json").exists():
            continue
        if any((candidate / name).exists() for name in EXPANSION_WEIGHT_NAMES):
            return candidate
    return None


def prompt_expansion_available() -> bool:
    return resolve_prompt_expansion_dir() is not None


def ensure_prompt_expansion_model(*, download: bool = True) -> Path | None:
    """Ensure Flufferizer weights exist; optionally download Fooocus expansion bin."""
    existing = resolve_prompt_expansion_dir()
    if existing:
        return existing

    target_dir = BACKEND_ROOT / "prompt_expansion"
    target_dir.mkdir(parents=True, exist_ok=True)
    if not download:
        return None

    try:
        from modules.util import load_file_from_url

        load_file_from_url(
            url=EXPANSION_DOWNLOAD_URL,
            model_dir=str(target_dir),
            file_name="pytorch_model.bin",
        )
    except Exception as exc:
        print(f"[dreamforge_prompt] Prompt expansion download failed: {exc}")
        return None

    return resolve_prompt_expansion_dir()


def configure_prompt_expansion_path() -> Path | None:
    """Point ``modules.prompt_expansion`` at the resolved expansion directory."""
    expansion_dir = resolve_prompt_expansion_dir()
    if not expansion_dir:
        return None

    import modules.prompt_expansion as prompt_expansion

    path_str = str(expansion_dir)
    prompt_expansion.dreamforge_expansion_path = path_str
    prompt_expansion.DreamForgeExpansion.tokenizer = None
    prompt_expansion.DreamForgeExpansion.model = None
    return expansion_dir
