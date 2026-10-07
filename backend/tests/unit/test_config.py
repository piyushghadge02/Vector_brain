"""Unit tests for application configuration."""

from app.config import Settings


def test_defaults_are_sane():
    s = Settings()
    assert s.app_name == "VectorBrain"
    assert s.env == "dev"
    assert s.database_url.startswith("postgresql+asyncpg://")
    assert s.retrieval_top_k == 8
    assert s.max_file_mb == 50


def test_env_override(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_value")
    s = Settings()
    assert s.env == "prod"
    assert s.log_level == "DEBUG"
    assert s.groq_api_key == "gsk_test_value"


def test_groq_key_defaults_to_none():
    assert Settings().groq_api_key is None
