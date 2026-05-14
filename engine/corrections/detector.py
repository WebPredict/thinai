"""Correction event detection for ThinAI.

Detects when something unexpected happens during gameplay and
produces CorrectionEvents that the diagnosis system can analyze.

Correction types:
  - illegal_move: system attempted a move that was rejected
  - missing_rule: opponent made a move not covered by the rules
  - outcome_surprise: game ended with unexpected result
  - explicit: user provided direct feedback about a rule
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from engine.gdl.state import GameState, Move, GameResult


class CorrectionType(Enum):
    ILLEGAL_MOVE = "illegal_move"
    MISSING_RULE = "missing_rule"
    OUTCOME_SURPRISE = "outcome_surprise"
    EXPLICIT = "explicit"


@dataclass
class CorrectionEvent:
    """A detected correction event with full context."""
    correction_type: CorrectionType
    description: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # Context about when the correction occurred
    game_name: Optional[str] = None
    turn_number: int = 0
    current_player: Optional[str] = None

    # What happened vs what was expected
    attempted_move: Optional[Move] = None
    expected_result: Optional[Any] = None
    actual_result: Optional[Any] = None

    # The state when the correction occurred
    state_snapshot: Optional[dict] = None

    # Which rules might be involved
    candidate_rules: list[str] = field(default_factory=list)

    # For explicit corrections: the user's feedback text
    feedback_text: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "type": self.correction_type.value,
            "description": self.description,
            "timestamp": self.timestamp,
            "game_name": self.game_name,
            "turn_number": self.turn_number,
            "current_player": self.current_player,
            "attempted_move": repr(self.attempted_move) if self.attempted_move else None,
            "expected_result": str(self.expected_result),
            "actual_result": str(self.actual_result),
            "candidate_rules": self.candidate_rules,
            "feedback_text": self.feedback_text,
        }


class CorrectionDetector:
    """Detects correction events during gameplay."""

    def __init__(self, game_name: str):
        self.game_name = game_name
        self.events: list[CorrectionEvent] = []
        self._expected_outcomes: dict[str, float] = {}  # track expected eval scores

    def detect_illegal_move(self, state: GameState, move: Move,
                            legal_moves: list[Move]) -> CorrectionEvent:
        """Detect when a move is attempted that isn't in the legal moves list.

        This happens when the system's understanding of the rules differs
        from the actual rules. The system generates a move based on its
        GDL, but when validated against the real rules, it's illegal.
        """
        event = CorrectionEvent(
            correction_type=CorrectionType.ILLEGAL_MOVE,
            description=f"Move {move} was rejected as illegal",
            game_name=self.game_name,
            turn_number=state.turn_number,
            current_player=state.current_player,
            attempted_move=move,
            expected_result="move accepted",
            actual_result="move rejected",
            candidate_rules=[move.rule_name],
        )
        self.events.append(event)
        return event

    def detect_unexpected_opponent_move(self, state: GameState,
                                        opponent_move: Move,
                                        our_legal_moves: list[Move]) -> Optional[CorrectionEvent]:
        """Detect when an opponent makes a move our rules don't recognize.

        If the opponent's move matches one of our legal moves, it's expected.
        If not, it suggests our rules are missing something.
        """
        # Check if the opponent's move would be legal under our rules
        # (with current_player temporarily set to the opponent)
        is_recognized = any(
            m.rule_name == opponent_move.rule_name and m.params == opponent_move.params
            for m in our_legal_moves
        )
        if is_recognized:
            return None

        event = CorrectionEvent(
            correction_type=CorrectionType.MISSING_RULE,
            description=f"Opponent played {opponent_move} which our rules don't allow",
            game_name=self.game_name,
            turn_number=state.turn_number,
            current_player=state.current_player,
            attempted_move=opponent_move,
            expected_result="no such legal move",
            actual_result="opponent played it successfully",
            candidate_rules=[opponent_move.rule_name],
        )
        self.events.append(event)
        return event

    def detect_outcome_surprise(self, state: GameState, result: GameResult,
                                 expected_winner: Optional[str],
                                 confidence: float) -> Optional[CorrectionEvent]:
        """Detect when the game ends with an unexpected outcome.

        If the system was confident it was winning (high eval score)
        but lost, or vice versa, something is wrong with either the
        evaluation or the end conditions.
        """
        if expected_winner is None:
            return None

        actual_winner = result.winner
        if actual_winner == expected_winner:
            return None

        # Only flag if confidence was reasonably high
        if confidence < 0.3:
            return None

        event = CorrectionEvent(
            correction_type=CorrectionType.OUTCOME_SURPRISE,
            description=f"Expected {expected_winner} to win (confidence={confidence:.0%}) "
                        f"but {actual_winner or 'draw'} occurred",
            game_name=self.game_name,
            turn_number=state.turn_number,
            current_player=state.current_player,
            expected_result=expected_winner,
            actual_result=actual_winner or "draw",
        )
        self.events.append(event)
        return event

    def detect_explicit_correction(self, state: GameState,
                                    feedback: str) -> CorrectionEvent:
        """Record an explicit user correction about the rules.

        The user has told us something is wrong. Parse what they said
        and create a correction event.
        """
        event = CorrectionEvent(
            correction_type=CorrectionType.EXPLICIT,
            description=f"User correction: {feedback}",
            game_name=self.game_name,
            turn_number=state.turn_number,
            current_player=state.current_player,
            feedback_text=feedback,
        )
        self.events.append(event)
        return event

    def update_expectations(self, player: str, eval_score: float):
        """Track evaluation scores to detect outcome surprises."""
        self._expected_outcomes[player] = eval_score

    def get_expected_winner(self) -> tuple[Optional[str], float]:
        """Return the expected winner and confidence based on eval scores."""
        if not self._expected_outcomes:
            return None, 0.0
        best_player = max(self._expected_outcomes, key=self._expected_outcomes.get)
        confidence = abs(self._expected_outcomes.get(best_player, 0))
        return best_player, confidence

    @property
    def correction_count(self) -> int:
        return len(self.events)

    def events_by_type(self, correction_type: CorrectionType) -> list[CorrectionEvent]:
        return [e for e in self.events if e.correction_type == correction_type]

    def summary(self) -> dict:
        """Summary of all detected corrections."""
        by_type = {}
        for ct in CorrectionType:
            events = self.events_by_type(ct)
            if events:
                by_type[ct.value] = len(events)
        return {
            "game_name": self.game_name,
            "total_corrections": self.correction_count,
            "by_type": by_type,
            "events": [e.to_dict() for e in self.events],
        }
