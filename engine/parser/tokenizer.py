"""Tokenizer for constrained English game descriptions.

Splits input text into sections by keywords (GAME:, BOARD:, etc.)
and normalizes whitespace.
"""

from __future__ import annotations
import re
from dataclasses import dataclass


SECTION_KEYWORDS = [
    "GAME", "PLAYERS", "BOARD", "PIECES", "SETUP",
    "MOVES", "SPECIAL", "WIN", "DRAW",
]


@dataclass
class Section:
    """A parsed section of a game description."""
    keyword: str
    content: str

    def lines(self) -> list[str]:
        """Get non-empty content lines."""
        return [l.strip() for l in self.content.strip().splitlines() if l.strip()]


def tokenize(text: str) -> list[Section]:
    """Split a game description into sections by keyword."""
    sections = []
    # Build regex to find section headers
    pattern = r"^(" + "|".join(SECTION_KEYWORDS) + r")\s*:\s*"
    current_keyword = None
    current_lines = []

    for line in text.splitlines():
        stripped = line.strip()
        match = re.match(pattern, stripped, re.IGNORECASE)
        if match:
            # Save previous section
            if current_keyword is not None:
                sections.append(Section(
                    keyword=current_keyword,
                    content="\n".join(current_lines),
                ))
            current_keyword = match.group(1).upper()
            # Content after the colon on the same line
            rest = stripped[match.end():].strip()
            current_lines = [rest] if rest else []
        elif current_keyword is not None:
            # Continuation line (indented or not)
            current_lines.append(stripped)

    # Save last section
    if current_keyword is not None:
        sections.append(Section(
            keyword=current_keyword,
            content="\n".join(current_lines),
        ))

    return sections


def get_section(sections: list[Section], keyword: str) -> Section | None:
    """Get a section by keyword, or None if not found."""
    for s in sections:
        if s.keyword == keyword:
            return s
    return None
