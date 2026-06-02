#!/usr/bin/env python3
"""
Test script for v2 route optimization.

Covers:
1. Original v1 code still importable
2. HaversinePreFilter reduces candidates
3. Haversine distance calculation
4. LLMCache hit/miss/ttl
5. IntentParser rule-first + cache
6. PerfMetrics JSON logging
7. HttpBackendClient connection pool reuse
8. Config switch: v2 on/off

Run from the shunlu/shunlu directory:
    cd alongway_agent
    python ../scripts/test_route_optimizer_v2.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Ensure agent is on the path
AGENT_DIR = Path(__file__).resolve().parents[1] / "alongway_agent"
sys.path.insert(0, str(AGENT_DIR))

os.environ.setdefault("STEPFUN_API_KEY", "")
os.environ.setdefault("ALONGWAY_USE_MOCK_BACKEND", "true")


def test_v1_imports():
    """Verify original v1 code still importable."""
    print("\n=== Test 1: v1 imports ===")
    from agent.models import PlanRequest, UserPreferences, PlanConstraints
    from agent.intent_parser import IntentParser
    from agent.planner_agent import PlanAgent
    from agent.scorer import PlanScorer
    print("  [PASS] All v1 modules importable")
    return True


def test_haversine_filter():
    """Verify Haversine pre-filter reduces candidates."""
    print("\n=== Test 2: HaversinePreFilter ===")
    from agent.haversine_filter import HaversinePreFilter
    from agent.models import EnrichedCandidate, Location, POI

    # Create test data: 5 POIs at varying distances from the route
    start = Location(name="Start", longitude=114.3645, latitude=30.5378)
    end = Location(name="End", longitude=114.4052, latitude=30.5078)

    pois = []
    for i in range(5):
        poi = POI(
            poi_id=f"poi_{i}",
            name=f"POI {i}",
            type="food",
            address="test",
            location="test",
            # Vary distances: some near route, some far
            longitude=114.3645 + 0.01 * (i + 1),
            latitude=30.5378 - 0.005 * (i + 1),
            rating=4.0 + i * 0.1,
            source_keyword="food",
        )
        pois.append(EnrichedCandidate(
            task_id="task_1",
            task_type="eat_meal",
            poi=poi,
            deal=None,
        ))

    candidates_by_task = {"task_1": pois}

    # With top_k=3, should only keep 3
    filt = HaversinePreFilter(top_k=3)
    result = filt.filter(start, end, candidates_by_task)
    assert len(result["task_1"]) == 3, f"Expected 3, got {len(result['task_1'])}"
    print(f"  [PASS] Reduced from {len(pois)} to {len(result['task_1'])} candidates")

    # With top_k=1, should only keep 1
    filt2 = HaversinePreFilter(top_k=1)
    result2 = filt2.filter(start, end, candidates_by_task)
    assert len(result2["task_1"]) == 1
    print(f"  [PASS] Reduced to {len(result2['task_1'])} candidate")

    # Verify Haversine distance is reasonable
    dist = HaversinePreFilter.haversine_meters(
        start.longitude or 0, start.latitude or 0,
        end.longitude or 0, end.latitude or 0,
    )
    assert 3000 < dist < 10000, f"Distance {dist}m seems unreasonable for this route"
    print(f"  [PASS] Start->End Haversine distance: {int(dist)}m")

    return True


def test_llm_cache():
    """Verify LLM cache operations."""
    print("\n=== Test 3: LLMCache ===")
    from agent.llm_cache import LLMCache

    cache = LLMCache(enabled=True, ttl_seconds=300)

    # Miss
    result = cache.get("从武大去光谷")
    assert result is None
    print("  [PASS] Cache miss works")

    # Set and hit
    cache.set("从武大去光谷", {"tasks": [{"type": "eat_meal"}]})
    result = cache.get("从武大去光谷")
    assert result is not None
    assert result["tasks"][0]["type"] == "eat_meal"
    print("  [PASS] Cache hit works")

    # Same query (whitespace difference) should hit
    result2 = cache.get("  从武大去光谷  ")
    assert result2 is not None
    print("  [PASS] Normalized cache hit works")

    # Stats
    stats = cache.stats
    assert stats["hits"] >= 2
    assert stats["misses"] >= 1
    print(f"  [PASS] Cache stats: {stats}")

    # Disabled cache
    cache_disabled = LLMCache(enabled=False)
    result3 = cache_disabled.get("任意查询")
    assert result3 is None
    print("  [PASS] Disabled cache returns None")

    # TTL expiration
    cache_ttl = LLMCache(enabled=True, ttl_seconds=0)  # immediate expiry
    cache_ttl.set("测试", {"key": "val"})
    time.sleep(0.1)
    result4 = cache_ttl.get("测试")
    assert result4 is None
    print("  [PASS] TTL expiration works")

    return True


def test_intent_parser_rule_first():
    """Verify intent parser can work with rules only (no LLM call)."""
    print("\n=== Test 4: IntentParser rule-first ===")
    import asyncio
    from agent.intent_parser import IntentParser
    from agent.models import UserPreferences

    # No LLM client → pure rules
    parser = IntentParser(
        llm_client=None,
        rule_first=True,
    )

    async def _run():
        result = await parser.parse_with_metadata(
            user_query="从武汉大学到光谷广场，顺路找点吃的，再买杯奶茶",
            budget=20,
            preferences=UserPreferences(),
        )
        intent = result.intent
        # Should have parsed at least 2 tasks
        assert len(intent.tasks) >= 2, f"Expected >=2 tasks, got {len(intent.tasks)}"
        assert not result.llm_called
        assert not result.cache_hit
        print(f"  [PASS] Rule-first: {len(intent.tasks)} tasks, LLM called={result.llm_called}")
        print(f"     Tasks: {[(t.type.value, t.raw_text) for t in intent.tasks]}")
        return True

    result = asyncio.run(_run())
    return result


def test_perf_logger():
    """Verify structured performance logging."""
    print("\n=== Test 5: PerfMetrics ===")
    from agent.perf_logger import PerfMetrics

    metrics = PerfMetrics(request_id="test-001")
    metrics.start()
    metrics.intent_parse_ms = 5
    metrics.llm_called = False
    metrics.llm_cache_hit = True
    metrics.poi_candidates_total = 8
    metrics.haversine_topk_count = 3
    metrics.amap_route_calls_count = 4
    metrics.amap_route_total_ms = 800
    time.sleep(0.01)
    metrics.log()

    d = metrics.to_dict()
    assert d["request_id"] == "test-001"
    assert d["version"] == "v2"
    assert d["intent_parse_ms"] == 5
    assert d["llm_cache_hit"] is True
    assert d["total_request_ms"] > 0
    print(f"  [PASS] PerfMetrics: total_ms={d['total_request_ms']}")
    print(f"     JSON: {d}")
    return True


def test_config_v2_switch():
    """Verify v2 configuration switches."""
    print("\n=== Test 6: v2 config switch ===")
    from agent.config import load_settings

    # Test with v2 enabled
    settings = load_settings()
    assert settings.route_optimization_v2 is True
    assert settings.haversine_topk == 3
    assert settings.llm_rule_first is True
    assert settings.llm_cache_enabled is True
    print(f"  [PASS] v2 enabled: topk={settings.haversine_topk}, rule_first={settings.llm_rule_first}")

    # Test with v2 disabled via env
    os.environ["ROUTE_OPTIMIZATION_V2"] = "false"
    settings2 = load_settings()
    assert settings2.route_optimization_v2 is False
    os.environ.pop("ROUTE_OPTIMIZATION_V2")
    print("  [PASS] v2 disabled via env works")
    return True


def test_haversine_detour_approximation():
    """Verify Haversine detour calculation is reasonable."""
    print("\n=== Test 7: Haversine detour accuracy ===")
    from agent.haversine_filter import HaversinePreFilter

    # Wuhan University to Optics Valley (~4km apart)
    start_lon, start_lat = 114.3645, 30.5378
    end_lon, end_lat = 114.4052, 30.5078

    base = HaversinePreFilter.haversine_meters(start_lon, start_lat, end_lon, end_lat)

    # POI on the direct route
    poi_on_route_lon = (start_lon + end_lon) / 2
    poi_on_route_lat = (start_lat + end_lat) / 2
    d1 = HaversinePreFilter.haversine_meters(start_lon, start_lat, poi_on_route_lon, poi_on_route_lat)
    d2 = HaversinePreFilter.haversine_meters(poi_on_route_lon, poi_on_route_lat, end_lon, end_lat)
    detour_on = d1 + d2 - base

    # POI far off the route
    poi_far_lon = end_lon + 0.02  # ~2km east
    poi_far_lat = end_lat - 0.01
    d1f = HaversinePreFilter.haversine_meters(start_lon, start_lat, poi_far_lon, poi_far_lat)
    d2f = HaversinePreFilter.haversine_meters(poi_far_lon, poi_far_lat, end_lon, end_lat)
    detour_far = d1f + d2f - base

    # POI on route should have lower detour than far POI
    assert detour_on < detour_far, f"detour_on={detour_on:.0f}m should be < detour_far={detour_far:.0f}m"
    # Triangle inequality: detour >= 0
    assert detour_on >= -1, f"detour_on={detour_on:.0f}m (minor floating point ok)"
    print(f"  [PASS] Base distance: {int(base)}m")
    print(f"  [PASS] On-route POI detour: {int(detour_on)}m")
    print(f"  [PASS] Far POI detour: {int(detour_far)}m")
    return True


def test_backend_client_pool():
    """Verify connection pool reuse."""
    print("\n=== Test 8: Connection pool ===")
    from agent.backend_client import HttpBackendClient

    client = HttpBackendClient(
        base_url="http://localhost:8000",
        timeout_seconds=5.0,
        use_connection_pool=True,
    )
    c1 = client._get_client()
    c2 = client._get_client()
    assert c1 is c2, "Pooled client should return same instance"
    print("  [PASS] Connection pool reuses same client")
    return True


def test_llm_failure_does_not_crash():
    """Verify that LLM failure falls back to rules without crashing."""
    print("\n=== Test 9: LLM failure → rule fallback ===")
    import asyncio
    from agent.intent_parser import IntentParser
    from agent.llm_client import LLMClient
    from agent.models import UserPreferences

    # LLM client that always fails
    class FailingLLMClient(LLMClient):
        async def parse_intent(self, user_query, budget, preferences):
            raise RuntimeError("Simulated LLM failure")

        async def generate_explanation(self, user_query, selected_plan, alternative_plans):
            return None

    parser = IntentParser(
        llm_client=FailingLLMClient(),
        llm_timeout_seconds=2,
        rule_first=False,  # Force LLM path
    )

    async def _run():
        result = await parser.parse_with_metadata(
            user_query="从武大去光谷找吃的",
            budget=None,
            preferences=UserPreferences(),
        )
        # Should not crash, should fall back to rules
        assert result.intent is not None
        assert len(result.intent.tasks) >= 1  # Rule fallback should give at least 1 task
        assert result.used_fallback is True
        assert result.llm_called is True
        print(f"  [PASS] LLM failure handled gracefully: {result.fallback_reason}")
        print(f"     Parsed {len(result.intent.tasks)} tasks via rule fallback")
        return True

    result = asyncio.run(_run())
    return result


def test_llm_timeout_does_not_crash():
    """Verify LLM timeout falls back to rules without crashing."""
    print("\n=== Test 10: LLM timeout → rule fallback ===")
    import asyncio
    from agent.intent_parser import IntentParser
    from agent.llm_client import LLMClient
    from agent.models import UserPreferences

    # LLM client that takes forever
    class SlowLLMClient(LLMClient):
        async def parse_intent(self, user_query, budget, preferences):
            await asyncio.sleep(10)  # Way longer than timeout
            return {"tasks": []}

        async def generate_explanation(self, user_query, selected_plan, alternative_plans):
            return None

    parser = IntentParser(
        llm_client=SlowLLMClient(),
        llm_timeout_seconds=1,  # Short timeout for test
        rule_first=False,  # Force LLM path to test timeout
    )

    async def _run():
        result = await parser.parse_with_metadata(
            user_query="从武大去光谷吃饭",
            budget=None,
            preferences=UserPreferences(),
        )
        assert result.intent is not None
        assert len(result.intent.tasks) >= 1
        print(f"  [PASS] LLM timeout handled: {result.fallback_reason}")
        print(f"     Parsed {len(result.intent.tasks)} tasks via rule fallback")
        return True

    result = asyncio.run(_run())
    return result


def main():
    print("=" * 60)
    print("  Route Optimizer v2 — Test Suite")
    print("=" * 60)

    tests = [
        ("v1 imports", test_v1_imports),
        ("HaversinePreFilter", test_haversine_filter),
        ("LLMCache", test_llm_cache),
        ("IntentParser rule-first", test_intent_parser_rule_first),
        ("PerfMetrics", test_perf_logger),
        ("Config v2 switch", test_config_v2_switch),
        ("Haversine detour accuracy", test_haversine_detour_approximation),
        ("Connection pool", test_backend_client_pool),
        ("LLM failure → fallback", test_llm_failure_does_not_crash),
        ("LLM timeout → fallback", test_llm_timeout_does_not_crash),
    ]

    passed = 0
    failed = 0

    for name, fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"  Results: {passed} passed, {failed} failed, {len(tests)} total")
    print(f"{'=' * 60}")

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
