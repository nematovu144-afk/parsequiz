"""Thread-safe in-memory job registry.

For production, replace with Redis or a database-backed store.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from app.schemas.quiz import JobStatus, ParseJob

_jobs: dict[UUID, ParseJob] = {}
_lock = asyncio.Lock()


async def create_job(filename: str, delimiter_mode: str = "auto") -> ParseJob:
    job = ParseJob(filename=filename, delimiter_mode=delimiter_mode)
    async with _lock:
        _jobs[job.job_id] = job
    return job


async def get_job(job_id: UUID) -> ParseJob | None:
    return _jobs.get(job_id)


async def update_job(job_id: UUID, **kwargs) -> None:
    async with _lock:
        job = _jobs.get(job_id)
        if job:
            for k, v in kwargs.items():
                setattr(job, k, v)


async def fail_job(job_id: UUID, error: str) -> None:
    await update_job(job_id, status=JobStatus.FAILED, error=error)
