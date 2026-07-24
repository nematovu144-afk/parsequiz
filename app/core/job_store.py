"""SQLite-backed job registry (via SQLAlchemy async engine).

Restart-durable: unlike the old in-memory dict, job state survives
server restarts/reloads and would be safe across multiple workers.
"""

from __future__ import annotations

from uuid import UUID

from app.db import base as db_base
from app.db.models import JobRecord
from app.schemas.quiz import JobStatus, ParseJob


def _row_to_job(row: JobRecord) -> ParseJob:
    return ParseJob.model_validate(
        {
            "job_id": row.job_id,
            "filename": row.filename,
            "status": row.status,
            "progress": row.progress,
            "questions": row.questions,
            "error": row.error,
            "delimiter_mode": row.delimiter_mode,
        }
    )


def _serialize(key: str, value: object) -> object:
    if key == "status" and isinstance(value, JobStatus):
        return value.value
    if key == "questions":
        return [q.model_dump(mode="json") for q in value]  # type: ignore[union-attr]
    return value


async def create_job(filename: str, delimiter_mode: str = "auto") -> ParseJob:
    job = ParseJob(filename=filename, delimiter_mode=delimiter_mode)
    async with db_base.async_session_factory() as session:
        session.add(
            JobRecord(
                job_id=str(job.job_id),
                filename=job.filename,
                status=job.status.value,
                progress=job.progress,
                questions=[],
                error=job.error,
                delimiter_mode=job.delimiter_mode,
            )
        )
        await session.commit()
    return job


async def get_job(job_id: UUID) -> ParseJob | None:
    async with db_base.async_session_factory() as session:
        row = await session.get(JobRecord, str(job_id))
        return _row_to_job(row) if row else None


async def update_job(job_id: UUID, **kwargs) -> None:
    async with db_base.async_session_factory() as session:
        row = await session.get(JobRecord, str(job_id))
        if row is None:
            return
        for key, value in kwargs.items():
            setattr(row, key, _serialize(key, value))
        await session.commit()


async def fail_job(job_id: UUID, error: str) -> None:
    await update_job(job_id, status=JobStatus.FAILED, error=error)
