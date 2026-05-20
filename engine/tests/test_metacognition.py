"""Tests for the metacognition system — effort allocation, confidence,
self-assessment, and clarification."""

import os
import json
import random
import pytest

from engine.engine import GameEngine
from engine.gdl.state import Move, GameResult
from engine.gdl.board import GridSpace, TrackSpace
from engine.reasoner.reasoner import Reasoner
from engine.reasoner.evaluator import LearnableEval
from engine.training.learner import LearningRunner
from engine.metacognition.effort import EffortAllocator, PositionAnalysis, EffortRecord
from engine.metacognition.confidence import DecisionConfidenceTracker, MoveConfidence
from engine.metacognition.self_assessment import SelfAssessor, GameSkillProfile
from engine.metacognition.clarifier import Clarifier, ClarificationUrgency


EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "games", "examples")


# ============================================================
# Effort Allocator Tests
# ============================================================

class TestEffortAllocator:
    def test_basic_recommendation(self):
        allocator = EffortAllocator(min_depth=1, max_depth=5)
        engine = GameEngine.from_file(os.path.join(EXAMPLES_DIR, "tictactoe.json"))
        state = engine.initial_state()
        decision = allocator.recommend(state, engine)
        assert 1 <= decision.depth <= 5
        assert decision.max_nodes > 0
        assert len(decision.reason) > 0

    def test_fewer_moves_deeper_search(self):
        """With fewer legal moves, the allocator should recommend deeper search."""
        allocator = EffortAllocator()
        # Simulate low branching
        analysis_low = PositionAnalysis(branching_factor=2, game_phase=0.5, piece_count=5)
        analysis_high = PositionAnalysis(branching_factor=25, game_phase=0.5, piece_count=5)
        depth_low = allocator._heuristic_depth(analysis_low)
        depth_high = allocator._heuristic_depth(analysis_high)
        assert depth_low > depth_high

    def test_endgame_bonus(self):
        """Endgame positions should get deeper search."""
        allocator = EffortAllocator()
        early = PositionAnalysis(branching_factor=10, game_phase=0.1, piece_count=5)
        late = PositionAnalysis(branching_factor=10, game_phase=0.8, piece_count=5)
        assert allocator._heuristic_depth(late) > allocator._heuristic_depth(early)

    def test_learning_from_history(self):
        allocator = EffortAllocator()
        # Record some outcomes
        for _ in range(5):
            allocator.record_outcome(EffortRecord(
                depth_used=2, nodes_searched=100,
                branching_factor=8, game_phase=0.5, outcome=-1.0,
            ))
        allocator.learn_from_history()
        # After losing at depth 2, should recommend deeper
        key = (1, 1)  # phase=0.5→bucket 1, branch=8→bucket 1
        assert allocator._adjustments.get(key, 0) > 0

    def test_depth_clamped(self):
        allocator = EffortAllocator(min_depth=2, max_depth=4)
        engine = GameEngine.from_file(os.path.join(EXAMPLES_DIR, "tictactoe.json"))
        state = engine.initial_state()
        decision = allocator.recommend(state, engine)
        assert 2 <= decision.depth <= 4

    def test_serialization(self):
        allocator = EffortAllocator()
        allocator._adjustments[(1, 2)] = 0.5
        data = allocator.to_dict()
        restored = EffortAllocator.from_dict(data)
        assert restored._adjustments[(1, 2)] == 0.5

    def test_stats(self):
        allocator = EffortAllocator()
        engine = GameEngine.from_file(os.path.join(EXAMPLES_DIR, "tictactoe.json"))
        state = engine.initial_state()
        allocator.recommend(state, engine)
        stats = allocator.stats()
        assert stats["total_decisions"] == 1


# ============================================================
# Decision Confidence Tests
# ============================================================

