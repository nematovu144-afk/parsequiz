"""Correct-answer delimiter detection and question boundary splitting.

This module handles two orthogonal problems:
  1. Splitting raw paragraphs into (question, options[]) groups.
  2. Detecting which option is marked correct.

Supported correct-answer markers (in priority order):
  ── Symbol prefixes ──
  +  Option text           → the "+" prefix
  *  Option text           → the "*" prefix
  #  Option text           → the "#" prefix
  [x] Option text          → checkbox syntax

  ── Format styles ──
  **Bold text**            → bold runs (from docx/pdf metadata)
  __Underlined text__      → underline runs

  ── Structural prefixes ──
  A) / B) / 1. / a.        → used to number options (not correct markers
                              on their own — combined with +/* /bold)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from app.parsers.base import RichParagraph


# ── Regex inventory ──────────────────────────────────────────

# Matches "1.", "2)", "A)", "a.", "A.", etc. at the start of a line
RE_OPTION_PREFIX = re.compile(
    r"^(?P<prefix>[A-Da-d1-9][.)]\s*)"  # letter/digit + separator
)

# Question-number prefix: "1.", "12.", "Q1.", "Savol 1:", "#1", etc.
RE_QUESTION_NUM = re.compile(
    r"^(?:(?:Q|Savol|Вопрос|Question)\s*)?#?\d{1,4}[.):]\s*",
    re.IGNORECASE,
)

# Correct-answer symbol prefix: +, *, #, [x], [X]
RE_CORRECT_SYMBOL = re.compile(
    r"^(?P<marker>[+*#]|\[x\]|\[X\])\s*"
)


@dataclass
class ParsedOption:
    text: str
    is_correct: bool = False


@dataclass
class RawQuestion:
    """An intermediate representation before final normalisation."""
    question_text: str = ""
    options: list[ParsedOption] = field(default_factory=list)
    explanation: Optional[str] = None


# ── Public API ───────────────────────────────────────────────


def split_into_questions(
    paragraphs: list[RichParagraph],
    mode: str = "auto",
) -> list[RawQuestion]:
    """Convert a flat list of paragraphs into structured RawQuestion objects.

    ``mode`` controls how correct answers are detected:
      - "auto"      — try symbol prefixes first, fall back to bold/underline
      - "bold"      — only use bold styling
      - "underline" — only use underline styling
      - "plus"      — only the '+' symbol prefix
      - "star"      — only the '*' symbol prefix
      - "hash"      — only the '#' symbol prefix
      - "checkbox"  — only [x] syntax
    """
    questions: list[RawQuestion] = []
    current_q: RawQuestion | None = None

    for para in paragraphs:
        plain = para.plain_text
        if not plain:
            continue

        # ── Is this line a new question header? ──────────────
        if _is_question_line(plain, para):
            if current_q and (current_q.question_text or current_q.options):
                questions.append(current_q)
            q_text = RE_QUESTION_NUM.sub("", plain).strip()
            current_q = RawQuestion(question_text=q_text)
            continue

        # ── Is this an option line? ──────────────────────────
        opt = _try_parse_option(plain, para, mode)
        if opt is not None:
            if current_q is None:
                # Options appearing before any question — create placeholder
                current_q = RawQuestion()
            current_q.options.append(opt)
            continue

        # ── Otherwise: continuation text ─────────────────────
        if current_q is not None:
            # Could be multi-line question text or explanation
            if current_q.options:
                # Text after options → likely explanation
                expl = plain
                if expl.lower().startswith(("explanation:", "izoh:", "пояснение:")):
                    expl = re.sub(r"^[^:]+:\s*", "", expl)
                current_q.explanation = (
                    f"{current_q.explanation} {expl}" if current_q.explanation else expl
                )
            else:
                # Continuation of question text
                current_q.question_text += " " + plain
        else:
            # Floating text before any question — start a new one
            current_q = RawQuestion(question_text=plain)

    # Flush last question
    if current_q and (current_q.question_text or current_q.options):
        questions.append(current_q)

    return questions


# ── Internals ────────────────────────────────────────────────


def _is_question_line(text: str, para: RichParagraph) -> bool:
    """Heuristic: a line is a question header if it starts with a question
    number OR ends with '?' and doesn't look like an option."""
    if RE_QUESTION_NUM.match(text):
        return True
    # Lines ending with '?' that are NOT short option-like strings
    if text.rstrip().endswith("?") and len(text) > 15:
        return True
    return False


def _try_parse_option(
    text: str,
    para: RichParagraph,
    mode: str,
) -> ParsedOption | None:
    """Try to interpret the line as an answer option.

    Returns None if it doesn't look like an option.
    """
    is_correct = False
    clean = text

    # Step 1: Check for symbol-prefix correct markers (+, *, #, [x])
    sym_match = RE_CORRECT_SYMBOL.match(clean)
    if sym_match:
        marker = sym_match.group("marker")
        if _marker_matches_mode(marker, mode):
            is_correct = True
        clean = clean[sym_match.end():]

    # Step 2: Strip structural prefix (A), B., 1., etc.)
    pfx_match = RE_OPTION_PREFIX.match(clean)
    if pfx_match:
        clean = clean[pfx_match.end():]
    elif not sym_match:
        # No symbol marker and no structural prefix — not an option line
        # (unless we detect bold/underline marking)
        if mode in ("auto", "bold") and para.has_any_bold():
            return ParsedOption(text=clean.strip(), is_correct=True)
        if mode in ("auto", "underline") and para.has_any_underline():
            return ParsedOption(text=clean.strip(), is_correct=True)
        return None

    clean = clean.strip()
    if not clean:
        return None

    # Step 3: Style-based correct detection (when no symbol was found)
    if not is_correct:
        if mode in ("auto", "bold") and para.has_any_bold():
            is_correct = True
        elif mode in ("auto", "underline") and para.has_any_underline():
            is_correct = True

    return ParsedOption(text=clean, is_correct=is_correct)


def _marker_matches_mode(marker: str, mode: str) -> bool:
    """Check if a symbol marker is active under the current detection mode."""
    if mode == "auto":
        return True
    mapping = {
        "plus": "+",
        "star": "*",
        "hash": "#",
        "checkbox": "[x]",
    }
    expected = mapping.get(mode)
    if expected:
        return marker.lower() == expected.lower()
    return False
