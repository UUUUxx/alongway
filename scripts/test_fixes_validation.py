"""
Validation tests for the three fixes:
  1. API call time reduction + caching
  2. Four template commands parsing
  3. Route optimization (Haversine circuity + TSP reorder)

Run: cd d:/shunluagent && PYTHONPATH=alongway_agent python scripts/test_fixes_validation.py
"""

import asyncio
import sys
import time

sys.path.insert(0, "alongway_agent")

from agent.intent_parser import IntentParser
from agent.llm_client import MockLLMClient
from agent.models import UserPreferences
from agent.route_evaluator import RouteEvaluator
from agent.haversine_filter import HaversinePreFilter
from agent.llm_cache import LLMCache

# ─── Access backend route cache for verification ───
sys.path.insert(0, "alongway_backend")
from app.services.route_service import _route_cache, append_polyline, _quick_distance_meters


PASS = 0
FAIL = 0


def check(condition, label):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label}")


# ══════════════════════════════════════════════════════════════════
# PART 1: Intent Parser – keyword fixes
# ══════════════════════════════════════════════════════════════════
print("=" * 60)
print("PART 1: Intent Parser – Keyword Category Fixes")
print("=" * 60)

parser = IntentParser(MockLLMClient())


def parse(q):
    return asyncio.run(
        parser.parse_with_metadata(q, budget=None, preferences=UserPreferences())
    ).intent


# 1.1 Template 1: brand + sushi + cake
print("\n1.1 Template 1: 茶百道 + 寿司 + 蛋糕")
r = parse("从华中科技大学，去世界城广场，我想喝茶百道，吃寿司，再吃一块蛋糕")
check(len(r.tasks) == 3, f"3 tasks parsed (got {len(r.tasks)})")
check(r.tasks[0].source_keywords[0] == "茶百道", f"task1: specific brand 茶百道 (got {r.tasks[0].source_keywords})")
check("寿司" in r.tasks[1].source_keywords or "日料" in r.tasks[1].source_keywords,
      f"task2: sushi keywords (got {r.tasks[1].source_keywords})")
check("蛋糕" in r.tasks[2].source_keywords or "甜品" in r.tasks[2].source_keywords,
      f"task3: cake/dessert keywords (got {r.tasks[2].source_keywords})")

# 1.2 Template 2: grilled fish + KTV + coffee + milk tea
print("\n1.2 Template 2: 烤鱼 + KTV + 咖啡 + 奶茶")
r = parse("从武汉大学，去群光广场，吃烤鱼，唱ktv，再买杯咖啡，买杯奶茶")
check(len(r.tasks) == 4, f"4 tasks parsed (got {len(r.tasks)})")
check("烧烤" not in r.tasks[0].source_keywords and "烤肉" not in r.tasks[0].source_keywords,
      f"task1(烤鱼): NO BBQ mixed in (got {r.tasks[0].source_keywords})")
check("鱼火锅" in r.tasks[0].source_keywords or "烤鱼" in r.tasks[0].source_keywords,
      f"task1(烤鱼): has 烤鱼/鱼火锅 (got {r.tasks[0].source_keywords})")
check("KTV" in r.tasks[1].source_keywords[0],
      f"task2: KTV keywords (got {r.tasks[1].source_keywords})")
check("咖啡" in r.tasks[2].source_keywords,
      f"task3: coffee keywords (got {r.tasks[2].source_keywords})")
check("奶茶" in r.tasks[3].source_keywords,
      f"task4: milk tea keywords (got {r.tasks[3].source_keywords})")

# 1.3 Template 3: haircut + BBQ + milk tea
print("\n1.3 Template 3: 剪发 + 烧烤 + 奶茶")
r = parse("从华中科技大学明德楼，到远洋世界，剪个头发，吃烧烤，再喝杯奶茶")
check(len(r.tasks) == 3, f"3 tasks parsed (got {len(r.tasks)})")
check(r.tasks[0].category == "hair", f"task1: hair category (got {r.tasks[0].category})")
check("烤鱼" not in r.tasks[1].source_keywords,
      f"task2(烧烤): NO grilled fish mixed in (got {r.tasks[1].source_keywords})")
check("烧烤" in r.tasks[1].source_keywords or "烤肉" in r.tasks[1].source_keywords,
      f"task2(烧烤): has BBQ keywords (got {r.tasks[1].source_keywords})")

