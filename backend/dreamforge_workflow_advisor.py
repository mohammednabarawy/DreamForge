from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("DreamForge")


@dataclass(frozen=True)
class WorkflowAdvice:
    """A suggestion to switch to a better workflow for the detected intent."""
    current_mode: str
    suggested_mode: str
    reason: str
    confidence: float  # 0.0-1.0
    action_label: str  # UI button text, e.g. "Use Identity Edit"


def advise_workflow(
    resolved_mode: str,
    model_family: str,
    prompt_signals: dict[str, float],
    has_input_image: bool,
    edit_strength: float,
    has_mask: bool,
) -> WorkflowAdvice | None:
    """Return a workflow suggestion if a better option exists.

    Returns None if the current workflow is already optimal.
    """
    model_fam = (model_family or "").lower()
    mode = (resolved_mode or "").lower()

    if not prompt_signals or not has_input_image:
        return None

    # --- Rule 1: Major body/clothing change on Krea 2 img2img → suggest Identity Edit ---
    has_major_body_change = any(
        sig in prompt_signals
        for sig in ("clothing_removal", "clothing_change", "body_change")
    )

    if has_major_body_change and model_fam == "krea2" and mode == "img2img":
        return WorkflowAdvice(
            current_mode=mode,
            suggested_mode="krea2_edit",
            reason=(
                "Identity Edit mode preserves the subject's face while allowing "
                "full body and clothing changes. Standard img2img at low denoise "
                "will preserve the original clothing from the input image."
            ),
            confidence=0.85,
            action_label="Use Identity Edit",
        )

    # --- Rule 2: Major body/clothing change on Flux img2img → suggest Kontext ---
    if has_major_body_change and model_fam in ("flux", "flux_kontext") and mode == "img2img":
        return WorkflowAdvice(
            current_mode=mode,
            suggested_mode="kontext",
            reason=(
                "Flux Kontext Edit mode preserves the subject's identity while "
                "allowing full body and scene changes. Standard img2img at low "
                "denoise will preserve unwanted elements from the input."
            ),
            confidence=0.80,
            action_label="Use Kontext Edit",
        )

    # --- Rule 3: Major transformation with very low denoise → suggest txt2img ---
    has_any_major_change = bool(prompt_signals)
    if has_any_major_change and edit_strength < 0.5 and not has_mask and mode == "img2img":
        return WorkflowAdvice(
            current_mode=mode,
            suggested_mode="txt2img",
            reason=(
                f"Your prompt describes major changes but denoise is only "
                f"{edit_strength:.2f}. The input image will dominate the output. "
                f"Consider generating from scratch with text-to-image."
            ),
            confidence=0.70,
            action_label="Generate from scratch",
        )

    # --- Rule 4: Localized change without mask → suggest inpaint ---
    # (Only if we detect localized intent like "change hair color", "fix eyes")
    # This is future work — skip for now.

    return None


def format_advice_message(advice: WorkflowAdvice) -> str:
    """Format the advice into a user-friendly message."""
    return (
        f"💡 Suggestion: {advice.reason}\n\n"
        f"Current mode: {advice.current_mode} → Suggested: {advice.suggested_mode}"
    )
