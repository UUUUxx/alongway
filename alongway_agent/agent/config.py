from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    backend_base_url: str = "http://localhost:8000"
    use_mock_backend: bool = False
    request_timeout_seconds: float = 10.0


def load_settings() -> Settings:
    use_mock_raw = os.getenv("ALONGWAY_USE_MOCK_BACKEND", "false").strip().lower()
    return Settings(
        backend_base_url=os.getenv(
            "ALONGWAY_BACKEND_BASE_URL", "http://localhost:8000"
        ).rstrip("/"),
        use_mock_backend=use_mock_raw not in {"0", "false", "no"},
        request_timeout_seconds=float(
            os.getenv("ALONGWAY_REQUEST_TIMEOUT_SECONDS", "10")
        ),
    )
