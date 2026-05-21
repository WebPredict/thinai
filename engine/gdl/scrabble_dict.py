"""Scrabble dictionary and letter values for ThinAI's simplified Scrabble."""

from __future__ import annotations
import os
from pathlib import Path

# Standard Scrabble letter values
LETTER_VALUES = {
    'A': 1, 'B': 3, 'C': 3, 'D': 2, 'E': 1, 'F': 4, 'G': 2, 'H': 4,
    'I': 1, 'J': 8, 'K': 5, 'L': 1, 'M': 3, 'N': 1, 'O': 1, 'P': 3,
    'Q': 10, 'R': 1, 'S': 1, 'T': 1, 'U': 1, 'V': 4, 'W': 4, 'X': 8,
    'Y': 4, 'Z': 10,
}

# Load word list
_WORDS_FILE = Path(__file__).parent / "scrabble_words.txt"
SCRABBLE_WORDS: frozenset[str] = frozenset()

if _WORDS_FILE.exists():
    with open(_WORDS_FILE) as f:
        SCRABBLE_WORDS = frozenset(line.strip().upper() for line in f if line.strip())


def is_valid_word(word: str) -> bool:
    """Check if a word is in the dictionary."""
    return word.upper() in SCRABBLE_WORDS


def word_score(word: str) -> int:
    """Calculate the base score of a word (no bonus squares)."""
    return sum(LETTER_VALUES.get(c, 0) for c in word.upper())
