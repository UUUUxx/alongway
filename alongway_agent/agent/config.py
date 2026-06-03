from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def _load_local_env() -> None:
    env_path = ROOT_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    backend_base_url: str = "http://localhost:8000"
    use_mock_backend: bool = False
    request_timeout_seconds: float = 60.0
    stepfun_api_key: str = ""
    stepfun_base_url: str = "https://api.stepfun.com/v1"
    stepfun_model: str = "step-3.5-flash"
    stepfun_timeout_seconds: float = 20.0
    poi_timeout_seconds: float = 20.0
    route_timeout_seconds: float = 120.0

    # ── v2 optimization toggles ──
    route_optimization_v2: bool = True
    haversine_topk: int = 5
    llm_rule_first: bool = True
    llm_cache_enabled: bool = True
    llm_cache_ttl_seconds: int = 300
    connection_pool_enabled: bool = True


def _env_bool(key: str, default: bool) -> bool:
    """Parse a boolean environment variable."""
    raw = os.getenv(key, str(default)).strip().lower()
    return raw not in {"0", "false", "no", "off"}


def load_settings() -> Settings:
    _load_local_env()
    use_mock_raw = os.getenv("ALONGWAY_USE_MOCK_BACKEND", "false").strip().lower()
    return Settings(
        backend_base_url=os.getenv(
            "ALONGWAY_BACKEND_BASE_URL", "http://localhost:8000"
        ).rstrip("/"),
        use_mock_backend=use_mock_raw not in {"0", "false", "no"},
        request_timeout_seconds=float(
            os.getenv("ALONGWAY_REQUEST_TIMEOUT_SECONDS", "60")
        ),
        stepfun_api_key=os.getenv(
            "STEPFUN_API_KEY",
            "UdMr061Erdx7bUdn4LFq0xkr3jXtzgES5sQnbsGFapbncfOXRQDZgGSjPzs7iWnP",
        ).strip(),
        stepfun_base_url=os.getenv(
            "STEPFUN_BASE_URL", "https://api.stepfun.com/v1"
        ).rstrip("/"),
        stepfun_model=os.getenv("STEPFUN_MODEL", "step-3.5-flash"),
        stepfun_timeout_seconds=float(os.getenv("STEPFUN_TIMEOUT_SECONDS", "20")),
        poi_timeout_seconds=float(os.getenv("ALONGWAY_POI_TIMEOUT_SECONDS", "20")),
        route_timeout_seconds=float(os.getenv("ALONGWAY_ROUTE_TIMEOUT_SECONDS", "120")),
        # v2 toggles
        route_optimization_v2=_env_bool("ROUTE_OPTIMIZATION_V2", True),
        haversine_topk=int(os.getenv("HAVERSINE_TOPK", "5")),
        llm_rule_first=_env_bool("LLM_RULE_FIRST", True),
        llm_cache_enabled=_env_bool("LLM_CACHE_ENABLED", True),
        llm_cache_ttl_seconds=int(os.getenv("LLM_CACHE_TTL_SECONDS", "300")),
        connection_pool_enabled=_env_bool("CONNECTION_POOL_ENABLED", True),
    )
