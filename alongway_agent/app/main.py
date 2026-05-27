from __future__ import annotations

from fastapi import FastAPI

from agent.backend_client import HttpBackendClient, MockBackendClient
from agent.config import load_settings
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
    plan_agent = PlanAgent(backend_client=backend_client)

    app = FastAPI(title="Alongway Agent", version="0.1.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/agent/plan", response_model=PlanResponse)
    async def plan(request: PlanRequest) -> PlanResponse:
        return await plan_agent.plan(request)

    return app


app = create_app()
