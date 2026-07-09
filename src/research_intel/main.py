from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from research_intel.api.routes import router
from research_intel.config import get_settings
from research_intel.db import SessionLocal, init_db
from research_intel.services.factory import build_services
from research_intel.services.scheduler import IntelligenceScheduler

STATIC_DIR = Path(__file__).parent / "web" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    init_db()
    services = build_services(settings)
    scheduler = IntelligenceScheduler(
        settings, SessionLocal, services.ingestion, services.daily_intelligence
    )
    scheduler.start()
    app.state.services = services
    app.state.scheduler = scheduler
    try:
        yield
    finally:
        scheduler.stop()


app = FastAPI(
    title="Research Intelligence Platform",
    version="0.1.0",
    description="Domain-aware multi-source research ingestion and evidence-backed recommendation API.",
    lifespan=lifespan,
)

app.include_router(router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")
