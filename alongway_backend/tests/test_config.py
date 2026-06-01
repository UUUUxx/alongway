"""
Tests for backend configuration defaults.
"""
from app.config import Settings


def test_database_url_defaults_to_sqlite(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_DB", raising=False)
    monkeypatch.delenv("POSTGRES_USER", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)

    settings = Settings()

    assert settings.sqlalchemy_database_url == "sqlite:///./alongway_mvp.db"


def test_amap_base_url_accepts_versioned_url(monkeypatch):
    monkeypatch.setenv("AMAP_BASE_URL", "https://restapi.amap.com/v3")

    settings = Settings()

    assert settings.amap_base_url == "https://restapi.amap.com"


def test_backend_env_file_is_loaded():
    settings = Settings()

    assert settings.amap_key
