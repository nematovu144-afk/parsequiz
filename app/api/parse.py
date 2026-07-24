"""GET /api/parse/{job_id} — poll job status and retrieve results."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.core.job_store import get_job
from app.schemas.quiz import ParseJob

router = APIRouter(tags=["parse"])


@router.get("/parse/{job_id}", response_model=ParseJob)
async def get_parse_status(job_id: UUID):
    """Poll the parsing job.  Returns questions when status == 'done'."""
    job = await get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
