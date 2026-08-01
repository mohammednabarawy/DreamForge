"""Tests for dreamforge_provider_base — error classification, HTTP helper, types."""

import urllib.error

import pytest

from dreamforge_provider_base import (
    ERR_ACCESS,
    ERR_AUTH,
    ERR_NETWORK,
    ERR_NOT_FOUND,
    ERR_PROVIDER,
    ERR_RATE_LIMIT,
    ERR_TIMEOUT,
    DiscoveryProvider,
    ProviderError,
    ProviderSearchParams,
    ProviderSearchResult,
    SearchFilters,
    classify_http_error,
)


class TestProviderError:
    def test_fields(self):
        err = ProviderError("auth_required", "Need login", 401)
        assert err.code == "auth_required"
        assert err.message == "Need login"
        assert err.status == 401
        assert str(err) == "Need login"

    def test_to_dict(self):
        err = ProviderError("timeout", "Timed out")
        d = err.to_dict()
        assert d["code"] == "timeout"
        assert d["message"] == "Timed out"
        assert d["status"] == 0


class TestClassifyHttpError:
    def test_401(self):
        exc = urllib.error.HTTPError("url", 401, "Unauthorized", {}, None)
        pe = classify_http_error(exc)
        assert pe.code == ERR_AUTH
        assert pe.status == 401

    def test_403(self):
        exc = urllib.error.HTTPError("url", 403, "Forbidden", {}, None)
        pe = classify_http_error(exc)
        assert pe.code == ERR_ACCESS

    def test_404(self):
        exc = urllib.error.HTTPError("url", 404, "Not Found", {}, None)
        pe = classify_http_error(exc)
        assert pe.code == ERR_NOT_FOUND

    def test_429(self):
        exc = urllib.error.HTTPError("url", 429, "Rate limited", {}, None)
        pe = classify_http_error(exc)
        assert pe.code == ERR_RATE_LIMIT

    def test_500(self):
        exc = urllib.error.HTTPError("url", 500, "Server Error", {}, None)
        pe = classify_http_error(exc)
        assert pe.code == ERR_PROVIDER
        assert pe.status == 500

    def test_url_error_timeout(self):
        exc = urllib.error.URLError("timed out")
        pe = classify_http_error(exc)
        assert pe.code == ERR_TIMEOUT

    def test_url_error_network(self):
        exc = urllib.error.URLError("Connection refused")
        pe = classify_http_error(exc)
        assert pe.code == ERR_NETWORK

    def test_timeout_error(self):
        exc = TimeoutError("deadline exceeded")
        pe = classify_http_error(exc)
        assert pe.code == ERR_TIMEOUT

    def test_generic_exception(self):
        exc = RuntimeError("something broke")
        pe = classify_http_error(exc)
        assert pe.code == ERR_PROVIDER


class TestSearchFilters:
    def test_defaults(self):
        f = SearchFilters()
        assert f.nsfw is False
        assert f.sort == "relevance"

    def test_cache_key_deterministic(self):
        f1 = SearchFilters(nsfw=True, sort="downloads")
        f2 = SearchFilters(nsfw=True, sort="downloads")
        assert f1.to_cache_key() == f2.to_cache_key()

    def test_cache_key_varies(self):
        f1 = SearchFilters(nsfw=False)
        f2 = SearchFilters(nsfw=True)
        assert f1.to_cache_key() != f2.to_cache_key()


class TestProviderSearchParams:
    def test_defaults(self):
        p = ProviderSearchParams()
        assert p.query == ""
        assert p.limit == 20
        assert p.page == 1

    def test_custom(self):
        p = ProviderSearchParams(query="flux", kind="checkpoint", limit=5, page=2)
        assert p.query == "flux"
        assert p.kind == "checkpoint"


class TestProviderSearchResult:
    def test_ok_when_no_error(self):
        r = ProviderSearchResult(provider="test")
        assert r.ok is True

    def test_not_ok_when_error(self):
        r = ProviderSearchResult(provider="test", error="fail", error_code="timeout")
        assert r.ok is False

    def test_to_dict(self):
        r = ProviderSearchResult(provider="civitai", total=42, page=2)
        d = r.to_dict()
        assert d["provider"] == "civitai"
        assert d["total"] == 42
        assert d["ok"] is True
        assert d["assets"] == []


class TestDiscoveryProviderBase:
    def test_supports_kind_empty(self):
        p = DiscoveryProvider()
        assert p.supports_kind("") is True

    def test_search_not_implemented(self):
        p = DiscoveryProvider()
        with pytest.raises(NotImplementedError):
            p.search(ProviderSearchParams())

    def test_info(self):
        p = DiscoveryProvider()
        p.id = "test"
        p.display_name = "Test"
        p.supported_kinds = ("checkpoint",)
        info = p.info()
        assert info["id"] == "test"
        assert "checkpoint" in info["supported_kinds"]
