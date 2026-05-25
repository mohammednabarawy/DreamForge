"""Plan and apply automatic organization of DreamForge model files.

Walks ``<models_root>``, runs every weight file through
:mod:`backend.modules.model_classifier`, and produces a deterministic plan that
moves each misplaced file into its canonical ComfyUI subfolder.

The default behaviour is **dry-run** – nothing is moved until callers pass
``apply=True``.  Low-confidence verdicts and ambiguous cases are surfaced in
``plan.ambiguous`` so the UI can ask the user before touching the file.

Layout we converge on::

    models/
      checkpoints/        full SD / SDXL / SD3 / HiDream-O1
      diffusion_models/   Flux / Flux Kontext / Flux 2 / Qwen Image / HiDream I1 / Wan
      text_encoders/      CLIP-L, CLIP-G, T5-XXL, Qwen-2.5-VL, Mistral-3-Small, ...
      vae/                ae.safetensors, flux2-vae, qwen_image_vae, sdxl_vae, ...
      clip_vision/        CLIP-Vision encoders
      loras/              LoRAs (plus their .txt sidecars)
      controlnet/         ControlNet weights
      upscale_models/     ESRGAN / RealESRGAN / SwinIR / 4xUltrasharp
      embeddings/         textual-inversion
      inpaint/            full SD inpainting models

LEGACY aliases (``unet`` -> ``diffusion_models``, ``clip`` -> ``text_encoders``)
are still scanned for inventory but new files are placed in the canonical
folders above.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

try:  # absolute import path used everywhere else in backend/
    from modules.model_classifier import (
        ALL_TARGET_FOLDERS,
        LEGACY_ALIAS,
        PRESERVED_EXTENSION_FOLDERS,
        ROLE_TO_FOLDER,
        ModelClassification,
        classify_directory,
    )
except ImportError:  # support `python -m backend.modules.model_organizer`
    from .model_classifier import (  # type: ignore[no-redef]
        ALL_TARGET_FOLDERS,
        LEGACY_ALIAS,
        PRESERVED_EXTENSION_FOLDERS,
        ROLE_TO_FOLDER,
        ModelClassification,
        classify_directory,
    )

# Companion sidecars we keep next to LoRAs / checkpoints when we move them.
SIDECAR_EXTENSIONS = {".txt", ".json", ".yaml", ".yml", ".png", ".jpg", ".jpeg", ".webp"}


@dataclass
class OrganizerAction:
    """A single planned move."""

    source: Path
    destination: Path
    classification: ModelClassification
    sidecars: list[tuple[Path, Path]] = field(default_factory=list)
    skip_reason: str | None = None  # set when we decided not to move

    @property
    def will_move(self) -> bool:
        return self.skip_reason is None and self.source != self.destination

    def as_dict(self) -> dict:
        return {
            "source": str(self.source),
            "destination": str(self.destination),
            "will_move": self.will_move,
            "skip_reason": self.skip_reason,
            "sidecars": [
                {"source": str(src), "destination": str(dst)} for src, dst in self.sidecars
            ],
            "classification": self.classification.as_dict(),
        }


@dataclass
class OrganizerPlan:
    """All actions for one ``models_root`` scan."""

    models_root: Path
    actions: list[OrganizerAction] = field(default_factory=list)
    ambiguous: list[ModelClassification] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def to_move(self) -> list[OrganizerAction]:
        return [action for action in self.actions if action.will_move]

    @property
    def skipped(self) -> list[OrganizerAction]:
        return [action for action in self.actions if not action.will_move]

    def summary(self) -> dict:
        return {
            "total": len(self.actions),
            "to_move": len(self.to_move),
            "ambiguous": len(self.ambiguous),
            "skipped": len(self.skipped),
            "needs_review": sum(1 for action in self.actions if action.classification.needs_review),
        }

    def as_dict(self) -> dict:
        return {
            "models_root": str(self.models_root),
            "summary": self.summary(),
            "actions": [action.as_dict() for action in self.actions],
            "ambiguous": [classification.as_dict() for classification in self.ambiguous],
            "errors": list(self.errors),
        }


# --------------------------------------------------------------------------- #
# Planning
# --------------------------------------------------------------------------- #

def _collect_sidecars(source: Path) -> list[Path]:
    """Return files that should travel with ``source`` (same stem, sidecar ext)."""
    out: list[Path] = []
    stem = source.stem
    for sibling in source.parent.iterdir():
        if not sibling.is_file() or sibling == source:
            continue
        if sibling.suffix.lower() in SIDECAR_EXTENSIONS and sibling.stem == stem:
            out.append(sibling)
    return out


def _unique_destination(target: Path) -> Path:
    """Return ``target`` if free; otherwise append ``-1``, ``-2``, ..."""
    if not target.exists():
        return target
    stem = target.stem
    suffix = target.suffix
    parent = target.parent
    for index in range(1, 1000):
        candidate = parent / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find a unique destination for {target}")


def build_plan(
    models_root: Path,
    *,
    include_low_confidence: bool = False,
) -> OrganizerPlan:
    """Inspect every weight file and propose canonical placements."""
    models_root = Path(models_root)
    plan = OrganizerPlan(models_root=models_root)
    if not models_root.is_dir():
        plan.errors.append(f"models_root does not exist: {models_root}")
        return plan

    classifications = classify_directory(models_root)

    for classification in classifications:
        source = classification.path

        try:
            relative_from_current = source.relative_to(models_root)
        except ValueError:
            plan.errors.append(f"file outside models_root: {source}")
            continue

        first_part = relative_from_current.parts[0] if relative_from_current.parts else ""
        nested = (
            Path(*relative_from_current.parts[1:])
            if len(relative_from_current.parts) > 1
            else Path(source.name)
        )

        # 1. Preserved ComfyUI extension folders (ipadapter/, gligen/, sams/,
        #    hypernetworks/, photomaker/, CatVTON/, ...): never move OUT.
        if first_part in PRESERVED_EXTENSION_FOLDERS:
            plan.actions.append(OrganizerAction(
                source=source,
                destination=source,
                classification=classification,
                skip_reason=f"preserved_extension_folder:{first_part}",
            ))
            continue

        # 2. Diffusers cache layouts (``.../unet/diffusion_pytorch_model.safetensors``,
        #    ``.../sd-vae-ft-mse/diffusion_pytorch_model.safetensors``) live in
        #    snapshot directories that ride alongside config JSONs.  We leave
        #    them alone – moving one weight file breaks the snapshot.
        if (
            source.name == "diffusion_pytorch_model.safetensors"
            and len(relative_from_current.parts) >= 3
        ):
            plan.actions.append(OrganizerAction(
                source=source,
                destination=source,
                classification=classification,
                skip_reason="diffusers_snapshot_layout",
            ))
            continue

        if not classification.target_dir:
            plan.ambiguous.append(classification)
            continue

        # 3. Files already in their canonical folder: nothing to do.
        if first_part == classification.target_dir:
            plan.actions.append(OrganizerAction(
                source=source,
                destination=source,
                classification=classification,
                skip_reason="already_in_canonical_folder",
            ))
            continue

        destination_folder = models_root / classification.target_dir

        in_legacy_alias = LEGACY_ALIAS.get(first_part) == classification.target_dir
        in_other_canonical_root = first_part in ROLE_TO_FOLDER.values()

        # Conservative rule for files that already live in a canonical folder:
        # require BOTH a tensor-derived role AND a known family before we
        # relocate them.  This protects ComfyUI helper files (MAT_Places, fooocus
        # inpaint heads, custom upscalers, long-clip variants...) that share
        # tensor signatures with their cousins but live in deliberately chosen
        # locations.
        strong_signal = (
            classification.role_from_header
            and classification.family != "unknown"
        )
        if in_legacy_alias:
            destination = destination_folder / nested
        elif in_other_canonical_root:
            if not strong_signal:
                plan.actions.append(OrganizerAction(
                    source=source,
                    destination=source,
                    classification=classification,
                    skip_reason=(
                        f"respect_existing_placement:{first_part} "
                        f"(confidence={classification.confidence}, "
                        f"role_from_header={classification.role_from_header})"
                    ),
                ))
                continue
            destination = destination_folder / source.name
        else:
            if classification.confidence == "low" and not include_low_confidence:
                plan.ambiguous.append(classification)
                continue
            destination = destination_folder / source.name

        destination = _unique_destination(destination)
        sidecars = [
            (sidecar, _unique_destination(destination.parent / sidecar.name))
            for sidecar in _collect_sidecars(source)
        ]

        plan.actions.append(OrganizerAction(
            source=source,
            destination=destination,
            classification=classification,
            sidecars=sidecars,
        ))

    return plan


# --------------------------------------------------------------------------- #
# Apply
# --------------------------------------------------------------------------- #

def _move_one(source: Path, destination: Path) -> tuple[bool, str | None]:
    """Move ``source`` to ``destination``. Returns ``(success, error_message)``."""
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Prefer atomic rename inside the same filesystem; fall back to copy+remove.
        try:
            source.replace(destination)
        except OSError:
            shutil.copy2(source, destination)
            source.unlink(missing_ok=True)
        return True, None
    except OSError as exc:
        return False, str(exc)


def apply_plan(plan: OrganizerPlan) -> dict:
    """Execute every ``will_move`` action in ``plan``.

    Returns a dict with ``moved``, ``failed`` and ``skipped`` lists.  The plan
    itself is not mutated – callers can show the diff between before/after.
    """
    moved: list[dict] = []
    failed: list[dict] = []
    skipped: list[dict] = []

    for action in plan.actions:
        if not action.will_move:
            skipped.append({"source": str(action.source), "reason": action.skip_reason})
            continue

        success, error = _move_one(action.source, action.destination)
        if not success:
            failed.append({
                "source": str(action.source),
                "destination": str(action.destination),
                "error": error,
            })
            continue

        moved_entry = {
            "source": str(action.source),
            "destination": str(action.destination),
            "sidecars": [],
        }

        for sidecar_src, sidecar_dst in action.sidecars:
            ok, err = _move_one(sidecar_src, sidecar_dst)
            moved_entry["sidecars"].append({
                "source": str(sidecar_src),
                "destination": str(sidecar_dst),
                "moved": ok,
                "error": err,
            })

        moved.append(moved_entry)

    return {"moved": moved, "failed": failed, "skipped": skipped}


# --------------------------------------------------------------------------- #
# High-level helper used by CLI / desktop bridge
# --------------------------------------------------------------------------- #

def organize_models(
    models_root: Path,
    *,
    apply: bool = False,
    include_low_confidence: bool = False,
) -> dict:
    """Plan (and optionally apply) the organization of ``models_root``."""
    plan = build_plan(models_root, include_low_confidence=include_low_confidence)
    payload = plan.as_dict()
    payload["applied"] = False
    if apply and plan.to_move:
        result = apply_plan(plan)
        payload["applied"] = True
        payload["result"] = result
    return payload
