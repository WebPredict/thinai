"""Integration tests for the correction system.

Tests the full pipeline: detection → diagnosis → revision → confidence update.
Uses deliberately incorrect game specs to verify corrections work.
"""

import os
import json
import pytest
from copy import deepcopy

from engine.engine import GameEngine
from engine.gdl.state import Move, GameResult
from engine.gdl.board import GridSpace, TrackSpace
from engine.corrections.confidence import ConfidenceTracker, RuleConfidence
from engine.corrections.detector import CorrectionDetector, CorrectionType
from engine.corrections.diagnosis import FaultDiagnoser
from engine.corrections.revision import RuleReviser
from engine.corrections.handler import CorrectionHandler


EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "games", "examples")


def _load_gdl(filename):
    with open(os.path.join(EXAMPLES_DIR, filename)) as f:
        return json.load(f)


# ============================================================
# Confidence Tracking Tests
# ============================================================

class TestConfidenceTracker:
    def test_initial_scores(self):
        gdl = _load_gdl("tictactoe.json")
        tracker = ConfidenceTracker(gdl)
        rc = tracker.get("place_mark")
        assert rc is not None
        assert rc.score == 0.6
        assert rc.provenance == "parsed"

    def test_confirm_increases(self):
        gdl = _load_gdl("tictactoe.json")
        tracker = ConfidenceTracker(gdl)
        tracker.confirm_rule("place_mark")
        rc = tracker.get("place_mark")
        assert rc.score > 0.6
        assert rc.confirmations == 1

    def test_penalize_decreases(self):
        gdl = _load_gdl("tictactoe.json")
        tracker = ConfidenceTracker(gdl)
        tracker.penalize_rule("place_mark")
        rc = tracker.get("place_mark")
        assert rc.score < 0.6
        assert rc.corrections == 1

    def test_confirm_all(self):
        gdl = _load_gdl("tictactoe.json")
        tracker = ConfidenceTracker(gdl)
        tracker.confirm_all_rules()
        for rc in tracker.all_scores.values():
            assert rc.score > 0.6

    def test_suspect_detection(self):
        gdl = _load_gdl("tictactoe.json")
        tracker = ConfidenceTracker(gdl)
        # Penalize heavily
        for _ in range(5):
            tracker.penalize_rule("place_mark")
        suspects = tracker.suspect_rules
        assert any(rc.rule_name == "place_mark" for rc in suspects)

    def test_serialization(self):
        gdl = _load_gdl("tictactoe.json")
        tracker = ConfidenceTracker(gdl)
        tracker.confirm_rule("place_mark")
        data = tracker.to_dict()
        restored = ConfidenceTracker.from_dict(data, gdl)
        rc = restored.get("place_mark")
        assert rc.score == tracker.get("place_mark").score

    def test_end_conditions_tracked(self):
        gdl = _load_gdl("tictactoe.json")
        tracker = ConfidenceTracker(gdl)
        assert tracker.get("end_win_0") is not None
        assert tracker.get("end_draw_1") is not None


# ============================================================
# Correction Detector Tests
# ============================================================

class TestCorrectionDetector:
    def test_detect_illegal_move(self):
        detector = CorrectionDetector("Tic-Tac-Toe")
        engine = GameEngine.from_file(os.path.join(EXAMPLES_DIR, "tictactoe.json"))
        state = engine.initial_state()
        # Create a bogus move
        bogus = Move("place_mark", {"target": GridSpace(5, 5)})
        event = detector.detect_illegal_move(state, bogus, engine.legal_moves(state))
        assert event.correction_type == CorrectionType.ILLEGAL_MOVE
        assert "place_mark" in event.candidate_rules

    def test_detect_outcome_surprise(self):
        detector = CorrectionDetector("Test")
        engine = GameEngine.from_file(os.path.join(EXAMPLES_DIR, "tictactoe.json"))
        state = engine.initial_state()

        # Set up expectation
        detector.update_expectations("player1", 0.8)
        result = GameResult("win", winner="player2")

        event = detector.detect_outcome_surprise(state, result, "player1", 0.8)
        assert event is not None
        assert event.correction_type == CorrectionType.OUTCOME_SURPRISE

    def test_no_surprise_when_expected(self):
        detector = CorrectionDetector("Test")
        engine = GameEngine.from_file(os.path.join(EXAMPLES_DIR, "tictactoe.json"))
        state = engine.initial_state()
        result = GameResult("win", winner="player1")
        event = detector.detect_outcome_surprise(state, result, "player1", 0.8)
        assert event is None

    def test_no_surprise_low_confidence(self):
        detector = CorrectionDetector("Test")
        engine = GameEngine.from_file(os.path.join(EXAMPLES_DIR, "tictactoe.json"))
        state = engine.initial_state()
        result = GameResult("win", winner="player2")
        event = detector.detect_outcome_surprise(state, result, "player1", 0.1)
        assert event is None

    def test_detect_explicit_correction(self):
        detector = CorrectionDetector("Test")
        engine = GameEngine.from_file(os.path.join(EXAMPLES_DIR, "tictactoe.json"))
        state = engine.initial_state()
        event = detector.detect_explicit_correction(
            state, "You can't place marks on occupied spaces"
        )
        assert event.correction_type == CorrectionType.EXPLICIT
        assert "occupied" in event.feedback_text

    def test_event_count(self):
        detector = CorrectionDetector("Test")
        engine = GameEngine.from_file(os.path.join(EXAMPLES_DIR, "tictactoe.json"))
        state = engine.initial_state()
        detector.detect_explicit_correction(state, "test1")
        detector.detect_explicit_correction(state, "test2")
        assert detector.correction_count == 2


