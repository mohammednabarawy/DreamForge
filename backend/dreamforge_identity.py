"""Modern identity preservation: Kontext/Qwen primary, optional IP-Adapter FaceID."""

from __future__ import annotations

from typing import Any

VALID_IDENTITY_MODES = frozenset(
    {"preserve_face", "kontext", "qwen_edit", "ipadapter_faceid", "auto"}
)
LEGACY_IDENTITY_ALIASES = frozenset({"face", "faceid", "face_id", "preserve_face"})

KONTEXT_IDENTITY_STRENGTH = 0.92
QWEN_IDENTITY_STRENGTH = 1.0
FACEID_DEFAULT_WEIGHT = 0.75


def _inventory_model(category: str, hints: tuple[str, ...] = ()) -> str | None:
    try:
        from dreamforge_cli_inventory import list_model_inventory

        items = list_model_inventory().get("categories", {}).get(category, [])
        if hints:
            for item in items:
                text = " ".join(
                    str(item.get(key, "")) for key in ("name", "relative_path", "stem")
                ).lower()
                if any(h in text for h in hints):
                    return str(item.get("name") or item.get("relative_path") or "").replace(
                        "\\", "/"
                    )
        if items:
            item = items[0]
            return str(item.get("name") or item.get("relative_path") or "").replace("\\", "/")
    except Exception:
        return None
    return None


def normalize_identity_mode(value: Any) -> str | None:
    key = str(value or "").strip().lower()
    if key in VALID_IDENTITY_MODES:
        return key
    if key in LEGACY_IDENTITY_ALIASES:
        return "preserve_face"
    return None


def is_identity_preservation_job(job) -> bool:
    return bool(
        getattr(job, "preserve_character", False)
        or getattr(job, "face_preservation", False)
        or normalize_identity_mode(getattr(job, "identity_mode", None))
    )


def faceid_assets_available() -> dict[str, Any]:
    """Return whether real FaceID weights + insightface stack are on disk."""
    from dreamforge_workflow_planner import custom_node_pack_present

    missing: list[str] = []
    if not custom_node_pack_present("ComfyUI_IPAdapter_plus"):
        missing.append("ComfyUI_IPAdapter_plus")
    faceid_model = _inventory_model("ipadapter", ("faceid", "face-id", "face_id"))
    if not faceid_model:
        missing.append("ipadapter_faceid_model")
    insightface = _inventory_model("insightface")
    if not insightface:
        missing.append("insightface_model")
    return {
        "ok": not missing,
        "ipadapter_faceid_model": faceid_model,
        "insightface_model": insightface,
        "missing": missing,
    }


def _reference_path(job) -> str:
    return str(
        getattr(job, "input_image", None)
        or getattr(job, "reference_image", None)
        or ""
    ).strip()


def _pick_kontext_checkpoint() -> str | None:
    needles = (
        "flux1-dev-kontext_fp8_scaled",
        "flux1-dev-kontext",
        "kontext",
        "flux kontext",
    )
    try:
        from dreamforge_cli_inventory import list_model_inventory

        for item in list_model_inventory().get("categories", {}).get("diffusion_models", []):
            hay = " ".join(
                str(item.get(key, "")) for key in ("name", "relative_path", "stem", "family")
            ).lower()
            if any(n in hay for n in needles) and "fill" not in hay:
                return str(item.get("name") or item.get("relative_path") or "").replace("\\", "/")
    except Exception:
        return None
    return None


def _pick_qwen_edit_checkpoint() -> str | None:
    try:
        from dreamforge_cli_inventory import list_model_inventory, pick_best_qwen_edit_model

        gallery = list_model_inventory().get("gallery", [])
        if isinstance(gallery, list) and gallery:
            picked = pick_best_qwen_edit_model(gallery)
            return picked or None
        for item in list_model_inventory().get("categories", {}).get("diffusion_models", []):
            hay = " ".join(
                str(item.get(key, "")) for key in ("name", "relative_path", "stem", "family")
            ).lower()
            if "qwen" in hay and "edit" in hay:
                return str(item.get("name") or item.get("relative_path") or "").replace("\\", "/")
    except Exception:
        return None
    return None


