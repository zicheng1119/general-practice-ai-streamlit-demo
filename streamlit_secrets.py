from __future__ import annotations

from collections.abc import Mapping
from typing import Any


DEFAULT_ENV = {
    "AI_TRIAGE_MODE": "deepseek",
    "AI_TRIAGE_PROVIDER": "deepseek",
    "AI_TRIAGE_MODEL": "deepseek-v4-pro",
    "AI_TRIAGE_BASE_URL": "https://api.deepseek.com",
    "AI_TRIAGE_REASONING_EFFORT": "high",
    "AI_TRIAGE_THINKING_MODE": "disabled",
    "AI_TRIAGE_SECONDARY_PROVIDER": "kimi",
    "AI_TRIAGE_SECONDARY_MODEL": "moonshot-v1-auto",
    "AI_TRIAGE_SECONDARY_BASE_URL": "https://api.moonshot.cn/v1",
    "AI_TRIAGE_SECONDARY_REASONING_EFFORT": "high",
    "AI_TRIAGE_SECONDARY_THINKING_MODE": "disabled",
    "BOOKING_PROVIDER": "mock",
    "CLINICAL_PROVIDER": "memory",
    "REMINDER_PROVIDER": "medtimer",
}

SECRET_ALIASES = {
    "AI_TRIAGE_API_KEY": ("AI_TRIAGE_API_KEY", "DEEPSEEK_API_KEY", "deepseek_api_key"),
    "AI_TRIAGE_SECONDARY_API_KEY": (
        "AI_TRIAGE_SECONDARY_API_KEY",
        "KIMI_API_KEY",
        "MOONSHOT_API_KEY",
        "kimi_api_key",
        "moonshot_api_key",
    ),
}


def _stringify(value: Any) -> str:
    return str(value).strip().strip('"').strip("'")


def _flatten(mapping: Mapping[str, Any]) -> dict[str, str]:
    flat: dict[str, str] = {}
    for key, value in mapping.items():
        if isinstance(value, Mapping):
            flat.update(_flatten(value))
        elif value is not None:
            flat[str(key)] = _stringify(value)
    return flat


def build_env_from_secrets(secrets: Mapping[str, Any]) -> dict[str, str]:
    flat = _flatten(secrets)
    env = dict(DEFAULT_ENV)

    for key in DEFAULT_ENV:
        if flat.get(key):
            env[key] = flat[key]

    for target_key, aliases in SECRET_ALIASES.items():
        for alias in aliases:
            if flat.get(alias):
                env[target_key] = flat[alias]
                break

    return env


def mask_secret(value: str | None) -> str:
    if not value:
        return "未配置"
    if len(value) <= 10:
        return "已配置"
    return f"{value[:4]}...{value[-4:]}"
