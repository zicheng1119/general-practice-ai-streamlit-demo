from streamlit_secrets import build_env_from_secrets, mask_secret


def test_build_env_from_flat_and_nested_streamlit_secrets() -> None:
    env = build_env_from_secrets(
        {
            "general": {
                "DEEPSEEK_API_KEY": "  deepseek-key  ",
                "KIMI_API_KEY": "kimi-key",
            },
            "AI_TRIAGE_SECONDARY_MODEL": "moonshot-v1-auto",
        }
    )

    assert env["AI_TRIAGE_API_KEY"] == "deepseek-key"
    assert env["AI_TRIAGE_SECONDARY_API_KEY"] == "kimi-key"
    assert env["AI_TRIAGE_PROVIDER"] == "deepseek"
    assert env["AI_TRIAGE_SECONDARY_PROVIDER"] == "kimi"
    assert env["AI_TRIAGE_SECONDARY_MODEL"] == "moonshot-v1-auto"


def test_mask_secret_never_exposes_full_value() -> None:
    assert mask_secret("sk-1234567890abcdef") == "sk-1...cdef"
    assert mask_secret("") == "未配置"