# ============================================================
# Fault Diagnosis Tests
# ============================================================

class TestFaultDiagnoser:
    def test_diagnose_illegal_move(self):
        gdl = _load_gdl("tictactoe.json")
        tracker = ConfidenceTracker(gdl)
        diagnoser = FaultDiagnoser(gdl, tracker)
        detector = CorrectionDetector("TTT")

        engine = GameEngine.from_file(os.path.join(EXAMPLES_DIR, "tictactoe.json"))
        state = engine.initial_state()
        bogus = Move("place_mark", {"target": GridSpace(5, 5)})
        event = detector.detect_illegal_move(state, bogus, [])

        diagnosis = diagnoser.diagnose(event)
        assert diagnosis.primary_candidate is not None
        assert diagnosis.primary_candidate.rule_name == "place_mark"
        assert diagnosis.diagnosis_type == "rule_condition"

    def test_diagnose_explicit_about_win(self):
        gdl = _load_gdl("tictactoe.json")
        tracker = ConfidenceTracker(gdl)
        diagnoser = FaultDiagnoser(gdl, tracker)
        detector = CorrectionDetector("TTT")

        engine = GameEngine.from_file(os.path.join(EXAMPLES_DIR, "tictactoe.json"))
        state = engine.initial_state()
        event = detector.detect_explicit_correction(
            state, "The win condition should be 4 in a row, not 3"
        )

        diagnosis = diagnoser.diagnose(event)
        # Should identify end conditions as candidates
        assert any(c.rule_name.startswith("end_") for c in diagnosis.candidates)

    def test_diagnose_outcome_surprise(self):
        gdl = _load_gdl("tictactoe.json")
        tracker = ConfidenceTracker(gdl)
        diagnoser = FaultDiagnoser(gdl, tracker)
        detector = CorrectionDetector("TTT")

        engine = GameEngine.from_file(os.path.join(EXAMPLES_DIR, "tictactoe.json"))
        state = engine.initial_state()
        result = GameResult("win", winner="player2")
        event = detector.detect_outcome_surprise(state, result, "player1", 0.9)

        diagnosis = diagnoser.diagnose(event)
        assert diagnosis.diagnosis_type == "end_condition"
        assert len(diagnosis.candidates) > 0


# ============================================================
# Rule Revision Tests
# ============================================================

class TestRuleReviser:
    def test_add_condition(self):
        gdl = _load_gdl("tictactoe.json")
        tracker = ConfidenceTracker(gdl)
        reviser = RuleReviser(gdl, tracker)

        success = reviser.apply_direct_revision(
            rule_name="place_mark",
            revision_type="add_condition",
            old_value=None,
            new_value="turn_number > 0",
        )
        assert success
        rule = next(r for r in gdl["rules"] if r["name"] == "place_mark")
        assert "turn_number > 0" in rule["conditions"]
        assert len(reviser.revision_history) == 1

    def test_modify_condition(self):
        gdl = _load_gdl("tictactoe.json")
        tracker = ConfidenceTracker(gdl)
        reviser = RuleReviser(gdl, tracker)

        old_cond = gdl["rules"][0]["conditions"][0]
        success = reviser.apply_direct_revision(
            rule_name="place_mark",
            revision_type="modify_condition",
            old_value=old_cond,
            new_value="piece_at(target) == empty and turn_number > 0",
        )
        assert success
        rule = gdl["rules"][0]
        assert rule["conditions"][0] == "piece_at(target) == empty and turn_number > 0"

    def test_consistency_check_contradiction(self):
        gdl = _load_gdl("tictactoe.json")
        tracker = ConfidenceTracker(gdl)
        reviser = RuleReviser(gdl, tracker)

        from engine.corrections.revision import Revision
        rev = Revision(
            revision_id="test",
            rule_name="nonexistent_rule",
            revision_type="add_condition",
            description="test",
            new_value="test condition",
        )
        warnings = reviser.check_consistency(rev)
        assert len(warnings) > 0  # Rule not found warning


