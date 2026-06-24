"""Shared pytest hooks for backend tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clear_model_inventory_cache_between_tests():
    try:
        from dreamforge_cli_inventory import clear_model_inventory_cache
    except ImportError:
        yield
        return
    clear_model_inventory_cache()
    yield
    clear_model_inventory_cache()