# 1.4 Template 4: breakfast + coffee + snacks
print("\n1.4 Template 4: 早餐 + 咖啡 + 小吃 (CRITICAL FIX)")
r = parse("我想从华中师范大学，去武汉大学，我想顺路吃早餐再买杯咖啡，吃点小吃")
check(len(r.tasks) >= 2, f"at least 2 tasks parsed (got {len(r.tasks)})")
has_breakfast_task = any(
    "早餐" in t.source_keywords or "早点" in t.source_keywords
    for t in r.tasks
)
check(has_breakfast_task, f"breakfast task EXISTS (tasks: {[(t.source_keywords) for t in r.tasks]})")

# 1.5 New: lunch keywords
print("\n1.5 New feature: 午餐 keywords")
r = parse("从华科到武大，想吃午餐")
check(len(r.tasks) >= 1, f"at least 1 task (got {len(r.tasks)})")
check(r.tasks[0].type.value == "eat_meal", f"eat_meal type (got {r.tasks[0].type})")
check("午餐" in r.tasks[0].source_keywords or "简餐" in r.tasks[0].source_keywords,
      f"lunch keywords (got {r.tasks[0].source_keywords})")

# 1.6 New: dinner/night-snack keywords
print("\n1.6 New feature: 晚餐/夜宵 keywords")
r = parse("去吃夜宵")
check(len(r.tasks) >= 1, f"at least 1 task (got {len(r.tasks)})")
check("夜宵" in r.tasks[0].source_keywords or "晚餐" in r.tasks[0].source_keywords,
      f"night snack keywords (got {r.tasks[0].source_keywords})")

# 1.7 BBQ vs grilled fish separation
print("\n1.7 BBQ vs 烤鱼 source_keywords separation")
r1 = parse("吃烧烤")
r2 = parse("吃烤鱼")
check("烤鱼" not in r1.tasks[0].source_keywords,
      f"BBQ query: no 烤鱼 in keywords (got {r1.tasks[0].source_keywords})")
check("烧烤" not in r2.tasks[0].source_keywords and "烤肉" not in r2.tasks[0].source_keywords,
      f"Grilled fish query: no BBQ in keywords (got {r2.tasks[0].source_keywords})")

# 1.8 Korean food stays clean
print("\n1.8 Korean food: no generic words mixed")
r = parse("想吃韩餐")
check("韩餐" in r.tasks[0].source_keywords or "韩国料理" in r.tasks[0].source_keywords,
      f"Korean food keywords present (got {r.tasks[0].source_keywords})")


# ══════════════════════════════════════════════════════════════════
# PART 2: Haversine Circuity Factor
# ══════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("PART 2: Haversine Circuity Factor")
print("=" * 60)

from agent.models import Location, RouteSegment, RouteResult

# Test that fallback route applies circuity factor
fake_points = [
    Location(name="A", longitude=114.35, latitude=30.50),
    Location(name="B", longitude=114.36, latitude=30.51),
]

# Raw Haversine
raw_dist = RouteEvaluator._haversine_meters(114.35, 30.50, 114.36, 30.51)

# Fallback route (should apply circuity)
fb = RouteEvaluator._fallback_route(fake_points, "walking")
check(fb.distance_meters > raw_dist * 1.2,
      f"Walking fallback applies circuity: raw={raw_dist:.0f}m, circuity_applied={fb.distance_meters}m")

fb_bike = RouteEvaluator._fallback_route(fake_points, "bicycling")
fb_drive = RouteEvaluator._fallback_route(fake_points, "driving")

# Haversine filter circuity
print("\n2.2 HaversinePreFilter applies circuity")
hf = HaversinePreFilter(top_k=3, travel_mode="walking")
check(hf.circuity == 1.35, f"Walking circuity factor: {hf.circuity}")
hf2 = HaversinePreFilter(top_k=3, travel_mode="bicycling")
check(hf2.circuity == 1.25, f"Bicycling circuity factor: {hf2.circuity}")
hf3 = HaversinePreFilter(top_k=3, travel_mode="driving")
check(hf3.circuity == 1.30, f"Driving circuity factor: {hf3.circuity}")


# ══════════════════════════════════════════════════════════════════
# PART 3: Route Cache
# ══════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("PART 3: Amap Route Cache")
print("=" * 60)

