from dreamforge_assets import (
    AssetFile,
    AssetVersion,
    DreamForgeAsset,
    Provenance,
)
from dreamforge_compute_profile import (
    ARCHITECTURE_VRAM_MB,
    ComputeProfile,
    VramEstimator,
    detect_compute_profile_static,
    estimate_asset_fit,
    recommend_file_for_asset,
    recommend_file_variants_from_dict,
)


def test_compute_profile_static_detects_auto_profile():
    profile = detect_compute_profile_static(vram_mb=24576, backend="cuda", vram_profile="auto")
    assert profile.vram_mb == 24576
    assert profile.backend == "cuda"
    assert profile.has_gpu is True
    assert profile.vram_gb == 24.0
    assert profile.recommended_profile == "16gb"


def test_compute_profile_static_tiers():
    assert detect_compute_profile_static(vram_mb=8192).recommended_profile == "8gb"
    assert detect_compute_profile_static(vram_mb=4096).recommended_profile == "5gb"
    assert detect_compute_profile_static(vram_mb=0).has_gpu is False
    assert detect_compute_profile_static(vram_mb=0).recommended_profile == "no_gpu"


def test_compute_profile_can_fit_respects_profile_budget():
    profile_8gb = detect_compute_profile_static(vram_mb=8192, vram_profile="8gb")
    assert profile_8gb.can_fit(8192) is True
    assert profile_8gb.can_fit(8193) is False
    # Explicit profile caps the budget even if more VRAM is present.
    profile_8gb_on_24gb = detect_compute_profile_static(vram_mb=24576, vram_profile="8gb")
    assert profile_8gb_on_24gb.can_fit(10000) is False
    assert detect_compute_profile_static(vram_mb=0).can_fit(1) is False


def test_compute_profile_round_trip():
    profile = detect_compute_profile_static(vram_mb=16384, vram_profile="16gb")
    restored = ComputeProfile.from_dict(profile.to_dict())
    assert restored == profile
    assert restored.vram_mb == 16384
    assert restored.vram_profile == "16gb"


def test_vram_estimator_architecture_and_variant():
    estimator = VramEstimator()
    base = estimator.estimate_for_architecture("flux")
    assert base["estimated_mb"] == ARCHITECTURE_VRAM_MB["flux"]
    fp8 = estimator.estimate_for_architecture("flux", variant="fp8", detail=True)
    assert fp8["reduction"] == 0.75
    assert fp8["estimated_mb"] == int(ARCHITECTURE_VRAM_MB["flux"] * 0.75)
    q4 = estimator.estimate_for_architecture("flux", variant="q4_k_m")
    assert q4["estimated_mb"] == int(ARCHITECTURE_VRAM_MB["flux"] * 0.55)
    unknown = estimator.estimate_for_architecture("totally_new", detail=True)
    assert unknown["estimated_mb"] == 0
    assert unknown["base_mb"] == 0


def test_vram_estimator_keeps_weights_constant_and_adds_workflow_overhead():
    estimator = VramEstimator()
    baseline = estimator.estimate_for_architecture("flux", width=512, height=512, detail=True)
    large = estimator.estimate_for_architecture("flux", width=2048, height=2048, detail=True, batch=2, vae_mb=1024)
    assert large["model_mb"] == int(ARCHITECTURE_VRAM_MB["flux"] * 0.8)
    assert large["estimated_mb"] > baseline["estimated_mb"]
    unknown = estimator.estimate_for_architecture("future_arch", detail=True, workflow_overhead_mb=900)
    assert unknown["estimated_mb"] == 900
    assert unknown["unknown_architecture"] is True


def _asset(architecture, variant="", local_path=""):
    return DreamForgeAsset(
        id="civitai:1",
        architecture=architecture,
        versions=[
            AssetVersion(
                id="v1",
                files=[
                    AssetFile(
                        filename="model.safetensors",
                        sha256="a" * 64,
                        variant=variant,
                        local_path=local_path,
                    )
                ],
            )
        ],
        provenance=Provenance(provider="civitai", provider_asset_id="1"),
    )


def test_estimate_asset_fit_recommends_within_budget():
    profile = detect_compute_profile_static(vram_mb=16384, vram_profile="16gb")
    result = estimate_asset_fit(_asset("sdxl"), profile)
    assert result["fits"] is True
    assert result["label"] == "Recommended"
    assert result["estimated_mb"] == ARCHITECTURE_VRAM_MB["sdxl"]


def test_estimate_asset_fit_warns_above_budget():
    profile = detect_compute_profile_static(vram_mb=4096, vram_profile="5gb")
    result = estimate_asset_fit(_asset("flux"), profile)
    assert result["fits"] is False
    assert result["label"].startswith("May exceed")


