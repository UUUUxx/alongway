from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import ensure_schema
from app.routers import (
    admin,
    deal_admin,
    health,
    internal_deals,
    internal_pois,
    internal_route,
    plan,
    poi_admin,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database tables on startup."""
    ensure_schema()
    yield


app = FastAPI(title="Along-way Backend", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://localhost:8001",  # Agent service
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# All routers
app.include_router(health.router)
app.include_router(plan.router)
app.include_router(internal_pois.router)
app.include_router(internal_deals.router)
app.include_router(internal_route.router)
app.include_router(poi_admin.router)
app.include_router(deal_admin.router)
app.include_router(admin.router)
