"""POST /api/upload — accept a file and start async parsing."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from app.config import settings
from app.core.exceptions import ParseError
from app.core.job_store import create_job, fail_job, update_job
from app.schemas.quiz import JobStatus, UploadResponse
from app.services.orchestrator import run_pipeline

router = APIRouter(tags=["upload"])

ALLOWED_EXTENSIONS = {".docx", ".pdf", ".txt"}


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    delimiter_mode: str = Form("auto"),
):
    """Upload a .docx/.pdf/.txt file and receive a job_id to poll."""

    # ── Validate extension ───────────────────────────────────
    filename = file.filename or "unknown"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {ALLOWED_EXTENSIONS}",
        )

    # ── Validate size ────────────────────────────────────────
    contents = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {settings.max_upload_mb} MB limit.",
        )

    # ── Persist to temp dir ──────────────────────────────────
    job = await create_job(filename=filename, delimiter_mode=delimiter_mode)
    dest = settings.upload_dir / f"{job.job_id}{ext}"
    dest.write_bytes(contents)

    # ── Kick off background parse ────────────────────────────
    background_tasks.add_task(_parse_task, job.job_id, dest, delimiter_mode)

    return UploadResponse(
        job_id=job.job_id,
        filename=filename,
        status=JobStatus.PENDING,
    )


async def _parse_task(job_id, file_path: Path, delimiter_mode: str):
    """Background task that runs the full pipeline."""
    try:
        await update_job(job_id, status=JobStatus.PROCESSING, progress=0.1)
        questions = await run_pipeline(
            file_path,
            delimiter_mode=delimiter_mode,
            use_llm_fallback=(settings.llm_provider != "none"),
        )
        await update_job(
            job_id,
            status=JobStatus.DONE,
            progress=1.0,
            questions=questions,
        )
    except ParseError as exc:
        await fail_job(job_id, str(exc))
    except Exception as exc:
        await fail_job(job_id, f"Unexpected error: {exc}")
    finally:
        # Clean up temp file
        try:
            file_path.unlink(missing_ok=True)
        except OSError:
            pass
