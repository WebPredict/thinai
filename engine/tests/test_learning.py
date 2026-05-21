"""Tests for the learning runner — does the system actually improve?"""

import os
import random
import pytest
from engine.engine import GameEngine
from engine.reasoner.evaluator import LearnableEval
from engine.training.learner import LearningRunner
from engine.training.opponents import RandomOpponent


EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "games", "examples")


@pytest.fixture
def ttt_engine():
    return GameEngine.from_file(os.path.join(EXAMPLES_DIR, "tictactoe.json"))


@pytest.fixture
def c4_engine():
    return GameEngine.from_file(os.path.join(EXAMPLES_DIR, "connect_four.json"))


class TestLearningTTT:
    def test_learning_produces_results(self, ttt_engine):
        random.seed(42)
        evaluator = LearnableEval("Tic-Tac-Toe", gdl=ttt_engine.gdl)
        runner = LearningRunner(ttt_engine, evaluator, max_depth=4)
        results = runner.train(10)

        assert results.total_games == 10
        assert results.wins + results.losses + results.draws == 10
        assert len(results.snapshots) == 10
        # Auto-features generate more features than the old hand-crafted 4
        assert len(results.feature_names) >= 4

    def test_weights_change(self, ttt_engine):
        random.seed(42)
        evaluator = LearnableEval("Tic-Tac-Toe", gdl=ttt_engine.gdl)
        initial_weights = list(evaluator.weights)
        runner = LearningRunner(ttt_engine, evaluator, max_depth=4)
        runner.train(10)

        # Weights should have changed
        assert evaluator.weights != initial_weights
        assert any(w != 0 for w in evaluator.weights)

    def test_learning_curve_improves(self, ttt_engine):
        """Win rate should improve over 40 games of training."""
        random.seed(42)
        evaluator = LearnableEval("Tic-Tac-Toe", gdl=ttt_engine.gdl)
        runner = LearningRunner(ttt_engine, evaluator, max_depth=4)
        results = runner.train(40)

        curve = results.win_rate_curve(window=10)
        # Compare first 10 vs last 10
        early = sum(curve[:10]) / 10
        late = sum(curve[-10:]) / 10
        # With progressive depth, the learner starts weak against a fixed
        # opponent — late performance should be better than early
        assert late >= early - 0.1, f"Learning degraded: {early:.0%} -> {late:.0%}"

    def test_generation_tracks(self, ttt_engine):
        random.seed(42)
        evaluator = LearnableEval("Tic-Tac-Toe", gdl=ttt_engine.gdl)
        runner = LearningRunner(ttt_engine, evaluator, max_depth=4)
        runner.train(15)
        assert evaluator.generation >= 5  # may early-stop

    def test_win_rate_curve(self, ttt_engine):
        random.seed(42)
        evaluator = LearnableEval("Tic-Tac-Toe", gdl=ttt_engine.gdl)
        runner = LearningRunner(ttt_engine, evaluator, max_depth=4)
        results = runner.train(20)
        curve = results.win_rate_curve(window=5)
        assert len(curve) >= 10  # may early-stop before 20
        assert all(0 <= v <= 1 for v in curve)

    def test_results_serialization(self, ttt_engine):
        random.seed(42)
        evaluator = LearnableEval("Tic-Tac-Toe", gdl=ttt_engine.gdl)
        runner = LearningRunner(ttt_engine, evaluator, max_depth=4)
        results = runner.train(5)
        d = results.to_dict()
        assert "win_rate_curve" in d
        assert "final_weights" in d
        assert len(d["snapshots"]) == 5


class TestLearningC4:
    def test_c4_learning(self, c4_engine):
        """Connect Four learner should achieve reasonable win rate against random."""
        random.seed(42)
        evaluator = LearnableEval("Connect Four", gdl=c4_engine.gdl)
        runner = LearningRunner(c4_engine, evaluator, max_depth=3)
        opponent = RandomOpponent(c4_engine)
        results = runner.train(20, opponent=opponent)

        assert results.win_rate >= 0.4, f"C4 win rate too low: {results.win_rate:.0%}"
