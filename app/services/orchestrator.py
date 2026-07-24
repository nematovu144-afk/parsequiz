"""Pipeline orchestrator: file → paragraphs → raw questions → validated Questions.

Flow:
  1. Choose parser by extension
  2. Extract RichParagraphs
  3. Split into RawQuestion objects (delimiter.py)
  4. Normalise into Question schema objects
  5. Validate & flag
  6. (optional) LLM fallback if too many flags
"""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from app.core.exceptions import UnsupportedFormatError
from app.parsers.base import BaseParser
from app.parsers.delimiter import RawQuestion, split_into_questions
from app.parsers.docx_parser import DocxParser
from app.parsers.pdf_parser import PdfParser
from app.parsers.txt_parser import TxtParser
from app.schemas.quiz import Question, ValidationFlag
from app.services.validator import validate_questions

logger = logging.getLogger(__name__)

# ── Parser registry ──────────────────────────────────────────

PARSERS: dict[str, BaseParser] = {
    ".docx": DocxParser(),
    ".pdf": PdfParser(),
    ".txt": TxtParser(),
}


# ── Public entry point ───────────────────────────────────────


async def run_pipeline(
    file_path: Path,
    delimiter_mode: str = "auto",
    use_llm_fallback: bool = True,
) -> list[Question]:
    """Full extraction pipeline.  Returns validated Question list."""

    ext = file_path.suffix.lower()
    parser = PARSERS.get(ext)
    if parser is None:
        raise UnsupportedFormatError(f"Unsupported file type: {ext}")

    # Step 1 — extract styled paragraphs
    paragraphs = await parser.extract(file_path)
    logger.info("Extracted %d paragraphs from %s", len(paragraphs), file_path.name)

    if not paragraphs:
        return []

    # Step 2 — split into raw questions
    raw_questions = split_into_questions(paragraphs, mode=delimiter_mode)
    logger.info("Split into %d raw questions", len(raw_questions))

    # Step 3 — normalise into schema
    questions = [_normalise(rq) for rq in raw_questions]

    # Step 4 — validate
    questions = validate_questions(questions)

    # Step 5 — LLM fallback if regex parsing looks poor
    if use_llm_fallback and _needs_llm_rescue(questions):
        logger.info("Too many flags — attempting LLM fallback")
        try:
            from app.llm.fallback import llm_extract

            full_text = "\n".join(p.plain_text for p in paragraphs)
            llm_questions = await llm_extract(full_text)
            if llm_questions and len(llm_questions) >= len(questions) * 0.5:
                questions = validate_questions(llm_questions)
                logger.info("LLM fallback produced %d questions", len(questions))
        except Exception:
            logger.exception("LLM fallback failed — returning regex results")

    return questions


# ── Normalisation ────────────────────────────────────────────


def _normalise(rq: RawQuestion) -> Question:
    """Convert a RawQuestion (from delimiter.py) into a Question schema."""
    correct_index: int | None = None
    option_texts: list[str] = []

    for i, opt in enumerate(rq.options):
        option_texts.append(opt.text)
        if opt.is_correct:
            correct_index = i  # last one wins if multiple are marked

    return Question(
        id=uuid4(),
        question=rq.question_text.strip(),
        options=option_texts,
        correct_option_index=correct_index,
        explanation=rq.explanation,
    )


def _needs_llm_rescue(questions: list[Question]) -> bool:
    """Decide whether the regex parse is too noisy to trust."""
    if not questions:
        return True  # got nothing — try LLM

    flagged = sum(1 for q in questions if q.flags)
    ratio = flagged / len(questions)
    return ratio > 0.4  # more than 40 % flagged → call for help