class TestDecisionConfidence:
    def test_score_move_basic(self):
        tracker = DecisionConfidenceTracker()
        mc = tracker.score_move(best_score=100.0, second_score=50.0, depth=3, branching=9)
        assert isinstance(mc, MoveConfidence)
        assert 0 <= mc.calibrated <= 1
        assert mc.gap_to_second == 50.0

    def test_large_gap_higher_confidence(self):
        tracker = DecisionConfidenceTracker()
        mc_large = tracker.score_move(100.0, 10.0, depth=3, branching=5)
        mc_small = tracker.score_move(100.0, 95.0, depth=3, branching=5)
        assert mc_large.calibrated > mc_small.calibrated

    def test_single_move_confidence(self):
        """Only one legal move — confidence from eval magnitude."""
        tracker = DecisionConfidenceTracker()
        mc = tracker.score_move(best_score=500.0, second_score=None, depth=3, branching=1)
        assert mc.branching_factor == 1

    def test_confidence_levels(self):
        mc_high = MoveConfidence(100, 50, 4, 5, calibrated=0.9)
        mc_low = MoveConfidence(100, 2, 1, 20, calibrated=0.2)
        assert mc_high.level == "very confident"
        assert mc_low.level == "very unsure"

    def test_game_end_updates_calibration(self):
        tracker = DecisionConfidenceTracker()
        # Make some predictions
        tracker.score_move(100.0, 50.0, 3, 5)
        tracker.score_move(80.0, 40.0, 3, 5)
        # End game — won
        tracker.on_game_end("player1", "player1")
        assert tracker.total_moves_scored == 2
        # Calibration should have data now
        report = tracker.calibration_report()
        assert len(report) > 0

    def test_calibration_report(self):
        tracker = DecisionConfidenceTracker()
        for _ in range(10):
            tracker.score_move(100.0, 50.0, 3, 5)
        tracker.on_game_end("player1", "player1")
        report = tracker.calibration_report()
        for entry in report:
            assert "predicted" in entry
            assert "actual" in entry


# ============================================================
# Self-Assessment Tests
# ============================================================

class TestSelfAssessment:
    def test_empty_assessment(self):
        assessor = SelfAssessor()
        profile = assessor.assess("Chess")
        assert profile.games_played == 0
        assert profile.skill_level == "untrained"

    def test_record_games(self):
        assessor = SelfAssessor()
        for _ in range(8):
            assessor.record_game("TTT", 1.0)
        for _ in range(2):
            assessor.record_game("TTT", -1.0)
        profile = assessor.assess("TTT")
        assert profile.games_played == 10
        assert profile.wins == 8
        assert profile.skill_level == "strong"

    def test_trend_detection(self):
        assessor = SelfAssessor()
        # First 5 losses, then 5 wins = improving
        for _ in range(5):
            assessor.record_game("Reversi", -1.0)
        for _ in range(5):
            assessor.record_game("Reversi", 1.0)
        profile = assessor.assess("Reversi")
        assert profile.trend == "improving"

    def test_multiple_games(self):
        assessor = SelfAssessor()
        for _ in range(10):
            assessor.record_game("TTT", 1.0)
        for _ in range(10):
            assessor.record_game("Reversi", -1.0)
        profiles = assessor.assess_all()
        assert len(profiles) == 2
        assert profiles[0].game_name == "TTT"  # higher win rate first

    def test_describe(self):
        assessor = SelfAssessor()
        for _ in range(10):
            assessor.record_game("Mancala", 1.0)
        profile = assessor.assess("Mancala")
        desc = profile.describe()
        assert "Mancala" in desc
        assert "well" in desc or "competent" in desc or "100%" in desc

    def test_describe_all(self):
        assessor = SelfAssessor()
        for _ in range(10):
            assessor.record_game("TTT", 1.0)
        text = assessor.describe_all()
        assert "TTT" in text


# ============================================================
# Clarifier Tests
# ============================================================

