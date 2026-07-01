from __future__ import annotations

import importlib


def test_settings_accepts_deepseek_api_key_alias(monkeypatch):
    monkeypatch.setenv("AI_TRIAGE_API_KEY", "")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-alias-key")

    import app.settings as settings_module

    reloaded = importlib.reload(settings_module)

    assert reloaded.settings.triage_api_key == "deepseek-alias-key"


def test_settings_accepts_moonshot_secondary_api_key_alias(monkeypatch):
    monkeypatch.setenv("AI_TRIAGE_SECONDARY_API_KEY", "")
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    monkeypatch.setenv("MOONSHOT_API_KEY", "moonshot-alias-key")

    import app.settings as settings_module

    reloaded = importlib.reload(settings_module)

    assert reloaded.settings.triage_secondary_api_key == "moonshot-alias-key"
