"""Backend working-directory context for legacy Fooocus modules."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

from _paths import BACKEND_ROOT


@contextmanager
def backend_working_directory(root: Path | None = None):
    """Run legacy ``modules.*`` imports with cwd at the backend root."""
    target = Path(root or BACKEND_ROOT)
    previous = os.getcwd()
    try:
        os.chdir(target)
        yield target
    finally:
        os.chdir(previous)
