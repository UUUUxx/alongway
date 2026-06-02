from __future__ import annotations

from fastapi import FastAPI

from agent.call_logger import log_call
from agent.backend_client import HttpBackendClient, MockBackendClient
from agent.config import load_settings
from agent.haversine_filter import HaversinePreFilter
from agent.llm_cache import LLMCache
from agent.llm_client import StepFunLLMClient
from agent.models import PlanRequest, PlanResponse
from agent.planner_agent import PlanAgent


def create_app() -> FastAPI:
    settings = load_settings()

    # ── Backend client ──
    backend_client = (
        MockBackendClient()
        if settings.use_mock_backend
        else HttpBackendClient(
            base_url=settings.backend_base_url,
            timeout_seconds=settings.request_timeout_seconds,
            use_connection_pool=settings.connection_pool_enabled,
        )
    )

    # ── LLM client ──
    llm_client = StepFunLLMClient(
        api_key=settings.stepfun_api_key,
        base_url=settings.stepfun_base_url,
        model=settings.stepfun_model,
        timeout_seconds=settings.stepfun_timeout_seconds,
    )

    # ── v2: optional optimizations ──
    llm_cache = LLMCache(
        enabled=settings.llm_cache_enabled,
        ttl_seconds=settings.llm_cache_ttl_seconds,
    ) if settings.route_optimization_v2 else None

    haversine_filter = HaversinePreFilter(
        top_k=settings.haversine_topk,
    ) if settings.route_optimization_v2 else None

    plan_agent = PlanAgent(
        backend_client=backend_client,
        llm_client=llm_client,
        llm_timeout_seconds=settings.stepfun_timeout_seconds,
        poi_timeout_seconds=settings.poi_timeout_seconds,
        route_timeout_seconds=settings.route_timeout_seconds,
        v2_enabled=settings.route_optimization_v2,
        haversine_filter=haversine_filter,
        llm_cache=llm_cache,
        rule_first=settings.llm_rule_first,
    )

    app = FastAPI(title="Alongway Agent", version="0.2.0-v2")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/agent/plan", response_model=PlanResponse)
    async def plan(request: PlanRequest) -> PlanResponse:
        response = await plan_agent.plan(request)
        log_call("agent.plan.result", request=request, result=response)
        return response

    return app


app = create_app()
