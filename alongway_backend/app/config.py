from functools import lru_cache
import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")
load_dotenv(ROOT_DIR.parent / ".env")


class Settings:
    def __init__(self) -> None:
        self.app_name = "route-deals-backend"
        # Support both DATABASE_URL (for MVP SQLite) and PostgreSQL config
        self.database_url = os.getenv("DATABASE_URL")
        self.postgres_host = os.getenv("POSTGRES_HOST", "localhost")
        self.postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))
        self.postgres_db = os.getenv("POSTGRES_DB")
        self.postgres_user = os.getenv("POSTGRES_USER")
        self.postgres_password = os.getenv("POSTGRES_PASSWORD")
        
        # MVP Agent service config
        self.agent_service_url = os.getenv("AGENT_SERVICE_URL", "http://localhost:8001")
        self.agent_service_timeout = int(os.getenv("AGENT_SERVICE_TIMEOUT", "30"))
        self.amap_key = os.getenv("AMAP_KEY", "").strip()
        self.amap_base_url = os.getenv("AMAP_BASE_URL", "https://restapi.amap.com").rstrip("/")
        self.amap_timeout_seconds = int(os.getenv("AMAP_TIMEOUT_SECONDS", "10"))

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
