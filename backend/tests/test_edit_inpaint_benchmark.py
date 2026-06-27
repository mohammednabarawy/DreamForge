from pathlib import Path

import pytest

from dreamforge_edit_inpaint_benchmark import (
    BENCHMARK_ROOT,
    load_benchmark_manifest,
    measure_benchmark_output_leakage,
    validate_benchmark_manifest,
)


def test_validate_benchmark_manifest_accepts_example_shape():
    manifest = {
        "schema_version": "1.0",
        "id": "demo",
        "mode": "inpaint",
        "source_image": "assets/source/portrait_1024.svg",
        "mask_image": "assets/masks/portrait_face_soft.svg",
        "prompt": "repair eyes",
    }
    errors = validate_benchmark_manifest(manifest, root=BENCHMARK_ROOT)
    assert errors == []


def test_validate_benchmark_manifest_rejects_inpaint_without_mask():
    manifest = {
        "schema_version": "1.0",
        "id": "demo",
        "mode": "inpaint",
        "source_image": "assets/source/portrait_1024.svg",
        "prompt": "repair eyes",
    }
    errors = validate_benchmark_manifest(manifest, root=BENCHMARK_ROOT)
    assert "inpaint cases require mask_image" in errors


def test_example_manifest_file_parses():
    example = BENCHMARK_ROOT / "cases" / "repair_detail.example.json"
    if not example.is_file():
        pytest.skip("example benchmark manifest not present")
    data = load_benchmark_manifest(example)
    assert data["task"] == "repair"


def test_example_manifest_assets_exist_and_validate():
    example = BENCHMARK_ROOT / "cases" / "repair_detail.example.json"
    data = load_benchmark_manifest(example)
    assert validate_benchmark_manifest(data, root=BENCHMARK_ROOT) == []


def test_measure_benchmark_output_leakage(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    root = tmp_path
    (root / "assets" / "source").mkdir(parents=True)
    (root / "assets" / "masks").mkdir(parents=True)
    source = Image.new("RGB", (64, 64), color=(10, 20, 30))
    mask = Image.new("L", (64, 64), color=0)
    for x in range(24, 40):
        for y in range(24, 40):
            mask.putpixel((x, y), 255)
    generated = source.copy()
    for x in range(24, 40):
        for y in range(24, 40):
            generated.putpixel((x, y), (200, 200, 200))
    source.save(root / "assets" / "source" / "source.png")
    mask.save(root / "assets" / "masks" / "mask.png")
    output = root / "output.png"
    generated.save(output)
    manifest = {
        "schema_version": "1.0",
        "id": "demo",
        "mode": "inpaint",
        "source_image": "assets/source/source.png",
        "mask_image": "assets/masks/mask.png",
        "prompt": "repair center",
    }

    report = measure_benchmark_output_leakage(manifest, output, root=root)
    assert report["ok"] is True
    assert report["changed_pixels"] == 0
