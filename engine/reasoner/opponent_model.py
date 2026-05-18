"""Opponent modeling for hidden-information games.

Infers what cards the opponent likely holds based on their
observed play patterns. For example:
- In Go Fish: opponent asked for 7s → they probably have 7s
- In Crazy Eights: opponent drew instead of playing → they lack matching suit/rank
- In Gin Rummy: opponent took from discard → they wanted that card for a meld
- In Poker: opponent kept all cards → they likely have a decent hand

These inferences become constraints on the belief state sampling,
making the AI's reasoning about hidden cards more accurate.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from engine.gdl.visibility import Constraint


@dataclass
class PlayObservation:
    """A record of an opponent's action."""
    action: str         # "draw_deck", "draw_discard", "discard", "play", "ask", etc.
    card_rank: Optional[str] = None
    card_suit: Optional[str] = None
    zone_from: Optional[str] = None
    zone_to: Optional[str] = None
    turn: int = 0


class OpponentModel:
    """Track opponent behavior to infer hidden card information.

    Builds constraints from observed play patterns:
    - Drawing from deck (not discard) → probably don't want the discard top
    - Discarding a rank → probably don't need that rank for melds
    - Not playing a matching card → probably don't have one
    """

    def __init__(self, opponent: str = "player2"):
        self.opponent = opponent
        self.observations: list[PlayObservation] = []
        self._constraints: list[Constraint] = []

    def observe(self, action: str, state_vars: dict,
                card_rank: Optional[str] = None,
                card_suit: Optional[str] = None,
                turn: int = 0):
        """Record an opponent action and derive constraints."""
        obs = PlayObservation(
            action=action,
            card_rank=card_rank,
            card_suit=card_suit,
            turn=turn,
        )
        self.observations.append(obs)
        self._derive_constraints(obs, state_vars)

    def _derive_constraints(self, obs: PlayObservation, state_vars: dict):
        """Derive constraints about opponent's hand from their action."""
        opp_hand = f"hand_{self.opponent.replace('player', 'p')}"

        if obs.action == "draw_deck":
            # Opponent drew from deck instead of discard — they might not want
            # the top discard card. Weak signal but worth noting.
            pass

        elif obs.action == "discard" and obs.card_rank:
            # Opponent discarded this rank — they probably don't need it
            self._constraints.append(Constraint(
                card_rank=obs.card_rank,
                zone_name=opp_hand,
                is_present=False,
                reason=f"discarded {obs.card_rank}",
            ))

        elif obs.action == "draw" and state_vars.get("last_action") == "draw":
            # In Crazy Eights/Uno: opponent drew → they have no matching card
            active_suit = state_vars.get("active_suit", "") or state_vars.get("active_color", "")
            if active_suit:
                self._constraints.append(Constraint(
                    card_suit=active_suit,
                    zone_name=opp_hand,
                    is_present=False,
                    reason=f"drew instead of playing {active_suit}",
                ))

        elif obs.action == "play" and obs.card_suit:
            # In trick-taking games (Hearts): if opponent played off-suit,
            # they're void in the lead suit
            lead_suit = state_vars.get("lead_suit", "")
            if lead_suit and obs.card_suit != lead_suit:
                self._constraints.append(Constraint(
                    card_suit=lead_suit,
                    zone_name=opp_hand,
                    is_present=False,
                    reason=f"played off-suit ({obs.card_suit} instead of {lead_suit})",
                ))

    def get_constraints(self) -> list[Constraint]:
        """Return all derived constraints."""
        return list(self._constraints)

    def reset(self):
        """Clear observations and constraints for a new game."""
        self.observations.clear()
        self._constraints.clear()

    def summary(self) -> dict:
        """Summary of what we've inferred about the opponent."""
        return {
            "observations": len(self.observations),
            "constraints": len(self._constraints),
            "inferences": [c.reason for c in self._constraints[-5:]],
        }
