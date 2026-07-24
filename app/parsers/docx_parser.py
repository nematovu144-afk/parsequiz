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
            rp = RichParagraph()
            for run in para.runs:
                rp.runs.append(
                    RichRun(
                        text=run.text,
                        bold=self._is_bold(run),
                        underline=run.underline is not None and run.underline is not False,
                        italic=bool(run.italic),
                    )
                )
            # If paragraph has no runs but has text (rare edge case):
            if not rp.runs and para.text.strip():
                rp.runs.append(RichRun(text=para.text))
            if not rp.is_blank:
                paragraphs.append(rp)
        return paragraphs

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