class TestClarifier:
    def test_check_no_draw(self):
        """Game with win but no draw should trigger a question."""
        gdl = {
            "meta": {"name": "Test", "players": 2, "turn_order": "alternating"},
            "rules": [{"name": "move", "conditions": ["true"], "effects": []}],
            "end_conditions": [{"type": "win", "condition": "false"}],
        }
        clarifier = Clarifier()
        questions = clarifier.check_rule_gaps(gdl)
        assert any("draw" in q.question_text.lower() for q in questions)

    def test_check_no_rules(self):
        gdl = {
            "meta": {"name": "Test", "players": 2, "turn_order": "alternating"},
            "rules": [],
            "end_conditions": [],
        }
        clarifier = Clarifier()
        questions = clarifier.check_rule_gaps(gdl)
        assert any(q.urgency == ClarificationUrgency.HIGH for q in questions)

    def test_check_conditional_no_turn_rule(self):
        gdl = {
            "meta": {"name": "Test", "players": 2, "turn_order": "conditional"},
            "rules": [{"name": "move", "conditions": [], "effects": []}],
            "end_conditions": [],
        }
        clarifier = Clarifier()
        questions = clarifier.check_rule_gaps(gdl)
        assert any("turn" in q.question_text.lower() for q in questions)

    def test_play_confusion_low_confidence(self):
        clarifier = Clarifier()
        q = clarifier.check_play_confusion(0.1, "Reversi")
        assert q is not None
        assert "unsure" in q.question_text.lower()

    def test_play_confusion_adequate_confidence(self):
        clarifier = Clarifier()
        q = clarifier.check_play_confusion(0.6, "Reversi")
        assert q is None

    def test_resolve_question(self):
        clarifier = Clarifier()
        clarifier.check_play_confusion(0.1, "Test")
        assert len(clarifier.unresolved) == 1
        clarifier.resolve(0, "Yes, keep playing")
        assert len(clarifier.unresolved) == 0

    def test_real_game_check(self):
        """Check a real game GDL for gaps — should find minimal issues."""
        with open(os.path.join(EXAMPLES_DIR, "tictactoe.json")) as f:
            gdl = json.load(f)
        clarifier = Clarifier()
        questions = clarifier.check_rule_gaps(gdl)
        # TTT is well-defined, should have no high-urgency issues
        high = [q for q in questions if q.urgency == ClarificationUrgency.HIGH]
        assert len(high) == 0


# ============================================================
# Integration: Reasoner with Metacognition
# ============================================================

class TestReasonerMetacognition:
    def test_reasoner_with_allocator(self):
        """Reasoner should use effort allocator for depth."""
        engine = GameEngine.from_file(os.path.join(EXAMPLES_DIR, "tictactoe.json"))
        allocator = EffortAllocator(min_depth=1, max_depth=3)
        reasoner = Reasoner(engine, max_depth=6, effort_allocator=allocator)
        state = engine.initial_state()
        move = reasoner.choose_move(state)
        assert move is not None
        assert 1 <= reasoner.last_depth_used <= 3  # allocator's range, not fixed 6

    def test_reasoner_with_confidence(self):
        """Reasoner should produce confidence scores."""
        engine = GameEngine.from_file(os.path.join(EXAMPLES_DIR, "tictactoe.json"))
        tracker = DecisionConfidenceTracker()
        reasoner = Reasoner(engine, max_depth=2, confidence_tracker=tracker)
        state = engine.initial_state()
        move = reasoner.choose_move(state)
        assert move is not None
        assert reasoner.last_confidence is not None
        assert 0 <= reasoner.last_confidence.calibrated <= 1

    def test_reasoner_without_metacognition(self):
        """Reasoner should still work without metacognition (backward compat)."""
        engine = GameEngine.from_file(os.path.join(EXAMPLES_DIR, "tictactoe.json"))
        reasoner = Reasoner(engine, max_depth=2)
        state = engine.initial_state()
        move = reasoner.choose_move(state)
        assert move is not None
        assert reasoner.last_confidence is None

    def test_training_with_metacognition(self):
        """Training loop should work with metacognition components."""
        random.seed(42)
        engine = GameEngine.from_file(os.path.join(EXAMPLES_DIR, "tictactoe.json"))
        evaluator = LearnableEval("Tic-Tac-Toe", gdl=engine.gdl)
        allocator = EffortAllocator(min_depth=1, max_depth=3)
        conf_tracker = DecisionConfidenceTracker()
        assessor = SelfAssessor()

        runner = LearningRunner(
            engine, evaluator, max_depth=2,
            effort_allocator=allocator,
            confidence_tracker=conf_tracker,
            self_assessor=assessor,
        )
        results = runner.train(5)
        assert results.total_games == 5

        # Self-assessor should have recorded games
        profile = assessor.assess("Tic-Tac-Toe")
        assert profile.games_played == 5

        # Confidence tracker should have scored moves
        assert conf_tracker.total_moves_scored > 0
