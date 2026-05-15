"""Visibility and belief state for hidden-information games.

In card games, each player sees a different view of the game:
- Their own hand (visible to them, hidden from opponent)
- The deck (hidden from everyone)
- The discard pile (visible to everyone)

The belief state represents what a player believes about
hidden cards based on what they've observed.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import random

from engine.gdl.cards import Card, CardZone, CardGameState


class PlayerView:
    """What a specific player can see of the card game state.

    Hides cards in zones the player can't see, but preserves
    counts (you know how many cards the opponent has, just not which).
    """

    def __init__(self, state: CardGameState, viewer: str):
        self.viewer = viewer
        self.current_player = state.current_player
        self.turn_number = state.turn_number
        self.zones: dict[str, dict] = {}

        for name, zone in state.zones.items():
            self.zones[name] = zone.to_dict(viewer)

    def visible_cards_in(self, zone_name: str) -> list[Optional[Card]]:
        """Get cards visible to this player in a zone."""
        zone_data = self.zones.get(zone_name, {})
        cards = zone_data.get("cards", [])
        return [
            Card.from_dict(c) if isinstance(c, dict) and "suit" in c else None
            for c in cards
        ]

    def zone_size(self, zone_name: str) -> int:
        """How many cards are in a zone (always visible)."""
        return self.zones.get(zone_name, {}).get("size", 0)

    def to_dict(self) -> dict:
        return {
            "viewer": self.viewer,
            "current_player": self.current_player,
            "turn_number": self.turn_number,
            "zones": self.zones,
        }


@dataclass
class Constraint:
    """A constraint on where a hidden card might be.

    Used to narrow belief state sampling based on observed play.
    Example: "opponent didn't play hearts when hearts were led"
    → opponent probably doesn't have hearts.
    """
    card_suit: Optional[str] = None
    card_rank: Optional[str] = None
    zone_name: Optional[str] = None
    is_present: bool = True  # True = card IS here, False = card is NOT here
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "suit": self.card_suit,
            "rank": self.card_rank,
            "zone": self.zone_name,
            "present": self.is_present,
            "reason": self.reason,
        }


class BeliefState:
    """A player's belief about the full game state.

    Tracks which cards' locations are known vs unknown, and
    constraints from observed play that narrow the possibilities.

    Can generate concrete sample states for search.
    """

    def __init__(self, viewer: str, state: CardGameState):
        self.viewer = viewer
        self.state = state
        self.constraints: list[Constraint] = []

        # Categorize cards
        self.known_locations: dict[int, str] = {}  # card_id → zone_name
        self.unknown_cards: list[Card] = []
        self.hidden_zones: list[str] = []  # zones we can't see

        self._analyze(state)

    def _analyze(self, state: CardGameState):
        """Analyze state to determine what we know vs don't know."""
        for name, zone in state.zones.items():
            if zone.can_see(self.viewer):
                # We can see these cards — their locations are known
                for card in zone.cards:
                    self.known_locations[card.id] = name
            else:
                # We can't see these cards — they're unknown
                self.hidden_zones.append(name)
                for card in zone.cards:
                    self.unknown_cards.append(card)

    def add_constraint(self, constraint: Constraint):
        """Add a constraint from observed play."""
        self.constraints.append(constraint)

    def sample(self) -> CardGameState:
        """Generate a concrete state consistent with our beliefs.

        Randomly distributes unknown cards among hidden zones,
        respecting constraints.
        """
        sampled = self.state.copy()

        # Collect all unknown cards
        unknown = list(self.unknown_cards)
        random.shuffle(unknown)

        # Clear hidden zones
        for zone_name in self.hidden_zones:
            zone = sampled.get_zone(zone_name)
            if zone:
                zone.cards.clear()

        # Distribute unknown cards to hidden zones
        # respecting capacity and constraints
        zone_targets = []
        for zone_name in self.hidden_zones:
            zone = sampled.get_zone(zone_name)
            if zone:
                # How many cards should this zone have?
                original_count = self.state.get_zone(zone_name).size
                zone_targets.append((zone_name, original_count))

        # Simple distribution: fill each zone to its original size
        idx = 0
        for zone_name, target_count in zone_targets:
            zone = sampled.get_zone(zone_name)
            for _ in range(target_count):
                if idx < len(unknown):
                    # Check constraints
                    card = self._pick_valid_card(unknown, idx, zone_name)
                    zone.add(card)
                    unknown.remove(card)
            idx = 0  # reset for next zone

        return sampled

    def _pick_valid_card(self, available: list[Card], start_idx: int,
                          target_zone: str) -> Card:
        """Pick a card that satisfies constraints for this zone."""
        # Try to find a card that doesn't violate constraints
        for card in available:
            valid = True
            for constraint in self.constraints:
                if not constraint.is_present and constraint.zone_name == target_zone:
                    if (constraint.card_suit and card.suit == constraint.card_suit):
                        valid = False
                        break
                    if (constraint.card_rank and card.rank == constraint.card_rank):
                        valid = False
                        break
            if valid:
                return card

        # No valid card found — return first available (constraint violated)
        return available[0]

    def num_samples_needed(self) -> int:
        """Estimate how many samples needed for reasonable coverage."""
        n_unknown = len(self.unknown_cards)
        if n_unknown <= 5:
            return 10
        if n_unknown <= 15:
            return 25
        return 50

    def to_dict(self) -> dict:
        return {
            "viewer": self.viewer,
            "known_cards": len(self.known_locations),
            "unknown_cards": len(self.unknown_cards),
            "hidden_zones": self.hidden_zones,
            "constraints": [c.to_dict() for c in self.constraints],
        }
