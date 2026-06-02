"""
Structured performance logging for v2 route optimization.

Records per-request timing metrics as JSON lines for easy analysis.
Output goes to both Python logger and a dedicated perf log file.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Write perf logs alongside other agent logs
PERF_LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
PERF_LOG_FILE = PERF_LOG_DIR / "perf_v2.jsonl"


@dataclass
class PerfMetrics:
    """All timing and count metrics for a single plan request."""

    request_id: str = ""
    version: str = "v2"

    # Intent parsing
    intent_parse_ms: int = 0
    llm_called: bool = False
    llm_cache_hit: bool = False
    rule_parse_used: bool = False

    # Candidate generation
    poi_candidates_total: int = 0
    haversine_topk_used: bool = False
    haversine_topk_count: int = 0

    # Route calculation
    base_route_ms: int = 0
    amap_route_calls_count: int = 0
    amap_route_total_ms: int = 0
    candidate_routes_evaluated: int = 0

    # Overall
    total_request_ms: int = 0

    # Extra info
    task_count: int = 0
    selected_poi_count: int = 0
    warnings: list[str] = field(default_factory=list)

    _started: float = field(default_factory=time.perf_counter, init=False)

    def start(self) -> None:
        self._started = time.perf_counter()

    def finish(self) -> None:
        self.total_request_ms = int((time.perf_counter() - self._started) * 1000)

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "version": self.version,
            "intent_parse_ms": self.intent_parse_ms,
            "llm_called": self.llm_called,
            "llm_cache_hit": self.llm_cache_hit,
            "rule_parse_used": self.rule_parse_used,
            "poi_candidates_total": self.poi_candidates_total,
            "haversine_topk_used": self.haversine_topk_used,
            "haversine_topk_count": self.haversine_topk_count,
            "base_route_ms": self.base_route_ms,
            "amap_route_calls_count": self.amap_route_calls_count,
            "amap_route_total_ms": self.amap_route_total_ms,
            "candidate_routes_evaluated": self.candidate_routes_evaluated,
            "total_request_ms": self.total_request_ms,
            "task_count": self.task_count,
            "selected_poi_count": self.selected_poi_count,
            "warnings": self.warnings,
        }

    def log(self) -> None:
        """Write metrics as a structured JSON line."""
        self.finish()
        record = self.to_dict()
        logger.info(
            "PERF | intent=%dms llm_call=%s cache=%s pois=%d topk=%d "
            "amap_calls=%d amap_ms=%d total_ms=%d",
            record["intent_parse_ms"],
            record["llm_called"],
            record["llm_cache_hit"],
            record["poi_candidates_total"],
            record["haversine_topk_count"],
            record["amap_route_calls_count"],
            record["amap_route_total_ms"],
            record["total_request_ms"],
        )

        # Also write to perf log file
        try:
            PERF_LOG_DIR.mkdir(parents=True, exist_ok=True)
            with open(PERF_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            pass  # Don't let perf logging break the main flow
