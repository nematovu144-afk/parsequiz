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

from app.parsers.base import RichParagraph

# ── Regex inventory ──────────────────────────────────────────

# Matches "1.", "2)", "A)", "a.", "A.", etc. at the start of a line.
# Includes S/V alongside A-D: Hemis-style Uzbek quiz banks commonly letter
# options A) V) S) D) instead of A) B) C) D).
RE_OPTION_PREFIX = re.compile(
    r"^(?P<prefix>[A-DSVa-dsv1-9][.)]\s*)"  # letter/digit + separator
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

# Line-delimited test-bank format (common export from Hemis and similar
# university LMS systems): options are separated by a line of only "="
# characters, questions by a line of only "+" characters, and the correct
# option is prefixed with "#". e.g.:
#   Question text?
#   ====
#   #correct option
#   ====
#   wrong option
#   ++++
RE_OPTION_SEP = re.compile(r"^={2,}$")
RE_QUESTION_SEP = re.compile(r"^\+{2,}$")


@dataclass
class ParsedOption:
    text: str
    is_correct: bool = False


@dataclass
class RawQuestion:
    """An intermediate representation before final normalisation."""
    question_text: str = ""
    options: list[ParsedOption] = field(default_factory=list)
    explanation: str | None = None


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
    if _looks_line_delimited(paragraphs):
        return _split_line_delimited(paragraphs, mode)

    questions: list[RawQuestion] = []
    current_q: RawQuestion | None = None
    # Tracks whether current_q was opened by a real question header (numbered
    # or ending in "?") rather than by stray leading text (e.g. a document
    # title) — only explicit questions are allowed to be flushed with no
    # options, so a title line can't surface as a bogus empty "question".
    current_q_explicit = False

    def _should_flush(q: RawQuestion | None) -> bool:
        return bool(q) and bool(q.options or (current_q_explicit and q.question_text))

    for para in paragraphs:
        plain = para.plain_text
        if not plain:
            continue

        # ── Is this line a new question header? ──────────────
        if _is_question_line(plain, para):
            if _should_flush(current_q):
                questions.append(current_q)
            q_text = RE_QUESTION_NUM.sub("", plain).strip()
            current_q = RawQuestion(question_text=q_text)
            current_q_explicit = True
            continue

        # ── Is this an option line? ──────────────────────────
        opt = _try_parse_option(plain, para, mode, has_open_question=current_q is not None)
        if opt is not None:
            if current_q is None:
                # Options appearing before any question — create placeholder
                current_q = RawQuestion()
                current_q_explicit = False
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
            # Floating text before any question (e.g. a document title) —
            # stashed on a placeholder that gets discarded at the next
            # flush point unless it later gains real options.
            current_q = RawQuestion(question_text=plain)
            current_q_explicit = False

    # Flush last question
    if _should_flush(current_q):
        questions.append(current_q)

    return questions


# ── Line-delimited format (Hemis-style "====" / "++++") ────────


def _looks_line_delimited(paragraphs: list[RichParagraph]) -> bool:
    """Detect the '====' / '++++' structural format before falling back
    to the generic per-line heuristic parser above. A bare line of 2+ "="
    characters essentially never occurs in genuine question/option prose,
    so two or more occurrences alone are a reliable signal -- even for a
    single-question document with no '++++' separator at all."""
    opt_count = sum(1 for p in paragraphs if RE_OPTION_SEP.match(p.plain_text))
    return opt_count >= 2


def _split_line_delimited(
    paragraphs: list[RichParagraph],
    mode: str,
) -> list[RawQuestion]:
    """Split a '====' (option separator) / '++++' (question separator)
    document into RawQuestions. The text before the first '====' in each
    block is the question; each following segment is one option, marked
    correct if it starts with a recognised symbol (default: '#')."""
    questions: list[RawQuestion] = []
    current_q: RawQuestion | None = None
    seg_lines: list[str] = []
    in_options = False

    def flush() -> None:
        nonlocal seg_lines, current_q
        text = " ".join(seg_lines).strip()
        seg_lines = []
        if not text:
            return
        if current_q is None:
            current_q = RawQuestion()
        if not in_options:
            current_q.question_text = (
                f"{current_q.question_text} {text}".strip()
                if current_q.question_text else text
            )
            return
        is_correct = False
        clean = text
        sym_match = RE_CORRECT_SYMBOL.match(clean)
        if sym_match:
            if _marker_matches_mode(sym_match.group("marker"), mode):
                is_correct = True
            clean = clean[sym_match.end():].strip()
        if clean:
            current_q.options.append(ParsedOption(text=clean, is_correct=is_correct))

    def finalize() -> None:
        nonlocal current_q, in_options
        if current_q and (current_q.question_text or current_q.options):
            questions.append(current_q)
        current_q = None
        in_options = False

    for para in paragraphs:
        text = para.plain_text
        if RE_QUESTION_SEP.match(text):
            flush()
            finalize()
            continue
        if RE_OPTION_SEP.match(text):
            flush()
            in_options = True
            continue
        seg_lines.append(text)

    flush()
    finalize()
    return questions


# ── Internals ────────────────────────────────────────────────


def _is_question_line(text: str, para: RichParagraph) -> bool:
    """Heuristic: a line is a question header if it starts with a question
    number OR ends with '?' and doesn't look like an option."""
    if RE_QUESTION_NUM.match(text):
        return True
    # Lines ending with '?' that are NOT short option-like strings
    return text.rstrip().endswith("?") and len(text) > 15


def _try_parse_option(
    text: str,
    para: RichParagraph,
    mode: str,
    has_open_question: bool,
) -> ParsedOption | None:
    """Try to interpret the line as an answer option.

    Returns None if it doesn't look like an option. ``has_open_question``
    gates the style-only (bold/underline, no letter prefix) heuristic: a
    lone bold/underlined line before any question has opened is far more
    likely to be a document title or heading than a correct answer, so it
    is never auto-promoted to an option in that state.
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
        # (unless we detect bold/underline marking, and a question is
        # already open — see has_open_question note above)
        if not has_open_question:
            return None
        if mode in ("auto", "bold") and para.has_any_bold():
            return ParsedOption(text=clean.strip(), is_correct=True)
        if mode in ("auto", "underline") and para.has_any_underline():
            return ParsedOption(text=clean.strip(), is_correct=True)
        return None

    clean = clean.strip()
    if not clean:
        return None

    # Step 3: Style-based correct detection (when no symbol was found)
    if not is_correct and (
        (mode in ("auto", "bold") and para.has_any_bold())
        or (mode in ("auto", "underline") and para.has_any_underline())
    ):
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
