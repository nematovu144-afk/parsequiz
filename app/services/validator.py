"""Structural validation: flag questions that need human review."""

from __future__ import annotations

from app.schemas.quiz import Question, ValidationFlag


def validate_questions(questions: list[Question]) -> list[Question]:
    """Mutate each question's ``flags`` list in-place and return the list."""
    for q in questions:
        q.flags = []

        # 1. Empty question text
        if not q.question.strip():
            q.flags.append(ValidationFlag.EMPTY_QUESTION)

        # 2. Fewer than 2 options
        if len(q.options) < 2:
            q.flags.append(ValidationFlag.TOO_FEW_OPTIONS)

        # 3. No correct answer selected
        no_correct = (
            q.correct_option_index is None
            or q.correct_option_index < 0
            or q.correct_option_index >= len(q.options)
        )
        if no_correct:
            q.flags.append(ValidationFlag.MISSING_CORRECT)

        # 4. Duplicate option texts (case-insensitive)
        lower_opts = [o.strip().lower() for o in q.options]
        if len(lower_opts) != len(set(lower_opts)):
            q.flags.append(ValidationFlag.DUPLICATE_OPTIONS)

        # 5. Residual parse artifacts (regex debris, stray symbols)
        for opt in q.options:
            if _looks_like_artifact(opt):
                q.flags.append(ValidationFlag.PARSE_ARTIFACT)
                break

    return questions


def _looks_like_artifact(text: str) -> bool:
    """Detect common parse debris: lone symbols, empty-ish strings."""
    stripped = text.strip()
    if not stripped:
        return True
    if stripped in ("+", "*", "#", "[x]", "[X]", "-"):
        return True
    return len(stripped) <= 1 and not stripped.isalnum()
