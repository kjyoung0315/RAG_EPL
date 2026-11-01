from src.config import get_settings


def test_default_chat_model_is_gpt_54_nano(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_CHAT_MODEL", raising=False)
    assert get_settings().chat_model == "gpt-5.4-nano"


def test_gms_key_is_used_before_openai_key(monkeypatch) -> None:
    monkeypatch.setenv("GMS_KEY", "gms-test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    settings = get_settings()
    assert settings.api_key == "gms-test-key"
    assert settings.has_api_key
    assert settings.api_base_url == "https://gms.ssafy.io/gmsapi/api.openai.com/v1/"
