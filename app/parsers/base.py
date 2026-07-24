"""Abstract protocol every format-specific parser must implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RichRun:
    """A styled run inside a paragraph — preserves bold / underline info."""

    text: str
    bold: bool = False
    underline: bool = False
    italic: bool = False


@dataclass
class RichParagraph:
    """One logical line with its inline styling runs."""

    runs: list[RichRun] = field(default_factory=list)

    @property
    def plain_text(self) -> str:
        return "".join(r.text for r in self.runs).strip()

    @property
    def is_blank(self) -> bool:
        return not self.plain_text

    def has_any_bold(self) -> bool:
        """True if at least one non-whitespace run is bold."""
        return any(r.bold and r.text.strip() for r in self.runs)

    def has_any_underline(self) -> bool:
        return any(r.underline and r.text.strip() for r in self.runs)


class BaseParser(ABC):
    """Extract a list of RichParagraph objects from a file."""

    @abstractmethod
    async def extract(self, path: Path) -> list[RichParagraph]:
        """Return ordered paragraphs with inline styling metadata."""
        ...
