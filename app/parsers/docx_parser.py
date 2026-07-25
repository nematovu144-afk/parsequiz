"""Extract rich paragraphs from .docx files using python-docx."""

from __future__ import annotations

import asyncio
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

from app.core.exceptions import CorruptedFileError
from app.parsers.base import BaseParser, RichParagraph, RichRun


class DocxParser(BaseParser):
    async def extract(self, path: Path) -> list[RichParagraph]:
        return await asyncio.to_thread(self._extract_sync, path)

    # ── sync internals (runs in thread pool) ─────────────────

    def _extract_sync(self, path: Path) -> list[RichParagraph]:
        try:
            doc = Document(str(path))
        except Exception as exc:
            raise CorruptedFileError(f"Cannot open docx: {exc}") from exc

        paragraphs: list[RichParagraph] = []
        for para in doc.paragraphs:
            paragraphs.extend(self._para_to_lines(para))
        return paragraphs

    def _para_to_lines(self, para) -> list[RichParagraph]:
        """Split one docx paragraph into one-or-more RichParagraphs.

        A manual line break (Shift+Enter, python-docx's Run.text renders it
        as an embedded "\\n") keeps everything inside a single <w:p> element
        even though it visually looks like separate lines -- e.g. a question
        header, then several options, glued into one "paragraph" with no
        real paragraph breaks between them. Splitting on those embedded
        newlines here lets each visual line reach delimiter.py on its own,
        the same as if it had been a real paragraph break.
        """
        if not para.runs and para.text.strip():
            return [RichParagraph(runs=[RichRun(text=para.text)])]

        lines: list[RichParagraph] = []
        current = RichParagraph()
        for run in para.runs:
            bold = self._is_bold(run)
            underline = run.underline is not None and run.underline is not False
            italic = bool(run.italic)
            segments = run.text.split("\n")
            for i, segment in enumerate(segments):
                if segment:
                    current.runs.append(
                        RichRun(text=segment, bold=bold, underline=underline, italic=italic)
                    )
                if i < len(segments) - 1:
                    lines.append(current)
                    current = RichParagraph()
        lines.append(current)
        return [line for line in lines if not line.is_blank]

    @staticmethod
    def _is_bold(run) -> bool:
        """Resolve bold from run props, then style inheritance."""
        if run.bold is True:
            return True
        if run.bold is False:
            return False
        # Check the underlying XML for inherited bold
        rpr = run._element.find(qn("w:rPr"))
        if rpr is not None:
            b_el = rpr.find(qn("w:b"))
            if b_el is not None:
                val = b_el.get(qn("w:val"))
                return val is None or val not in ("0", "false")
        return False
