"""Unit tests for the SQLite-backed job registry."""

from uuid import uuid4

import pytest

from app.core import job_store
from app.schemas.quiz import JobStatus, Question


@pytest.mark.asyncio
async def test_create_and_get_job(test_db):
    job = await job_store.create_job(filename="quiz.txt", delimiter_mode="auto")

    fetched = await job_store.get_job(job.job_id)

    assert fetched is not None
    assert fetched.job_id == job.job_id
    assert fetched.filename == "quiz.txt"
    assert fetched.status == JobStatus.PENDING
    assert fetched.questions == []


@pytest.mark.asyncio
async def test_get_job_missing_returns_none(test_db):
    assert await job_store.get_job(uuid4()) is None


@pytest.mark.asyncio
async def test_update_job_persists_questions(test_db):
    job = await job_store.create_job(filename="quiz.txt")
    questions = [Question(question="2+2?", options=["3", "4"], correct_option_index=1)]

    await job_store.update_job(
        job.job_id, status=JobStatus.DONE, progress=1.0, questions=questions
    )
    fetched = await job_store.get_job(job.job_id)

    assert fetched.status == JobStatus.DONE
    assert fetched.progress == 1.0
    assert len(fetched.questions) == 1
    assert fetched.questions[0].question == "2+2?"
    assert fetched.questions[0].correct_option_index == 1


@pytest.mark.asyncio
async def test_fail_job_sets_error_and_status(test_db):
    job = await job_store.create_job(filename="quiz.txt")

    await job_store.fail_job(job.job_id, "boom")
    fetched = await job_store.get_job(job.job_id)

    assert fetched.status == JobStatus.FAILED
    assert fetched.error == "boom"


@pytest.mark.asyncio
async def test_update_job_missing_job_is_a_noop(test_db):
    # Should not raise even though no such job exists.
    await job_store.update_job(uuid4(), status=JobStatus.PROCESSING)
