"""Unit tests for TxtParser."""

import pytest

from app.core.exceptions import CorruptedFileError
from app.parsers.txt_parser import TxtParser


@pytest.mark.asyncio
async def test_extract_skips_blank_lines(tmp_path):
    path = tmp_path / "quiz.txt"
    path.write_text("1. Question?\n\nA) One\nB) Two\n", encoding="utf-8")

    paragraphs = await TxtParser().extract(path)

    assert [p.plain_text for p in paragraphs] == ["1. Question?", "A) One", "B) Two"]


@pytest.mark.asyncio
async def test_extract_missing_file_raises_corrupted_file_error(tmp_path):
    with pytest.raises(CorruptedFileError):
        await TxtParser().extract(tmp_path / "does_not_exist.txt")