# ============================================================
# Correction Handler Integration Tests
# ============================================================

class TestCorrectionHandler:
    def test_handler_initialization(self):
        gdl = _load_gdl("tictactoe.json")
        handler = CorrectionHandler(gdl)
        assert handler.game_name == "Tic-Tac-Toe"
        assert not handler.has_corrections

    def test_successful_move_confirms(self):
        gdl = _load_gdl("tictactoe.json")
        handler = CorrectionHandler(gdl)
        engine = GameEngine.from_file(os.path.join(EXAMPLES_DIR, "tictactoe.json"))
        state = engine.initial_state()
        move = engine.legal_moves(state)[0]
        handler.on_successful_move(state, move)
        rc = handler.confidence.get("place_mark")
        assert rc.confirmations == 1

    def test_game_end_confirms_all(self):
        gdl = _load_gdl("tictactoe.json")
        handler = CorrectionHandler(gdl)
        engine = GameEngine.from_file(os.path.join(EXAMPLES_DIR, "tictactoe.json"))
        state = engine.initial_state()
        result = GameResult("draw")
        handler.on_game_end(state, result)
        assert handler.games_completed == 1

    def test_explicit_correction(self):
        gdl = _load_gdl("tictactoe.json")
        handler = CorrectionHandler(gdl)
        engine = GameEngine.from_file(os.path.join(EXAMPLES_DIR, "tictactoe.json"))
        state = engine.initial_state()
        diagnosis = handler.on_explicit_correction(
            state, "You should not be allowed to place marks after winning"
        )
        assert handler.has_corrections
        assert diagnosis is not None

    def test_callback_invoked(self):
        gdl = _load_gdl("tictactoe.json")
        handler = CorrectionHandler(gdl)
        events_received = []
        handler.set_callbacks(on_correction=lambda e: events_received.append(e))

        engine = GameEngine.from_file(os.path.join(EXAMPLES_DIR, "tictactoe.json"))
        state = engine.initial_state()
        handler.on_explicit_correction(state, "test feedback")
        assert len(events_received) == 1

    def test_summary(self):
        gdl = _load_gdl("tictactoe.json")
        handler = CorrectionHandler(gdl)
        summary = handler.summary()
        assert "game_name" in summary
        assert "confidence_summary" in summary


# ============================================================
# End-to-end: Wrong Rules → Correction → Fixed
# ============================================================

