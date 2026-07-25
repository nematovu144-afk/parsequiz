"""POST /api/upload — accept a file and start async parsing."""

import logging
import time
from contextlib import suppress
from pathlib import Path
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)

from app.config import settings
from app.core.exceptions import ParseError
from app.core.job_store import create_job, fail_job, get_job, update_job
from app.core.rate_limit import limiter
from app.schemas.quiz import JobStatus, ReparseRequest, UploadResponse
from app.services.orchestrator import run_pipeline

router = APIRouter(tags=["upload"])
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".docx", ".pdf", ".txt"}

# Uploaded files are kept after parsing (not deleted) so /api/reparse can
# re-run the pipeline with a different delimiter_mode without re-uploading.
# This sweep bounds disk growth from files nobody ever comes back to.
STALE_UPLOAD_MAX_AGE_SECONDS = 24 * 3600


def _cleanup_stale_uploads() -> None:
    now = time.time()
    with suppress(OSError):
        for f in settings.upload_dir.iterdir():
            with suppress(OSError):
                if f.is_file() and (now - f.stat().st_mtime) > STALE_UPLOAD_MAX_AGE_SECONDS:
                    f.unlink(missing_ok=True)


@router.post("/upload", response_model=UploadResponse)
@limiter.limit("10/minute")
async def upload_file(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    delimiter_mode: str = Form("auto"),
):
    """Upload a .docx/.pdf/.txt file and receive a job_id to poll."""
    _cleanup_stale_uploads()

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


@router.post("/reparse/{job_id}", response_model=UploadResponse)
@limiter.limit("10/minute")
async def reparse_file(
    request: Request,
    job_id: UUID,
    body: ReparseRequest,
    background_tasks: BackgroundTasks,
):
    """Re-run parsing on an already-uploaded file with a different
    delimiter_mode, without requiring the client to re-upload it."""
    job = await get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    ext = Path(job.filename).suffix.lower()
    file_path = settings.upload_dir / f"{job_id}{ext}"
    if not file_path.exists():
        raise HTTPException(
            status_code=410,
            detail="Original file is no longer available — please upload it again.",
        )

    await update_job(
        job_id,
        status=JobStatus.PENDING,
        progress=0.0,
        questions=[],
        error=None,
        delimiter_mode=body.delimiter_mode,
    )
    background_tasks.add_task(_parse_task, job_id, file_path, body.delimiter_mode)

    return UploadResponse(job_id=job_id, filename=job.filename, status=JobStatus.PENDING)


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
    except Exception:
        # Full detail goes to the server log only — the exception text can
        # contain internal paths/library internals we don't want to hand
        # back to an anonymous client.
        logger.exception("Unexpected error parsing job %s", job_id)
        await fail_job(job_id, "Hujjatni tahlil qilishda kutilmagan xatolik yuz berdi.")