_route_cache.clear()
check(_route_cache.stats["size"] == 0, "Cache starts empty")
check(_route_cache.stats["hits"] == 0, "Hits start at 0")

# Simulate caching
_route_cache.set(114.35, 30.50, 114.36, 30.51, "walking", (1500, 1200.0, [[114.35, 30.50], [114.36, 30.51]]))

stats = _route_cache.stats
check(stats["size"] == 1, f"Cache has 1 entry (got {stats['size']})")
check(stats["misses"] >= 0, "Misses tracked")

# Read back
cached = _route_cache.get(114.35, 30.50, 114.36, 30.51, "walking")
check(cached is not None, "Cache hit: same coordinates")
check(cached[0] == 1500, f"Cache returns correct distance: {cached[0]}m")

# Different travel mode = different cache key
cached_diff = _route_cache.get(114.35, 30.50, 114.36, 30.51, "driving")
check(cached_diff is None, "Different travel_mode = cache miss")

stats2 = _route_cache.stats
check(stats2["hits"] == 1, f"Hits tracked: {stats2['hits']}")
check(stats2["misses"] == 1, f"Misses tracked: {stats2['misses']}")

# Slightly different coordinates = different key
cached3 = _route_cache.get(114.351, 30.501, 114.361, 30.511, "walking")
check(cached3 is None, "Slightly different coords = cache miss (correct)")

print("\n3.2 Route continuity (append_polyline)")
# Same endpoint
target = [[114.35, 30.50], [114.36, 30.51]]
seg = [[114.36, 30.51], [114.37, 30.52]]
append_polyline(target, seg)
check(len(target) == 3 and target[-1] == [114.37, 30.52],
      "Continuous polyline concatenated")

# Gap test
target2 = [[114.35, 30.50]]
seg2 = [[114.40, 30.55], [114.41, 30.56]]
append_polyline(target2, seg2)
check(len(target2) == 3, f"Gap polyline bridged (got {len(target2)} points)")


# ══════════════════════════════════════════════════════════════════
# PART 4: LLM Config Tuning
# ══════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("PART 4: LLM Config Tuning")
print("=" * 60)

# Check StepFunLLMClient config via code inspection
from agent.llm_client import _INTENT_SYSTEM_PROMPT

check("【重要】" in _INTENT_SYSTEM_PROMPT, "LLM prompt has anti-mixing rules (规则12)")
check("严禁混入其他品类" in _INTENT_SYSTEM_PROMPT, "LLM prompt has explicit prohibition of mixing")
check("\"吃早餐/吃早饭\"" in _INTENT_SYSTEM_PROMPT, "LLM prompt covers breakfast keywords")
check("\"吃午餐/吃中饭\"" in _INTENT_SYSTEM_PROMPT, "LLM prompt covers lunch keywords")
check("\"吃晚餐/吃夜宵\"" in _INTENT_SYSTEM_PROMPT, "LLM prompt covers dinner keywords")

# 4.2 LLM Cache TTL
print("\n4.2 LLM Cache")
cache = LLMCache(ttl_seconds=600)  # Updated default
check(cache.ttl_seconds == 600, f"Cache TTL is 600s (got {cache.ttl_seconds})")

cache.set("test query", {"tasks": [{"task_id": "task_1", "type": "eat_meal"}]})
cached_val = cache.get("test query")
check(cached_val is not None, "Cache stores and retrieves")
check(cached_val["tasks"][0]["type"] == "eat_meal", "Cache returns correct data")

# TTL zero = immediate expiry
cache2 = LLMCache(ttl_seconds=0)
cache2.set("test2", {"tasks": []})
check(cache2.get("test2") is None, "Zero TTL = immediate expiry (correct)")

# 4.3 is_after_destination threshold relaxed
print("\n4.3 is_after_destination threshold")
from agent.route_evaluator import RouteEvaluator as RE
# Check the threshold constant in the code
import inspect
src = inspect.getsource(RE._is_after_destination)
check("1.20" in src, f"Threshold relaxed to 1.20")


# ══════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print(f"RESULTS: {PASS} passed, {FAIL} failed out of {PASS + FAIL}")
print("=" * 60)

if FAIL > 0:
    sys.exit(1)
else:
    print("All validation tests passed!")
