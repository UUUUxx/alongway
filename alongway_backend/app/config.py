from functools import lru_cache
import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_DIR = BACKEND_DIR.parent
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(WORKSPACE_DIR / ".env")
load_dotenv(WORKSPACE_DIR.parent / ".env")


class Settings:
    def __init__(self) -> None:
        self.app_name = "route-deals-backend"
        # Support both DATABASE_URL (for MVP SQLite) and PostgreSQL config
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./alongway_mvp.db")
        self.postgres_host = os.getenv("POSTGRES_HOST", "localhost")
        self.postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))
        self.postgres_db = os.getenv("POSTGRES_DB")
        self.postgres_user = os.getenv("POSTGRES_USER")
        self.postgres_password = os.getenv("POSTGRES_PASSWORD")
        
        # MVP Agent service config
        self.agent_service_url = os.getenv("AGENT_SERVICE_URL", "http://localhost:8001")
        self.agent_service_timeout = int(os.getenv("AGENT_SERVICE_TIMEOUT", "180"))
        self.amap_key = os.getenv(
            "AMAP_KEY", "913efea4bc17530034d7db2db3d46903"
        ).strip()
        self.amap_js_key = os.getenv("AMAP_JS_KEY", "").strip() or self.amap_key
        self.amap_base_url = _normalize_amap_base_url(
            os.getenv("AMAP_BASE_URL", "https://restapi.amap.com")
        )
        self.amap_timeout_seconds = int(os.getenv("AMAP_TIMEOUT_SECONDS", "8"))

        # Debug mode — when True, log full request bodies (including coordinates+preferences)
        self.debug = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        # Fallback to PostgreSQL if DATABASE_URL not set
        missing = [
            name
            for name, value in (
                ("POSTGRES_DB", self.postgres_db),
                ("POSTGRES_USER", self.postgres_user),
                ("POSTGRES_PASSWORD", self.postgres_password),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                "Missing database configuration: "
                + ", ".join(missing)
                + ". Set DATABASE_URL or POSTGRES_* variables."
            )
        user = quote_plus(self.postgres_user or "")
        password = quote_plus(self.postgres_password or "")
        return (
            f"postgresql+psycopg2://{user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _normalize_amap_base_url(value: str) -> str:
    base_url = value.strip().rstrip("/")
    if base_url.endswith("/v3") or base_url.endswith("/v4"):
        return base_url.rsplit("/", 1)[0]
    return base_url