class TestWrongRulesConvergence:
    """Test that the system can fix deliberately wrong rules."""

    def test_fix_wrong_win_condition_ttt(self):
        """TTT with wrong win condition (4 in a row instead of 3).

        Correction: change win condition from >= 4 to >= 3.
        After correction, the engine should detect 3-in-a-row wins.
        """
        gdl = _load_gdl("tictactoe.json")

        # Deliberately break the win condition
        gdl["end_conditions"][0]["condition"] = \
            "any d in directions: line_length(last_placed, d, current_player) >= 4"

        handler = CorrectionHandler(gdl, auto_apply=False)
        engine = GameEngine(gdl)

        # Play a game where player 1 gets 3 in a row
        state = engine.initial_state()
        # X at (0,0)
        state = engine.apply_move(state, Move("place_mark", {"target": GridSpace(0, 0)}))
        # O at (1,0)
        state = engine.apply_move(state, Move("place_mark", {"target": GridSpace(1, 0)}))
        # X at (0,1)
        state = engine.apply_move(state, Move("place_mark", {"target": GridSpace(0, 1)}))
        # O at (1,1)
        state = engine.apply_move(state, Move("place_mark", {"target": GridSpace(1, 1)}))
        # X at (0,2) — should be 3 in a row across top
        state = engine.apply_move(state, Move("place_mark", {"target": GridSpace(0, 2)}))

        # With wrong rule (>= 4), this shouldn't be terminal
        result = engine.check_terminal(state)
        assert result is None, "Wrong win condition should not trigger for 3-in-a-row"

        # Now fix it via the handler
        handler.modify_end_condition(
            index=0,
            new_condition="any d in directions: line_length(last_placed, d, current_player) >= 3",
        )

        # Rebuild engine with corrected GDL
        fixed_engine = GameEngine(handler.get_gdl())

        # Replay the same game
        state2 = fixed_engine.initial_state()
        state2 = fixed_engine.apply_move(state2, Move("place_mark", {"target": GridSpace(0, 0)}))
        state2 = fixed_engine.apply_move(state2, Move("place_mark", {"target": GridSpace(1, 0)}))
        state2 = fixed_engine.apply_move(state2, Move("place_mark", {"target": GridSpace(0, 1)}))
        state2 = fixed_engine.apply_move(state2, Move("place_mark", {"target": GridSpace(1, 1)}))
        state2 = fixed_engine.apply_move(state2, Move("place_mark", {"target": GridSpace(0, 2)}))

        result2 = fixed_engine.check_terminal(state2)
        assert result2 is not None, "Fixed win condition should detect 3-in-a-row"
        assert result2.winner == "player1"

    def test_fix_wrong_rule_condition_nim(self):
        """Nim where taking from empty piles is incorrectly allowed.

        Start with a broken rule (no condition checking pile has stones),
        then add the correct condition.
        """
        gdl = _load_gdl("nim.json")

        # Break the rule: remove the condition
        gdl["rules"][0]["conditions"] = []

        handler = CorrectionHandler(gdl, auto_apply=False)
        engine = GameEngine(gdl)

        state = engine.initial_state()
        # Empty pile 0 first
        state = engine.apply_move(state, Move("take_stones", {"pile": TrackSpace(0), "amount": 3}))

        # With broken rules, taking from empty pile 0 is "legal"
        moves = engine.legal_moves(state)
        pile0_moves = [m for m in moves if m.params["pile"] == TrackSpace(0)]
        assert len(pile0_moves) > 0, "Broken rules allow taking from empty pile"

        # Fix it
        handler.add_rule_condition("take_stones", "count(pieces_at(pile)) >= amount")

        # Rebuild engine
        fixed_engine = GameEngine(handler.get_gdl())
        fixed_state = fixed_engine.initial_state()
        fixed_state = fixed_engine.apply_move(
            fixed_state, Move("take_stones", {"pile": TrackSpace(0), "amount": 3})
        )
        fixed_moves = fixed_engine.legal_moves(fixed_state)
        pile0_fixed = [m for m in fixed_moves if m.params["pile"] == TrackSpace(0)]
        assert len(pile0_fixed) == 0, "Fixed rules should prevent taking from empty pile"

    def test_correction_preserves_other_games(self):
        """Correcting one game's rules doesn't affect another game's stored GDL."""
        gdl_ttt = _load_gdl("tictactoe.json")
        gdl_nim = _load_gdl("nim.json")

        handler_ttt = CorrectionHandler(gdl_ttt)
        handler_nim = CorrectionHandler(gdl_nim)

        # Correct TTT
        engine = GameEngine.from_file(os.path.join(EXAMPLES_DIR, "tictactoe.json"))
        state = engine.initial_state()
        handler_ttt.on_explicit_correction(state, "test correction")

        # Nim should be unchanged
        assert handler_nim.corrections_applied == 0
        assert not handler_nim.has_corrections
        nim_rules = handler_nim.get_gdl()["rules"]
        original_nim = _load_gdl("nim.json")
        assert nim_rules[0]["conditions"] == original_nim["rules"][0]["conditions"]

    def test_confidence_evolves_over_games(self):
        """Confidence scores change as games are played."""
        gdl = _load_gdl("tictactoe.json")
        handler = CorrectionHandler(gdl)
        engine = GameEngine(gdl)

        initial_score = handler.confidence.get("place_mark").score

        # Simulate several successful games
        for _ in range(5):
            state = engine.initial_state()
            move = engine.legal_moves(state)[0]
            handler.on_successful_move(state, move)
            handler.on_game_end(state, GameResult("draw"))

        final_score = handler.confidence.get("place_mark").score
        assert final_score > initial_score, \
            f"Confidence should increase: {initial_score} → {final_score}"

    def test_handler_summary_complete(self):
        """Summary should include all relevant information."""
        gdl = _load_gdl("tictactoe.json")
        handler = CorrectionHandler(gdl)
        engine = GameEngine(gdl)
        state = engine.initial_state()

        handler.on_explicit_correction(state, "test")
        handler.on_game_end(state, GameResult("draw"))

        summary = handler.summary()
        assert summary["total_corrections"] >= 1
        assert summary["games_completed"] == 1
        assert len(summary["confidence_summary"]) > 0
