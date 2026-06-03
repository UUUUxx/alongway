"""
FastAPI application entry point.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import get_engine
from app.models import Base
from app.routers import (
    admin,
    deal_admin,
    geocode,
    health,
    internal_deals,
    internal_pois,
    internal_route,
    map_config,
    plan,
    poi_admin,
)

# Configure logging based on DEBUG setting
settings = get_settings()
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database tables on startup."""
    logger.info("Starting Along-way Backend v0.2.0 (DEBUG=%s)", settings.debug)
    Base.metadata.create_all(bind=get_engine())
    yield
    logger.info("Shutting down")


app = FastAPI(title="Along-way Backend", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://localhost:8001",  # Agent service
        "null",  # Local file:// frontend during quick demos
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# All routers
app.include_router(health.router)
app.include_router(plan.router)
app.include_router(geocode.router)
app.include_router(internal_pois.router)
app.include_router(internal_deals.router)
app.include_router(internal_route.router)
app.include_router(map_config.router)
app.include_router(poi_admin.router)
app.include_router(deal_admin.router)
app.include_router(admin.router)

logger.info("All routers registered")
