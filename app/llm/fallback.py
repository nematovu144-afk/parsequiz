"""LLM-based fallback extraction for messy / non-standard documents.

Supports OpenAI, Anthropic, and Gemini via plain httpx calls (no SDK
dependencies).  Only called when regex parsing flags > 40 % of questions.
"""

from __future__ import annotations

import json
import logging
from uuid import uuid4

import httpx

from app.config import settings
from app.schemas.quiz import Question

logger = logging.getLogger(__name__)

# ── The master extraction prompt ─────────────────────────────

SYSTEM_PROMPT = """\
You are a precise document parser that converts educational test/exam text \
into structured JSON.  You never invent questions — you only extract what \
exists in the source.

RULES:
1. Return ONLY a JSON array — no markdown fences, no commentary.
2. Each element must have exactly these fields:
   {
     "question": "<full question text>",
     "options": ["A text", "B text", "C text", "D text"],
     "correct_option_index": <0-based int | null if undetectable>,
     "explanation": "<string | null>"
   }
3. Detect the correct answer from ANY of these markers in the source:
   • A leading +, *, or # symbol before the option
   • [x] or [X] checkbox prefix
   • **Bold** or UPPERCASE styling
   • Underlined text
   • An answer key section (e.g. "Answers: 1-B, 2-A, …")
   • An explicit label like "✓", "correct", "to'g'ri", "правильный"
4. Preserve the original language — do NOT translate.
5. Strip marker symbols (+, *, #, [x]) from the option text itself.
6. If a question has an explanation or "izoh" / "пояснение", put it in \
   the "explanation" field.
7. If you cannot determine the correct answer, set correct_option_index to null.
8. Ignore headers, footers, page numbers, watermarks, and decorative text.
9. If options use letters (A/B/C/D) or numbers (1/2/3/4), normalise to a \
   plain list — do NOT include the prefix in the option text.
10. Handle multi-line questions: concatenate continuation lines into a single \
    question string.
"""

USER_PROMPT_TEMPLATE = """\
Extract every question from the following exam document text.  \
Return the result as a JSON array following the schema in your instructions.

--- DOCUMENT START ---
{text}
--- DOCUMENT END ---
"""

# Maximum characters to send (protect against token blowout)
MAX_TEXT_CHARS = 60_000


async def llm_extract(full_text: str) -> list[Question]:
    """Send document text to the configured LLM and parse the response."""
    provider = settings.llm_provider
    if provider == "none":
        return []

    # Truncate if enormous
    text = full_text[:MAX_TEXT_CHARS]
    user_msg = USER_PROMPT_TEMPLATE.format(text=text)

    raw_json = await _call_llm(provider, user_msg)
    return _parse_llm_response(raw_json)


# ── Provider dispatch ────────────────────────────────────────


async def _call_llm(provider: str, user_msg: str) -> str:
    """Route to the right provider and return the raw text response."""
    async with httpx.AsyncClient(timeout=120) as client:
        if provider == "openai":
            return await _call_openai(client, user_msg)
        elif provider == "anthropic":
            return await _call_anthropic(client, user_msg)
        elif provider == "gemini":
            return await _call_gemini(client, user_msg)
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")


async def _call_openai(client: httpx.AsyncClient, user_msg: str) -> str:
    resp = await client.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.openai_api_key}"},
        json={
            "model": settings.llm_model,
            "temperature": 0.0,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
        },
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


async def _call_anthropic(client: httpx.AsyncClient, user_msg: str) -> str:
    resp = await client.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": settings.llm_model or "claude-sonnet-4-6",
            "max_tokens": 8192,
            "temperature": 0.0,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_msg}],
        },
    )
    resp.raise_for_status()
    blocks = resp.json().get("content", [])
    return "".join(b["text"] for b in blocks if b.get("type") == "text")


async def _call_gemini(client: httpx.AsyncClient, user_msg: str) -> str:
    model = settings.llm_model or "gemini-1.5-flash"
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
        f":generateContent?key={settings.gemini_api_key}"
    )
    resp = await client.post(
        url,
        json={
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"parts": [{"text": user_msg}]}],
            "generationConfig": {"temperature": 0.0},
        },
    )
    resp.raise_for_status()
    parts = resp.json()["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts)


# ── Response parsing ─────────────────────────────────────────


def _parse_llm_response(raw: str) -> list[Question]:
    """Parse the LLM's JSON array into Question objects."""
    # Strip markdown code fences if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.error("LLM returned invalid JSON:\n%.500s", cleaned)
        return []

    if not isinstance(data, list):
        data = [data]

    questions: list[Question] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            q = Question(
                id=uuid4(),
                question=str(item.get("question", "")),
                options=[str(o) for o in item.get("options", [])],
                correct_option_index=item.get("correct_option_index"),
                explanation=item.get("explanation"),
            )
            questions.append(q)
        except Exception:
            logger.warning("Skipping malformed LLM question: %s", item)
    return questions
