#!/usr/bin/env python3
"""Fail when UI feature surfaces lack backend handlers (Fooocus parity audit)."""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from dreamforge_feature_surfaces import (  # noqa: E402
    audit_frontend_surface_tokens,
    run_feature_surface_audit,
)


def main() -> int:
    issues = run_feature_surface_audit() + audit_frontend_surface_tokens()
    if issues:
        print("Feature surface audit FAILED:\n")
        for item in issues:
            print(f"  - {item}")
        return 1
    print("Feature surface audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
