"""Fooocus-style Vary (subtle / strong) img2img presets."""

from __future__ import annotations

from typing import Any

VALID_VARY_AMOUNTS = frozenset({"subtle", "strong"})

VARY_STRENGTH: dict[str, float] = {
    "subtle": 0.3,
    "strong": 0.6,
}


def normalize_vary_amount(value: Any) -> str | None:
    key = str(value or "").strip().lower()
    return key if key in VALID_VARY_AMOUNTS else None


def apply_vary_amount_to_job(job) -> dict[str, Any]:
    """Ensure vary_amount maps to restyle img2img strength when unset."""
    amount = normalize_vary_amount(getattr(job, "vary_amount", None))
    if not amount:
        return {}
    strength = VARY_STRENGTH[amount]
    out: dict[str, Any] = {
        "vary_amount": amount,
        "reference_role": "restyle",
        "workflow_mode": "generate",
        "cn_selection": "Custom...",
        "cn_type": "img2img",
        "edit_type": "auto",
    }
    if getattr(job, "edit_strength", None) is None:
        out["edit_strength"] = strength
    return out
