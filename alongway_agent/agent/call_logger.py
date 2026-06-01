from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from agent.config import ROOT_DIR

logger = logging.getLogger("agent.call_log")
LOG_DIR = ROOT_DIR / "logs"
CALL_LOG_PATH = LOG_DIR / "agent_calls.jsonl"


def log_call(
    event: str,
    *,
    request: Any = None,
    result: Any = None,
    error: Any = None,
) -> None:
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "request": _safe_json(request),
        "result": _safe_json(result),
        "error": _safe_json(error),
    }
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with CALL_LOG_PATH.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception as exc:  # pragma: no cover - logging must not break planning
        logger.warning("failed to write call log: %s", exc)


def _safe_json(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _mask_or_safe(key, item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe_json(item) for item in value]
    if isinstance(value, tuple):
        return [_safe_json(item) for item in value]
    return value


def _mask_or_safe(key: Any, value: Any) -> Any:
    if str(key).lower() in {"key", "api_key", "apikey", "authorization"}:
        return "***"
    return _safe_json(value)
