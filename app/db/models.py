"""ORM models. One table: a parse job and its (possibly empty) questions."""

from __future__ import annotations

from sqlalchemy import JSON, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class JobRecord(Base):
    __tablename__ = "jobs"

    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    filename: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String, default="pending")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    questions: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    delimiter_mode: Mapped[str] = mapped_column(String, default="auto")
