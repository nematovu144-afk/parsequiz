"""Extract rich paragraphs from .pdf files using pdfplumber.

pdfplumber exposes per-character font metadata, so we can reconstruct
bold/italic styling even from PDFs.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pdfplumber

from app.core.exceptions import CorruptedFileError
from app.parsers.base import BaseParser, RichParagraph, RichRun


class PdfParser(BaseParser):
    async def extract(self, path: Path) -> list[RichParagraph]:
        return await asyncio.to_thread(self._extract_sync, path)

    def _extract_sync(self, path: Path) -> list[RichParagraph]:
        try:
            pdf = pdfplumber.open(str(path))
        except Exception as exc:
            raise CorruptedFileError(f"Cannot open PDF: {exc}") from exc

        paragraphs: list[RichParagraph] = []
        try:
            for page in pdf.pages:
                lines = self._page_to_rich_lines(page)
                paragraphs.extend(lines)
        finally:
            pdf.close()
        return paragraphs

    # ── per-page character grouping ──────────────────────────

    @staticmethod
    def _page_to_rich_lines(page) -> list[RichParagraph]:
        """Group characters into lines, then into styled runs."""
        text = page.extract_text()
        if not text:
            return []

        # Fast path: use plain lines with basic bold heuristic from chars
        bold_chars: set[int] = set()
        chars = page.chars or []
        for i, ch in enumerate(chars):
            font = (ch.get("fontname") or "").lower()
            if "bold" in font or "black" in font:
                bold_chars.add(i)

        result: list[RichParagraph] = []
        char_idx = 0
        for raw_line in text.split("\n"):
            line = raw_line.strip()
            if not line:
                char_idx += len(raw_line) + 1
                continue

            rp = RichParagraph()
            # Build a single run per line, marking bold if majority of
            # non-space chars in that span are bold-fonted.
            line_bold_count = 0
            line_total = 0
            for ch in line:
                if ch.strip():
                    line_total += 1
                    if char_idx in bold_chars:
                        line_bold_count += 1
                char_idx += 1
            char_idx += 1  # newline

            is_bold = line_total > 0 and (line_bold_count / line_total) > 0.5
            rp.runs.append(RichRun(text=line, bold=is_bold))
            result.append(rp)

        return result
