"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import export, parse, upload
from app.config import settings  # noqa: F401 — force early init
from app.db.base import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="Quiz Parser API",
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

# ── API routers ──────────────────────────────────────────────
app.include_router(upload.router, prefix="/api")
app.include_router(parse.router, prefix="/api")
app.include_router(export.router, prefix="/api")

# ── Serve frontend (static build) ───────────────────────────
# Uncomment after building the React app into frontend/dist:
# app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")
