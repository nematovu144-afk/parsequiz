"""Domain models shared across the entire application."""

from __future__ import annotations

from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

# ── Question schema ──────────────────────────────────────────


class ValidationFlag(str, Enum):
    """Flags attached to questions that need human review."""

    MISSING_CORRECT = "missing_correct_answer"
    TOO_FEW_OPTIONS = "fewer_than_2_options"
    EMPTY_QUESTION = "empty_question_text"
    DUPLICATE_OPTIONS = "duplicate_options"
    MULTIPLE_CORRECT = "multiple_correct_answers"
    PARSE_ARTIFACT = "possible_parse_artifact"


class Question(BaseModel):
    """A single parsed quiz question."""

    id: UUID = Field(default_factory=uuid4)
    question: str = ""
    options: list[str] = Field(default_factory=list)
    correct_option_index: int | None = None
    explanation: str | None = None
    flags: list[ValidationFlag] = Field(default_factory=list)


# ── Job lifecycle ────────────────────────────────────────────


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class ParseJob(BaseModel):
    """Tracks an async parse job."""

    job_id: UUID = Field(default_factory=uuid4)
    filename: str = ""
    status: JobStatus = JobStatus.PENDING
    progress: float = 0.0  # 0-1
    questions: list[Question] = Field(default_factory=list)
    error: str | None = None
    delimiter_mode: str = "auto"  # "auto" | "bold" | "plus" | …


# ── API payloads ─────────────────────────────────────────────


class UploadResponse(BaseModel):
    job_id: UUID
    filename: str
    status: JobStatus


class ReparseRequest(BaseModel):
    delimiter_mode: str = "auto"


class ExportRequest(BaseModel):
    questions: list[Question]
    format: str = "json"  # "json" | "xlsx" | "csv"