def resolve_identity_route(job, *, model_family: str | None = None) -> dict[str, Any]:
    """Decide kontext / qwen_edit / ipadapter_faceid / img2img for identity jobs."""
    if not is_identity_preservation_job(job):
        return {"route": "none"}

    ref = _reference_path(job)
    if not ref:
        return {"route": "invalid", "reason": "reference image required for identity preservation"}

    mode = normalize_identity_mode(getattr(job, "identity_mode", None)) or "preserve_face"
    family = (model_family or "").lower()

    if mode == "ipadapter_faceid":
        assets = faceid_assets_available()
        if assets["ok"]:
            return {
                "route": "ipadapter_faceid",
                "reference_image": ref,
                **assets,
            }
        kontext = _pick_kontext_checkpoint()
        qwen = _pick_qwen_edit_checkpoint()
        fallback = "kontext" if kontext else ("qwen_edit" if qwen else "img2img")
        return {
            "route": fallback,
            "reference_image": ref,
            "model": kontext or qwen,
            "notice": "FaceID assets missing; using Kontext/Qwen identity instead.",
            "faceid_missing": assets["missing"],
        }

    if mode in {"kontext", "preserve_face", "auto"}:
        kontext = _pick_kontext_checkpoint()
        if kontext and mode != "qwen_edit":
            return {
                "route": "kontext",
                "reference_image": ref,
                "model": kontext,
            }

    if mode in {"qwen_edit", "preserve_face", "auto"}:
        qwen = _pick_qwen_edit_checkpoint()
        if qwen:
            return {
                "route": "qwen_edit",
                "reference_image": ref,
                "model": qwen,
            }

    if family == "flux_kontext":
        return {"route": "kontext", "reference_image": ref}
    if family == "qwen_image_edit":
        return {"route": "qwen_edit", "reference_image": ref}

    return {"route": "img2img", "reference_image": ref}


def _kontext_patch(ref: str, model: str | None = None) -> dict[str, Any]:
    patch: dict[str, Any] = {
        "reference_role": "restyle",
        "workflow_mode": "generate",
        "input_image": ref,
        "reference_image": ref,
        "preserve_character": True,
        "face_preservation": True,
        "identity_mode": "preserve_face",
        "edit_type": "kontext",
        "edit_strength": KONTEXT_IDENTITY_STRENGTH,
        "cn_selection": "None",
        "cn_type": "None",
        "steps": 20,
    }
    if model:
        patch["model"] = model
    return patch


def _qwen_edit_patch(ref: str, model: str | None = None) -> dict[str, Any]:
    patch: dict[str, Any] = {
        "reference_role": "restyle",
        "workflow_mode": "generate",
        "input_image": ref,
        "reference_image": ref,
        "preserve_character": True,
        "face_preservation": True,
        "identity_mode": "preserve_face",
        "edit_type": "qwen_edit",
        "edit_strength": QWEN_IDENTITY_STRENGTH,
        "cn_selection": "None",
        "cn_type": "None",
    }
    if model:
        patch["model"] = model
    return patch


def _faceid_patch(ref: str, assets: dict[str, Any]) -> dict[str, Any]:
    return {
        "reference_role": "image_prompt",
        "workflow_mode": "ipadapter_faceid",
        "reference_image": ref,
        "input_image": None,
        "preserve_character": True,
        "face_preservation": True,
        "identity_mode": "ipadapter_faceid",
        "edit_type": "auto",
        "cn_selection": "None",
        "cn_type": "None",
        "ipadapter_model": assets.get("ipadapter_faceid_model"),
        "ipadapter_weight": FACEID_DEFAULT_WEIGHT,
    }


def apply_identity_to_job(job) -> dict[str, Any]:
    """Route identity-preservation jobs to Kontext/Qwen or gated FaceID."""
    if getattr(job, "vary_amount", None):
        return {}
    if str(getattr(job, "enhance_auto_fix", False)).lower() in {"1", "true"} or getattr(
        job, "enhance_target", None
    ):
        return {}

    plan = resolve_identity_route(
        job,
        model_family=str(getattr(job, "model_family", None) or ""),
    )
    if plan.get("route") == "none":
        return {}
    if plan.get("route") == "invalid":
        return {"identity_error": plan.get("reason")}

    route = plan["route"]
    ref = plan["reference_image"]
    out: dict[str, Any] = {}

    if route == "ipadapter_faceid":
        out = _faceid_patch(ref, plan)
    elif route == "kontext":
        out = _kontext_patch(ref, plan.get("model"))
    elif route == "qwen_edit":
        out = _qwen_edit_patch(ref, plan.get("model"))
    elif route == "img2img":
        out = {
            "reference_role": "restyle",
            "workflow_mode": "generate",
            "input_image": ref,
            "reference_image": ref,
            "preserve_character": True,
            "face_preservation": True,
            "identity_mode": "preserve_face",
            "edit_type": "auto",
            "cn_selection": "Custom...",
            "cn_type": "img2img",
        }
    else:
        return {}

    if plan.get("notice"):
        out["_identity_fallback_notice"] = plan["notice"]

    for key, value in out.items():
        if key.startswith("_"):
            setattr(job, key, value)
        else:
            setattr(job, key, value)
    return out
