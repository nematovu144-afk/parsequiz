"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api import export, parse, upload
from app.config import settings  # noqa: F401 — force early init
from app.core.rate_limit import limiter
from app.db.base import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="ParseQuiz API",
    version="1.0.0",
    description="Ingest .docx/.pdf/.txt test files → structured quiz JSON",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ── API routers ──────────────────────────────────────────────
app.include_router(upload.router, prefix="/api")
app.include_router(parse.router, prefix="/api")
app.include_router(export.router, prefix="/api")

# ── Serve frontend ───────────────────────────────────────────
# Plain HTML/JS, no build step — mounted last so it doesn't shadow /api routes.
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
