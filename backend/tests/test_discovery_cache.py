"""Tests for dreamforge_discovery_cache — put/get/invalidate/TTL."""

import time

import pytest

from dreamforge_discovery_cache import (
    DEFAULT_TTL_SECONDS,
    get_cached_response,
    invalidate,
    params_cache_key,
    put_cached_response,
)
from dreamforge_provider_base import ProviderSearchParams, SearchFilters


@pytest.fixture(autouse=True)
def clean_cache():
    invalidate()
    yield
    invalidate()


class TestParamsCacheKey:
    def test_deterministic(self):
        p = ProviderSearchParams(query="flux", kind="checkpoint")
        assert params_cache_key("civitai", p) == params_cache_key("civitai", p)

    def test_provider_prefix(self):
        p = ProviderSearchParams(query="flux")
        assert params_cache_key("civitai", p).startswith("civitai_")
        assert params_cache_key("huggingface", p).startswith("huggingface_")

    def test_different_query_different_key(self):
        p1 = ProviderSearchParams(query="flux")
        p2 = ProviderSearchParams(query="sdxl")
        assert params_cache_key("civitai", p1) != params_cache_key("civitai", p2)

    def test_different_kind_different_key(self):
        p1 = ProviderSearchParams(kind="checkpoint")
        p2 = ProviderSearchParams(kind="lora")
        assert params_cache_key("civitai", p1) != params_cache_key("civitai", p2)

    def test_different_page_different_key(self):
        p1 = ProviderSearchParams(page=1)
        p2 = ProviderSearchParams(page=2)
        assert params_cache_key("civitai", p1) != params_cache_key("civitai", p2)

    def test_filters_affect_key(self):
        p1 = ProviderSearchParams(filters=SearchFilters(nsfw=False))
        p2 = ProviderSearchParams(filters=SearchFilters(nsfw=True))
        assert params_cache_key("civitai", p1) != params_cache_key("civitai", p2)


class TestCachePutGet:
    def test_put_and_get(self):
        key = "test_key_1"
        data = {"assets": [{"id": "x"}], "total": 1}
        put_cached_response(key, data)
        result = get_cached_response(key)
        assert result is not None
        assert result["total"] == 1

    def test_get_missing_returns_none(self):
        assert get_cached_response("nonexistent_key") is None

    def test_ttl_expiry(self):
        key = "test_ttl_key"
        put_cached_response(key, {"x": 1}, ttl_seconds=0)
        time.sleep(0.1)
        assert get_cached_response(key, ttl_seconds=0) is None

    def test_default_ttl(self):
        key = "test_default_ttl"
        put_cached_response(key, {"x": 1})
        assert get_cached_response(key) is not None
        assert get_cached_response(key, ttl_seconds=DEFAULT_TTL_SECONDS) is not None


class TestInvalidate:
    def test_invalidate_all(self):
        put_cached_response("civitai_aaa", {"x": 1})
        put_cached_response("huggingface_bbb", {"x": 2})
        removed = invalidate()
        assert removed >= 2
        assert get_cached_response("civitai_aaa") is None
        assert get_cached_response("huggingface_bbb") is None

    def test_invalidate_by_provider(self):
        put_cached_response("civitai_aaa", {"x": 1})
        put_cached_response("huggingface_bbb", {"x": 2})
        removed = invalidate("civitai")
        assert removed == 1
        assert get_cached_response("civitai_aaa") is None
        assert get_cached_response("huggingface_bbb") is not None

    def test_invalidate_unknown_provider(self):
        put_cached_response("civitai_aaa", {"x": 1})
        removed = invalidate("nonexistent")
        assert removed == 0
        assert get_cached_response("civitai_aaa") is not None
