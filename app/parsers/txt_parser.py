"""Extract paragraphs from .txt files — no styling available."""

from __future__ import annotations

from pathlib import Path

from app.core.exceptions import CorruptedFileError
from app.parsers.base import BaseParser, RichParagraph, RichRun


class TxtParser(BaseParser):
    async def extract(self, path: Path) -> list[RichParagraph]:
        try:
            raw = path.read_text(encoding="utf-8-sig", errors="replace")
        except Exception as exc:
            raise CorruptedFileError(f"Cannot read txt: {exc}") from exc

        paragraphs: list[RichParagraph] = []
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped:
                paragraphs.append(RichParagraph(runs=[RichRun(text=stripped)]))
        return paragraphs