def test_estimate_asset_fit_uses_asset_variant():
    profile = detect_compute_profile_static(vram_mb=4096, vram_profile="5gb")
    # fp8 flux estimate (~9216MB) still exceeds 5gb, variant alone is not enough.
    result = estimate_asset_fit(_asset("flux", variant="fp8"), profile)
    assert result["fits"] is False


def _multi_variant_asset(architecture="flux"):
    """A flux asset with fp16/fp8/gguf variants for recommendation tests."""
    return DreamForgeAsset(
        id="civitai:9",
        architecture=architecture,
        versions=[
            AssetVersion(
                id="v1",
                files=[
                    AssetFile(
                        filename="flux_fp16.safetensors",
                        sha256="f" * 64,
                        variant="fp16",
                        format="safetensors",
                        size_bytes=23 * 1024**3,
                    ),
                    AssetFile(
                        filename="flux_fp8.safetensors",
                        sha256="e" * 64,
                        variant="fp8",
                        format="safetensors",
                        size_bytes=12 * 1024**3,
                    ),
                    AssetFile(
                        filename="flux_q4.gguf",
                        sha256="d" * 64,
                        variant="q4_k_m",
                        format="gguf",
                        size_bytes=6 * 1024**3,
                    ),
                ],
            )
        ],
        provenance=Provenance(provider="civitai", provider_asset_id="9"),
    )


def test_recommend_file_prefers_highest_quality_that_fits():
    # 24GB profile fits even fp16 flux (~12GB) -> recommend fp16.
    profile = detect_compute_profile_static(vram_mb=24576, vram_profile="auto")
    result = recommend_file_for_asset(_multi_variant_asset(), profile)
    assert result["recommended"]["variant"] == "fp16"
    assert result["recommended"]["fits"] is True
    assert len(result["files"]) == 3


def test_recommend_file_falls_back_to_quantized_on_small_vram():
    # 8GB profile: fp16 (~12GB) and fp8 (~9GB) don't fit, q4 (~6.7GB) does.
    profile = detect_compute_profile_static(vram_mb=8192, vram_profile="8gb")
    result = recommend_file_for_asset(_multi_variant_asset(), profile)
    assert result["recommended"]["variant"] == "q4_k_m"
    assert result["recommended"]["fits"] is True


def test_recommend_file_closest_to_fitting_when_nothing_fits():
    profile = detect_compute_profile_static(vram_mb=4096, vram_profile="5gb")
    result = recommend_file_for_asset(_multi_variant_asset(), profile)
    # Nothing fits on 5GB; the smallest (q4_k_m ~6.7GB) is "closest".
    assert result["recommended"]["variant"] == "q4_k_m"
    assert result["recommended"]["fits"] is False


def test_recommend_file_unknown_architecture_is_unverifiable():
    profile = detect_compute_profile_static(vram_mb=16384, vram_profile="16gb")
    result = recommend_file_for_asset(
        _multi_variant_asset(architecture="brand_new_arch"), profile
    )
    # No estimate -> fits is None (unverifiable), still picks a known-SHA file.
    assert result["recommended"]["fits"] is None
    assert result["recommended"]["sha256"]


def test_recommend_file_prefers_known_sha256():
    profile = detect_compute_profile_static(vram_mb=24576, vram_profile="auto")
    # First (fp16, highest quality) file has no SHA -> a later known-SHA file wins.
    asset = DreamForgeAsset(
        id="civitai:9",
        architecture="flux",
        versions=[
            AssetVersion(
                id="v1",
                files=[
                    AssetFile(
                        filename="flux_fp16.safetensors",
                        variant="fp16",
                        format="safetensors",
                    ),
                    AssetFile(
                        filename="flux_fp8.safetensors",
                        sha256="e" * 64,
                        variant="fp8",
                        format="safetensors",
                    ),
                ],
            )
        ],
        provenance=Provenance(provider="civitai", provider_asset_id="9"),
    )
    result = recommend_file_for_asset(asset, profile)
    assert result["recommended"]["sha256"]


def test_recommend_file_variants_from_dict_bridge_surface():
    profile = detect_compute_profile_static(vram_mb=24576, vram_profile="auto")
    asset = _multi_variant_asset()
    result = recommend_file_variants_from_dict(asset.to_dict(), profile=profile)
    assert result["ok"] is True
    assert result["recommended"]["variant"] == "fp16"
    assert "profile" in result

    missing = recommend_file_variants_from_dict(None, profile=profile)
    assert missing["ok"] is False
    assert missing.get("error") == "missing_asset"
