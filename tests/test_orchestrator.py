"""Integration tests for the full parse pipeline (extract -> split -> validate)."""

import pytest

from app.core.exceptions import UnsupportedFormatError
from app.services.orchestrator import run_pipeline

SAMPLE = """\
1. What is 2+2?
A) 3
+ B) 4
C) 5

2. Capital of France?
A) London
* B) Paris
C) Berlin
"""


@pytest.mark.asyncio
async def test_run_pipeline_txt_end_to_end(tmp_path):
    path = tmp_path / "quiz.txt"
    path.write_text(SAMPLE, encoding="utf-8")

    questions = await run_pipeline(path, delimiter_mode="auto", use_llm_fallback=False)

    assert len(questions) == 2
    assert questions[0].question == "What is 2+2?"
    assert questions[0].options == ["3", "4", "5"]
    assert questions[0].correct_option_index == 1
    assert questions[0].flags == []

    assert questions[1].question == "Capital of France?"
    assert questions[1].correct_option_index == 1


@pytest.mark.asyncio
async def test_run_pipeline_unsupported_extension_raises(tmp_path):
    path = tmp_path / "quiz.rtf"
    path.write_text("whatever", encoding="utf-8")

    with pytest.raises(UnsupportedFormatError):
        await run_pipeline(path)


@pytest.mark.asyncio
async def test_run_pipeline_empty_file_returns_no_questions(tmp_path):
    path = tmp_path / "empty.txt"
    path.write_text("", encoding="utf-8")

    questions = await run_pipeline(path, use_llm_fallback=False)

    assert questions == []
