"""Unit tests for PdfParser.

Building a real PDF needs a PDF-writing library we don't otherwise
depend on, so the bold-detection heuristic is tested directly against
a fake pdfplumber Page (same shape: .extract_text() + .chars), and only
the corrupted-file path is exercised through the real extract() entrypoint.
"""

import pytest

from app.core.exceptions import CorruptedFileError
from app.parsers.pdf_parser import PdfParser


class _FakePage:
    def __init__(self, text: str, bold_indices: set[int]):
        self._text = text
        # One char entry per character in `text` (including newlines is not
        # required since PdfParser never indexes past non-newline chars).
        self.chars = [
            {"fontname": "Arial-Bold" if i in bold_indices else "Arial"}
            for i in range(len(text))
        ]

    def extract_text(self):
        return self._text


def test_bold_line_detected_via_font_heuristic():
    # "A) Red\nB) Blue\nC) Green" -> indices 7-13 are "B) Blue"
    text = "A) Red\nB) Blue\nC) Green"
    page = _FakePage(text, bold_indices=set(range(7, 14)))

    lines = PdfParser._page_to_rich_lines(page)

    assert [ln.plain_text for ln in lines] == ["A) Red", "B) Blue", "C) Green"]
    assert lines[1].has_any_bold() is True
    assert lines[0].has_any_bold() is False
    assert lines[2].has_any_bold() is False


def test_blank_text_returns_no_lines():
    page = _FakePage("", bold_indices=set())
    assert PdfParser._page_to_rich_lines(page) == []


@pytest.mark.asyncio
async def test_extract_corrupted_file_raises(tmp_path):
    path = tmp_path / "not_a_pdf.pdf"
    path.write_bytes(b"this is not a valid pdf file")

    with pytest.raises(CorruptedFileError):
        await PdfParser().extract(path)
