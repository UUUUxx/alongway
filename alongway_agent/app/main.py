from __future__ import annotations

from fastapi import FastAPI

from agent.call_logger import log_call
from agent.backend_client import HttpBackendClient, MockBackendClient
from agent.config import load_settings
from agent.llm_client import StepFunLLMClient
from agent.models import PlanRequest, PlanResponse
from agent.planner_agent import PlanAgent


def create_app() -> FastAPI:
    settings = load_settings()
    backend_client = (
        MockBackendClient()
        if settings.use_mock_backend
        else HttpBackendClient(
            base_url=settings.backend_base_url,
            timeout_seconds=settings.request_timeout_seconds,
        )
    )
    llm_client = StepFunLLMClient(
        api_key=settings.stepfun_api_key,
        base_url=settings.stepfun_base_url,
        model=settings.stepfun_model,
        timeout_seconds=settings.stepfun_timeout_seconds,
    )
    plan_agent = PlanAgent(
        backend_client=backend_client,
        llm_client=llm_client,
        llm_timeout_seconds=settings.stepfun_timeout_seconds,
        poi_timeout_seconds=settings.poi_timeout_seconds,
        route_timeout_seconds=settings.route_timeout_seconds,
    )

    app = FastAPI(title="Alongway Agent", version="0.1.0")

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
