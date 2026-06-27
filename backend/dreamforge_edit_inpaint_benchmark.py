"""Edit/inpaint benchmark manifest loader and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BENCHMARK_ROOT = Path(__file__).resolve().parent / "benchmarks" / "edit_inpaint"
SCHEMA_VERSION = "1.0"
REQUIRED_FIELDS = ("schema_version", "id", "mode", "source_image", "prompt")
VALID_MODES = {"edit", "inpaint", "outpaint"}


def benchmark_cases_dir(root: Path | None = None) -> Path:
    return (root or BENCHMARK_ROOT) / "cases"


def load_benchmark_manifest(path: Path | str) -> dict[str, Any]:
    manifest_path = Path(path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Benchmark manifest must be an object: {manifest_path}")
    return data


def validate_benchmark_manifest(
    data: dict[str, Any],
    *,
    root: Path | None = None,
) -> list[str]:
    """Return validation errors; empty list means valid."""
    errors: list[str] = []
    if str(data.get("schema_version") or "") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    for field in REQUIRED_FIELDS:
        if not str(data.get(field) or "").strip():
            errors.append(f"missing required field: {field}")
    mode = str(data.get("mode") or "").strip().lower()
    if mode and mode not in VALID_MODES:
        errors.append(f"unsupported mode: {mode}")
    if mode == "inpaint" and not str(data.get("mask_image") or "").strip():
        errors.append("inpaint cases require mask_image")
    base = root or BENCHMARK_ROOT
    for key in ("source_image", "mask_image"):
        rel = str(data.get(key) or "").strip()
        if not rel:
            continue
        if not (base / rel).exists():
            errors.append(f"missing asset file: {rel}")
    expectations = data.get("expectations")
    if isinstance(expectations, dict):
        ratio = expectations.get("max_outside_mask_leakage_ratio")
        if ratio is not None:
            try:
                value = float(ratio)
                if value < 0 or value > 1:
                    errors.append("max_outside_mask_leakage_ratio must be between 0 and 1")
            except (TypeError, ValueError):
                errors.append("max_outside_mask_leakage_ratio must be numeric")
    return errors


def list_benchmark_manifests(root: Path | None = None) -> list[Path]:
    cases = benchmark_cases_dir(root)
    if not cases.is_dir():
        return []
    return sorted(cases.glob("*.json"))


def load_validated_benchmark(path: Path | str, *, root: Path | None = None) -> dict[str, Any]:
    data = load_benchmark_manifest(path)
    errors = validate_benchmark_manifest(data, root=root)
    if errors:
        joined = "; ".join(errors)
        raise ValueError(f"Invalid benchmark manifest {path}: {joined}")
    return data


def measure_benchmark_output_leakage(
    manifest: dict[str, Any],
    output_image: Path | str,
    *,
    root: Path | None = None,
    tolerance: int = 3,
    edge_band: int = 2,
) -> dict[str, Any]:
    """Measure outside-mask leakage for an inpaint benchmark output."""
    if str(manifest.get("mode") or "").lower() != "inpaint":
        raise ValueError("Outside-mask leakage is defined for inpaint benchmarks only")
    source_rel = str(manifest.get("source_image") or "").strip()
    mask_rel = str(manifest.get("mask_image") or "").strip()
    if not source_rel or not mask_rel:
        raise ValueError("Inpaint benchmark requires source_image and mask_image")

    from PIL import Image

    from dreamforge_krita_resources import measure_inpaint_outside_mask_leakage

    base = root or BENCHMARK_ROOT
    source = Image.open(base / source_rel).convert("RGB")
    mask = Image.open(base / mask_rel).convert("L")
    generated = Image.open(output_image).convert("RGB")
    report = measure_inpaint_outside_mask_leakage(
        source,
        generated,
        mask,
        tolerance=tolerance,
        edge_band=edge_band,
    )
    expectations = manifest.get("expectations")
    max_ratio = None
    if isinstance(expectations, dict):
        raw_ratio = expectations.get("max_outside_mask_leakage_ratio")
        if raw_ratio is not None:
            max_ratio = float(raw_ratio)
            report["ok"] = bool(report.get("ok")) or report["leakage_ratio"] <= max_ratio
            report["max_expected_leakage_ratio"] = max_ratio
    return report
