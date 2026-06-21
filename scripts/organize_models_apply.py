"""Apply DreamForge model organization and remove known duplicates."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from dreamforge_cli_inventory import MODELS_ROOT  # noqa: E402
from modules.model_organizer import build_plan, apply_plan  # noqa: E402


def _sha256_prefix(path: Path, nbytes: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        h.update(fh.read(nbytes))
    h.update(str(path.stat().st_size).encode())
    return h.hexdigest()


def _files_equivalent(a: Path, b: Path) -> bool:
    if not a.is_file() or not b.is_file():
        return False
    sa, sb = a.stat().st_size, b.stat().st_size
    if sa != sb:
        return False
    if sa < 50 * 1024 * 1024:
        return a.read_bytes() == b.read_bytes()
    return _sha256_prefix(a) == _sha256_prefix(b)


def remove_redundant_if_canonical_exists(redundant_rel: str, canonical_rel: str) -> str | None:
    redundant = MODELS_ROOT / redundant_rel
    canonical = MODELS_ROOT / canonical_rel
    if not redundant.is_file():
        return None
    if not canonical.is_file():
        return None
    if not _files_equivalent(redundant, canonical):
        print(f"  skip dedupe (different content): {redundant_rel}")
        return None
    redundant.unlink()
    print(f"  removed duplicate: {redundant_rel} (kept {canonical_rel})")
    return redundant_rel


def remove_stale_partials() -> list[str]:
    removed = []
    for path in MODELS_ROOT.rglob("*.part"):
        if path.is_file() and path.stat().st_size == 0:
            path.unlink()
            removed.append(str(path.relative_to(MODELS_ROOT)))
            print(f"  removed stale partial: {path.relative_to(MODELS_ROOT)}")
    return removed


def skip_moves_when_dest_exists(plan) -> int:
    """Delete sources when the canonical destination filename already exists."""
    skipped = 0
    for action in plan.actions:
        if action.skip_reason is not None or action.source == action.destination:
            continue
        canonical = action.destination.parent / action.source.name
        if not canonical.is_file():
            continue
        if _files_equivalent(action.source, canonical):
            action.source.unlink(missing_ok=True)
            action.skip_reason = "deduped_against_existing_destination"
            skipped += 1
            rel = action.source.relative_to(MODELS_ROOT)
            print(f"  removed duplicate (dest exists): {rel}")
    return skipped


def main() -> int:
    print(f"Models root: {MODELS_ROOT}")
    print("\n[1] Remove known duplicates and stale partials")
    remove_stale_partials()
    dedupe_pairs = [
        ("clip/clip_l.safetensors", "text_encoders/clip_l.safetensors"),
        ("diffusion_models/flux1-dev-fp8.safetensors", "checkpoints/flux1-dev-fp8.safetensors"),
        ("vae/flux_vae.safetensors", "vae/ae.safetensors"),
    ]
    for redundant, canonical in dedupe_pairs:
        remove_redundant_if_canonical_exists(redundant, canonical)

    print("\n[2] Build organization plan")
    plan = build_plan(MODELS_ROOT)
    deduped = skip_moves_when_dest_exists(plan)
    to_move = sum(1 for a in plan.actions if a.will_move)
    print(f"  planned moves: {to_move} (deduped {deduped} against existing targets)")

    if to_move:
        print("\n[3] Apply moves")
        for action in plan.actions:
            if action.will_move:
                rel_src = action.source.relative_to(MODELS_ROOT)
                rel_dst = action.destination.relative_to(MODELS_ROOT)
                print(f"  {rel_src} -> {rel_dst}")
        result = apply_plan(plan)
        print(f"  moved: {len(result['moved'])} failed: {len(result['failed'])}")
        if result["failed"]:
            for item in result["failed"]:
                print(f"    FAIL {item}")
            return 1
    else:
        print("\n[3] Nothing to move")

    print("\n[4] Post-clean duplicate -N suffix files")
    for path in sorted(MODELS_ROOT.rglob("*")):
        if not path.is_file():
            continue
        stem = path.stem
        if "-" not in stem or not stem.split("-")[-1].isdigit():
            continue
        base_stem = stem.rsplit("-", 1)[0]
        canonical = path.with_name(f"{base_stem}{path.suffix}")
        if canonical.is_file() and _files_equivalent(path, canonical):
            path.unlink()
            print(f"  removed duplicate suffix file: {path.relative_to(MODELS_ROOT)}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
