"""Shift-attention prompt spans across a batch (RuinedFooocus / yownas)."""

from __future__ import annotations

import math
import re

_RE_ATTENTION_SPAN = re.compile(r"([\-.\d]+~[\-~.\d]+)", re.X)


def shift_attention(text: str, distance: float) -> str:
    """Interpolate ``(token:0.5~1.5)`` style spans for multi-image batches."""

    def inject_value(dist: float, match_obj: re.Match[str]) -> str:
        parts = match_obj.group(1).split("~")
        span = len(parts) - 1
        if span <= 0:
            return parts[0]
        q1 = int(math.floor(dist * span))
        q2 = int(math.ceil(dist * span))
        return str(
            float(parts[q1])
            + ((float(parts[q2]) - float(parts[q1])) * (dist * span - q1))
        )

    return _RE_ATTENTION_SPAN.sub(lambda match: inject_value(distance, match), text or "")
