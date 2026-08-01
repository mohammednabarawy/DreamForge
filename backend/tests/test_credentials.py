"""Tests for dreamforge_credentials — secure credential store, never exposes secrets."""

import pytest

from dreamforge_credentials import (
    CREDENTIAL_PROVIDERS,
    credential_redacted_status,
    get_provider_credential,
    provider_credential_status,
    set_provider_credential,
)


@pytest.fixture
def fake_config(monkeypatch):
    config = {}

    def fake_load():
        return config

    def fake_save(new_config):
        snapshot = dict(new_config)
        config.clear()
        config.update(snapshot)

    monkeypatch.setattr("dreamforge_credentials._read_app_config", fake_load)
    monkeypatch.setattr("dreamforge_credentials._write_app_config", fake_save)
    return config


class TestProviderCredentialStatus:
    def test_empty_status(self, fake_config):
        status = provider_credential_status()
        assert status["ok"] is True
        assert status["status"]["civitai"]["configured"] is False
        assert status["status"]["civitai"]["tail"] == ""

    def test_configured_status(self, fake_config):
        fake_config["ui"] = {"civitai_api_key": "civ_key_1234"}
        status = provider_credential_status()
        assert status["status"]["civitai"]["configured"] is True
        assert status["status"]["civitai"]["tail"] == "1234"

    def test_never_exposes_full_secret(self, fake_config):
        fake_config["ui"] = {"civitai_api_key": "super_secret_key_9999"}
        status = provider_credential_status()
        assert "super_secret_key_9999" not in str(status)


class TestGetProviderCredential:
    def test_returns_secret_backend_only(self, fake_config):
        fake_config["ui"] = {"civitai_api_key": "civ_key_1234"}
        assert get_provider_credential("civitai") == "civ_key_1234"

    def test_empty_when_not_configured(self, fake_config):
        assert get_provider_credential("civitai") == ""

    def test_unknown_provider_returns_empty(self, fake_config):
        assert get_provider_credential("unknown") == ""

    def test_huggingface_uses_its_own_secret(self, fake_config):
        fake_config["ui"] = {"civitai_api_key": "civ", "huggingface_api_key": "hf_secret"}
        assert get_provider_credential("huggingface") == "hf_secret"


class TestSetProviderCredential:
    def test_set(self, fake_config):
        result = set_provider_credential("civitai", "new_key_5678")
        assert result["ok"] is True
        assert result["status"]["civitai"]["configured"] is True
        assert fake_config["ui"]["civitai_api_key"] == "new_key_5678"

    def test_clear_with_empty(self, fake_config):
        fake_config["ui"] = {"civitai_api_key": "old_key"}
        result = set_provider_credential("civitai", "")
        assert result["ok"] is True
        assert result["status"]["civitai"]["configured"] is False
        assert fake_config["ui"]["civitai_api_key"] == ""

    def test_unsupported_provider(self, fake_config):
        result = set_provider_credential("unsupported", "key")
        assert result["ok"] is False
        assert "unsupported_provider" in result["error"]

    def test_huggingface_does_not_overwrite_civitai(self, fake_config):
        fake_config["ui"] = {"civitai_api_key": "civ"}
        set_provider_credential("huggingface", "hf_token")
        assert fake_config["ui"] == {"civitai_api_key": "civ", "huggingface_api_key": "hf_token"}


class TestCredentialRedactedStatus:
    def test_returns_status_dict_only(self, fake_config):
        fake_config["ui"] = {"civitai_api_key": "abcd"}
        status = credential_redacted_status()
        assert status["civitai"]["configured"] is True


class TestCredentialProviders:
    def test_civitai_is_recognized(self):
        assert "civitai" in CREDENTIAL_PROVIDERS
