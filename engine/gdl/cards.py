"""Card system for ThinAI.

Provides Card, CardZone, and deck generation for card games.
Cards can be in various zones (deck, hand, discard, table) with
different visibility rules per zone.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import random


# Standard suits and ranks
SUITS = ["hearts", "diamonds", "clubs", "spades"]
SUIT_SYMBOLS = {"hearts": "\u2665", "diamonds": "\u2666", "clubs": "\u2663", "spades": "\u2660"}
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
RANK_VALUES = {r: i + 2 for i, r in enumerate(RANKS)}  # 2=2, 3=3, ..., A=14


@dataclass(frozen=True)
class Card:
    """A playing card."""
    suit: str
    rank: str
    id: int  # unique identifier within a deck

    @property
    def value(self) -> int:
        """Numeric value for comparison (2-14)."""
        return RANK_VALUES.get(self.rank, 0)

    @property
    def symbol(self) -> str:
        return SUIT_SYMBOLS.get(self.suit, "?")

    def __repr__(self):
        return f"{self.rank}{self.symbol}"

    def to_dict(self) -> dict:
        return {"suit": self.suit, "rank": self.rank, "id": self.id}

    @classmethod
    def from_dict(cls, data: dict) -> "Card":
        return cls(suit=data["suit"], rank=data["rank"], id=data["id"])


class CardZone:
    """A collection of cards — deck, hand, discard pile, etc.

    Zones have visibility rules:
      - "all": everyone can see the cards (discard pile, table)
      - "owner": only the owner can see (player's hand)
      - "none": nobody can see (face-down deck)
    """

    def __init__(self, name: str, owner: Optional[str] = None,
                 visible_to: str = "all", ordered: bool = False,
                 capacity: Optional[int] = None):
        self.name = name
        self.owner = owner  # None = shared, "player1" = private
        self.visible_to = visible_to  # "all", "owner", "none"
        self.ordered = ordered  # True = draw from top (deck)
        self.capacity = capacity  # None = unlimited
        self.cards: list[Card] = []

    def add(self, card: Card, to_top: bool = True):
        """Add a card to this zone."""
        if to_top:
            self.cards.append(card)
        else:
            self.cards.insert(0, card)

    def remove(self, card: Card) -> Card:
        """Remove a specific card from this zone."""
        self.cards.remove(card)
        return card

    def draw(self) -> Optional[Card]:
        """Draw the top card (last in list). Returns None if empty."""
        if not self.cards:
            return None
        return self.cards.pop()

    def draw_bottom(self) -> Optional[Card]:
        """Draw the bottom card (first in list)."""
        if not self.cards:
            return None
        return self.cards.pop(0)

    def peek(self) -> Optional[Card]:
        """Look at the top card without removing it."""
        return self.cards[-1] if self.cards else None

    def shuffle(self):
        """Randomize card order."""
        random.shuffle(self.cards)

    def contains(self, card: Card) -> bool:
        return card in self.cards

    def find(self, suit: Optional[str] = None, rank: Optional[str] = None) -> list[Card]:
        """Find cards matching criteria."""
        result = self.cards
        if suit:
            result = [c for c in result if c.suit == suit]
        if rank:
            result = [c for c in result if c.rank == rank]
        return result

    @property
    def size(self) -> int:
        return len(self.cards)

    @property
    def is_empty(self) -> bool:
        return len(self.cards) == 0

    def can_see(self, viewer: Optional[str]) -> bool:
        """Can this viewer see the cards in this zone?"""
        if self.visible_to == "all":
            return True
        if self.visible_to == "owner" and viewer == self.owner:
            return True
        return False

    def visible_cards(self, viewer: Optional[str]) -> list[Optional[Card]]:
        """Get cards as seen by a viewer. Hidden cards return None."""
        if self.can_see(viewer):
            return list(self.cards)
        # Viewer can see the count but not the contents
        return [None] * len(self.cards)

    def to_dict(self, viewer: Optional[str] = None) -> dict:
        """Serialize, respecting visibility."""
        if viewer and not self.can_see(viewer):
            return {
                "name": self.name,
                "owner": self.owner,
                "size": self.size,
                "cards": [{"hidden": True} for _ in self.cards],
            }
        return {
            "name": self.name,
            "owner": self.owner,
            "size": self.size,
            "cards": [c.to_dict() for c in self.cards],
        }

    def __repr__(self):
        return f"CardZone({self.name}, {self.size} cards)"


def create_standard_deck(deck_type: str = "standard52") -> list[Card]:
    """Create a standard deck of cards.

    Supported types:
      - "standard52": standard 52-card deck
      - "standard52_jokers": 52 + 2 jokers
    """
    cards = []
    card_id = 0
    for suit in SUITS:
        for rank in RANKS:
            cards.append(Card(suit=suit, rank=rank, id=card_id))
            card_id += 1

    if deck_type == "standard52_jokers":
        cards.append(Card(suit="joker", rank="Joker", id=card_id))
        card_id += 1
        cards.append(Card(suit="joker", rank="Joker", id=card_id))

    return cards


def compare_cards(a: Card, b: Card) -> int:
    """Compare two cards by rank value. Returns >0 if a wins, <0 if b wins, 0 if tie."""
    return a.value - b.value


def hand_description(cards: list[Card]) -> str:
    """Human-readable description of a hand of cards."""
    if not cards:
        return "empty hand"
    return ", ".join(repr(c) for c in sorted(cards, key=lambda c: -c.value))


class CardGameState:
    """State for a card game — manages multiple zones.

    This wraps the zone system and provides game-level operations
    like dealing, moving cards between zones, etc.
    """

    def __init__(self):
        self.zones: dict[str, CardZone] = {}
        self.current_player: str = "player1"
        self.turn_number: int = 1

    def add_zone(self, zone: CardZone):
        self.zones[zone.name] = zone

    def get_zone(self, name: str) -> Optional[CardZone]:
        return self.zones.get(name)

    def deal(self, from_zone: str, to_zone: str, count: int):
        """Move N cards from one zone to another."""
        source = self.zones[from_zone]
        dest = self.zones[to_zone]
        for _ in range(min(count, source.size)):
            card = source.draw()
            if card:
                dest.add(card)

    def move_card(self, card: Card, from_zone: str, to_zone: str):
        """Move a specific card between zones."""
        source = self.zones[from_zone]
        dest = self.zones[to_zone]
        source.remove(card)
        dest.add(card)

    def shuffle_zone(self, zone_name: str):
        """Shuffle a zone's cards."""
        self.zones[zone_name].shuffle()

    def all_zones(self) -> list[CardZone]:
        return list(self.zones.values())

    def to_dict(self, viewer: Optional[str] = None) -> dict:
        """Serialize state, respecting visibility for viewer."""
        return {
            "current_player": self.current_player,
            "turn_number": self.turn_number,
            "zones": {name: zone.to_dict(viewer) for name, zone in self.zones.items()},
        }

    def copy(self) -> "CardGameState":
        """Deep copy for search."""
        new = CardGameState()
        new.current_player = self.current_player
        new.turn_number = self.turn_number
        for name, zone in self.zones.items():
            new_zone = CardZone(
                name=zone.name, owner=zone.owner,
                visible_to=zone.visible_to, ordered=zone.ordered,
                capacity=zone.capacity,
            )
            new_zone.cards = list(zone.cards)  # Cards are frozen, safe to share
            new.zones[name] = new_zone
        return new
