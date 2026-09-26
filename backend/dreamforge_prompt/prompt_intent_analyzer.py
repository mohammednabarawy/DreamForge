"""Lightweight prompt intent analysis for conflict detection.

Detects when a user's text prompt describes a major transformation
(clothing removal, outfit change, scene change, body change) that
requires high denoise to achieve — and warns if the current denoise
is too low.

No VLM or CLIP model is loaded.  Detection is regex-based (~0ms).
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Regex patterns that signal the user wants a major transformation
# requiring high denoise (>= 0.85) to achieve.
# ---------------------------------------------------------------------------

_MAJOR_TRANSFORM_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "clothing_removal": [
        re.compile(r"\bnude\b", re.I),
        re.compile(r"\bnaked\b", re.I),
        re.compile(r"\bundress", re.I),
        re.compile(r"\bremov\w*\s+cloth", re.I),
        re.compile(r"\bstrip\w*\s+(off|down|naked)", re.I),
        re.compile(r"\bwithout\s+(any\s+)?cloth", re.I),
        re.compile(r"\bno\s+cloth", re.I),
        re.compile(r"\btopless\b", re.I),
        re.compile(r"\bbottomless\b", re.I),
        re.compile(r"\bbare\s+(chest|breasts?|body|skin|torso)\b", re.I),
    ],
    "clothing_change": [
        re.compile(r"\bwearing\s+(?:a\s+)?(?!the\s+same)", re.I),
        re.compile(r"\bdressed\s+in\b", re.I),
        re.compile(r"\bchange\w*\s+(to|into|the)\s+\w*\s*(outfit|cloth|dress|suit|bikini|lingerie)", re.I),
        re.compile(r"\bswap\w*\s+(outfit|cloth|dress)", re.I),
        re.compile(r"\bin\s+a\s+(red|blue|white|black|green|pink|yellow)\s+(dress|gown|suit|bikini)", re.I),
    ],
    "major_scene_change": [
        re.compile(r"\b(on|at)\s+(a|the)\s+beach\b", re.I),
        re.compile(r"\bin\s+(a|the)\s+(forest|jungle|desert|ocean|space|moon)\b", re.I),
        re.compile(r"\b(indoor|outdoor|outside|inside)\b.*\b(outdoor|indoor|outside|inside)\b", re.I),
        re.compile(r"\btransport\w*\s+to\b", re.I),
        re.compile(r"\bmove\w*\s+to\s+a\b", re.I),
    ],
    "body_change": [
        re.compile(r"\b(breasts?|buttocks?|nipples?|genitals?)\s+(are\s+)?visible\b", re.I),
        re.compile(r"\bexposed\s+(breasts?|chest|body|skin|torso)\b", re.I),
        re.compile(r"\bshowing\s+(her|his|their)\s+(body|figure|breasts?)\b", re.I),
    ],
}

# Minimum recommended denoise for each signal type.
_DENOISE_FLOOR: dict[str, float] = {
    "clothing_removal": 0.95,
    "clothing_change": 0.85,
    "major_scene_change": 0.90,
    "body_change": 0.92,
}


def detect_transform_intent(prompt: str) -> dict[str, float]:
    """Detect major transformation signals in the prompt.

    Returns a dict mapping ``signal_type -> confidence`` (0.0–1.0).
    Only returns signals that were detected.
    """
    if not prompt:
        return {}

    signals: dict[str, float] = {}
    for signal_type, patterns in _MAJOR_TRANSFORM_PATTERNS.items():
        matches = sum(1 for p in patterns if p.search(prompt))
        if matches > 0:
            # Confidence scales with number of matching patterns
            confidence = min(1.0, matches * 0.5)
            signals[signal_type] = confidence
    return signals


def recommend_denoise_floor(signals: dict[str, float]) -> float:
    """Given detected transform signals, return the minimum recommended denoise.

    Returns ``0.0`` if no signals detected (meaning any denoise is fine).
    """
    if not signals:
        return 0.0
    # Use the highest floor across all detected signals
    return max(
        _DENOISE_FLOOR.get(sig, 0.0)
        for sig in signals
    )


def format_conflict_message(
    signals: dict[str, float],
    current_denoise: float,
    recommended_floor: float,
) -> str:
    """Format a human-readable warning message."""
    signal_names = {
        "clothing_removal": "clothing removal / nudity",
        "clothing_change": "outfit change",
        "major_scene_change": "major scene change",
        "body_change": "body/anatomy change",
    }
    detected = [signal_names.get(s, s) for s in signals]
    detected_str = ", ".join(detected)
    return (
        f"Your prompt describes {detected_str}, but denoise is set to "
        f"{current_denoise:.2f}. At this level, {int((1 - current_denoise) * 100)}% "
        f"of the original image structure is preserved, which will likely "
        f"prevent the requested change. Consider raising denoise to "
        f"{recommended_floor:.2f}+ or using an identity-preserving edit mode."
    )
