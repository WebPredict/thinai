"""Correction handler for ThinAI.

Orchestrates the full correction pipeline:
  detection → diagnosis → revision → confidence update

Integrates with the game engine and training loop.
"""

from __future__ import annotations
from copy import deepcopy
from typing import Optional, Callable

from engine.corrections.confidence import ConfidenceTracker
from engine.corrections.detector import CorrectionDetector, CorrectionEvent, CorrectionType
from engine.corrections.diagnosis import FaultDiagnoser, Diagnosis
from engine.corrections.revision import RuleReviser, Revision
from engine.gdl.state import GameState, Move, GameResult


class CorrectionHandler:
    """Orchestrates correction detection, diagnosis, and revision."""

    def __init__(self, gdl: dict, auto_apply: bool = True):
        """
        Args:
            gdl: The GDL specification to monitor and correct.
            auto_apply: If True, automatically apply proposed revisions.
                       If False, revisions are proposed but not applied
                       (useful for human-in-the-loop mode).
        """
        self.gdl = gdl
        self.auto_apply = auto_apply
        self.game_name = gdl.get("meta", {}).get("name", "unknown")

        # Initialize subsystems
        self.confidence = ConfidenceTracker(gdl)
        self.detector = CorrectionDetector(self.game_name)
        self.diagnoser = FaultDiagnoser(gdl, self.confidence)
        self.reviser = RuleReviser(gdl, self.confidence)

        # Callbacks for external systems
        self._on_correction: Optional[Callable] = None
        self._on_revision: Optional[Callable] = None

        # Stats
        self.corrections_applied = 0
        self.games_completed = 0

    def set_callbacks(self, on_correction: Callable = None,
                      on_revision: Callable = None):
        """Set callbacks for correction events."""
        self._on_correction = on_correction
        self._on_revision = on_revision

    # --- Game lifecycle hooks ---

    def on_move_rejected(self, state: GameState, move: Move,
                         legal_moves: list[Move]) -> Optional[Diagnosis]:
        """Called when the system attempts an illegal move.

        Returns a Diagnosis if a correction was detected, else None.
        """
        event = self.detector.detect_illegal_move(state, move, legal_moves)
        return self._handle_event(event)

    def on_opponent_move(self, state: GameState, opponent_move: Move,
                         our_legal_moves: list[Move]) -> Optional[Diagnosis]:
        """Called after the opponent makes a move.

        Checks if the opponent's move is one our rules recognize.
        """
        event = self.detector.detect_unexpected_opponent_move(
            state, opponent_move, our_legal_moves
        )
        if event is None:
            return None
        return self._handle_event(event)

    def on_game_end(self, state: GameState, result: GameResult):
        """Called when a game ends. Updates confidence and checks for surprises."""
        self.games_completed += 1

        # Check for outcome surprise
        expected_winner, confidence = self.detector.get_expected_winner()
        event = self.detector.detect_outcome_surprise(
            state, result, expected_winner, confidence
        )
        if event:
            self._handle_event(event)
        else:
            # Game ended as expected — confirm all rules
            self.confidence.confirm_all_rules()

        # Reset expectations for next game
        self.detector._expected_outcomes.clear()

    def on_successful_move(self, state: GameState, move: Move):
        """Called after a move is successfully applied.

        Confirms the rule used.
        """
        self.confidence.confirm_rule(move.rule_name)

    def on_explicit_correction(self, state: GameState,
                                feedback: str) -> Optional[Diagnosis]:
        """Called when a user provides direct feedback."""
        event = self.detector.detect_explicit_correction(state, feedback)
        return self._handle_event(event)

    def update_eval_expectation(self, player: str, eval_score: float):
        """Update the detector's expectation for outcome surprise detection."""
        self.detector.update_expectations(player, eval_score)

    # --- Core pipeline ---

    def _handle_event(self, event: CorrectionEvent) -> Optional[Diagnosis]:
        """Run the full correction pipeline for a detected event."""
        if self._on_correction:
            self._on_correction(event)

        # Diagnose
        diagnosis = self.diagnoser.diagnose(event)

        if not diagnosis.candidates:
            return diagnosis

        # Propose revisions
        revisions = self.reviser.propose_revisions(diagnosis)

        if self.auto_apply and revisions:
            for revision in revisions:
                warnings = self.reviser.check_consistency(revision)
                if not warnings:
                    success = self.reviser.apply_revision(revision)
                    if success:
                        self.corrections_applied += 1
                        if self._on_revision:
                            self._on_revision(revision)

        return diagnosis

    # --- Direct rule modification ---

    def modify_rule_condition(self, rule_name: str, old_condition: str,
                               new_condition: str) -> bool:
        """Directly modify a rule condition.

        Used for programmatic corrections (e.g., fixing a known wrong rule).
        """
        return self.reviser.apply_direct_revision(
            rule_name=rule_name,
            revision_type="modify_condition",
            old_value=old_condition,
            new_value=new_condition,
            description=f"Direct condition modification on '{rule_name}'",
        )

    def modify_end_condition(self, index: int, new_condition: str = None,
                              new_player: str = None) -> bool:
        """Directly modify an end condition."""
        end_conditions = self.gdl.get("end_conditions", [])
        if index >= len(end_conditions):
            return False
        ec = end_conditions[index]
        ec_name = f"end_{ec['type']}_{index}"

        changes = {}
        if new_condition:
            changes["condition"] = new_condition
        if new_player:
            changes["player"] = new_player

        if not changes:
            return False

        revision = Revision(
            revision_id=self.reviser._next_id(),
            rule_name=ec_name,
            revision_type="modify_end_condition",
            description=f"Direct end condition modification",
            old_value=ec.get("condition"),
            new_value=changes,
        )
        # Apply directly (bypass normal proposal flow)
        if new_condition:
            ec["condition"] = new_condition
        if new_player:
            ec["player"] = new_player
        revision.applied = True
        self.reviser.revision_history.append(revision)
        self.confidence.penalize_rule(ec_name)
        self.corrections_applied += 1
        return True

    def add_rule_condition(self, rule_name: str, condition: str) -> bool:
        """Add a condition to a rule."""
        return self.reviser.apply_direct_revision(
            rule_name=rule_name,
            revision_type="add_condition",
            old_value=None,
            new_value=condition,
            description=f"Add condition to '{rule_name}': {condition}",
        )

    # --- Queries ---

    @property
    def has_corrections(self) -> bool:
        return self.detector.correction_count > 0

    def summary(self) -> dict:
        """Full summary of correction activity."""
        return {
            "game_name": self.game_name,
            "games_completed": self.games_completed,
            "total_corrections": self.detector.correction_count,
            "revisions_applied": self.corrections_applied,
            "confidence_summary": self.confidence.summary(),
            "suspect_rules": [rc.to_dict() for rc in self.confidence.suspect_rules],
            "revision_history": self.reviser.history_summary(),
            "detection_summary": self.detector.summary(),
        }

    def get_gdl(self) -> dict:
        """Return the current (possibly modified) GDL spec."""
        return self.gdl
