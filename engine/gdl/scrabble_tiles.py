"""Scrabble tile bag and bonus square definitions for ThinAI's simplified Scrabble."""

from __future__ import annotations
import random
from engine.gdl.scrabble_dict import LETTER_VALUES

# Tile distribution for 2-player 9x9 (reduced from standard 100 tiles)
# Roughly 70 tiles total — enough for a full game on a smaller board
TILE_DISTRIBUTION = {
    'A': 6, 'B': 2, 'C': 2, 'D': 3, 'E': 8, 'F': 2, 'G': 2, 'H': 2,
    'I': 6, 'J': 1, 'K': 1, 'L': 3, 'M': 2, 'N': 4, 'O': 5, 'P': 2,
    'Q': 1, 'R': 4, 'S': 3, 'T': 4, 'U': 3, 'V': 1, 'W': 1, 'X': 1,
    'Y': 2, 'Z': 1,
}
# Total: 71 tiles

# Bonus square map for 9x9 board (symmetric pattern)
# TW = Triple Word, DW = Double Word, TL = Triple Letter, DL = Double Letter
BONUS_SQUARES = {
    # Triple Word (corners and mid-edges)
    (0, 0): 'TW', (0, 8): 'TW', (8, 0): 'TW', (8, 8): 'TW',
    # Double Word (diagonal pattern)
    (1, 1): 'DW', (1, 7): 'DW', (7, 1): 'DW', (7, 7): 'DW',
    (2, 2): 'DW', (2, 6): 'DW', (6, 2): 'DW', (6, 6): 'DW',
    # Center star (Double Word)
    (4, 4): 'DW',
    # Double Letter
    (0, 3): 'DL', (0, 5): 'DL', (8, 3): 'DL', (8, 5): 'DL',
    (3, 0): 'DL', (5, 0): 'DL', (3, 8): 'DL', (5, 8): 'DL',
    # Triple Letter
    (3, 3): 'TL', (3, 5): 'TL', (5, 3): 'TL', (5, 5): 'TL',
}


def create_tile_bag() -> list[dict]:
    """Create a shuffled bag of letter tiles."""
    bag = []
    tile_id = 0
    for letter, count in TILE_DISTRIBUTION.items():
        for _ in range(count):
            bag.append({
                'letter': letter,
                'value': LETTER_VALUES.get(letter, 0),
                'id': tile_id,
            })
            tile_id += 1
    random.shuffle(bag)
    return bag


def draw_tiles(bag: list[dict], count: int) -> list[dict]:
    """Draw tiles from the bag. Returns drawn tiles."""
    drawn = []
    for _ in range(min(count, len(bag))):
        drawn.append(bag.pop())
    return drawn
