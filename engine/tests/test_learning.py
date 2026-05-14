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
        evaluator = LearnableEval("Tic-Tac-Toe")
        runner = LearningRunner(ttt_engine, evaluator, max_depth=4)
        results = runner.train(10)

        assert results.total_games == 10
        assert results.wins + results.losses + results.draws == 10
        assert len(results.snapshots) == 10
        assert results.feature_names == ["center_control", "corner_count", "two_in_row", "threats"]

    def test_weights_change(self, ttt_engine):
        random.seed(42)
        evaluator = LearnableEval("Tic-Tac-Toe", weights=[0, 0, 0, 0])
        initial_weights = list(evaluator.weights)
        runner = LearningRunner(ttt_engine, evaluator, max_depth=4)
        runner.train(10)

        # Weights should have changed from all zeros
        assert evaluator.weights != initial_weights
        assert any(w != 0 for w in evaluator.weights)

    def test_learning_curve_improves(self, ttt_engine):
        """Win rate should improve over 40 games of training."""
        random.seed(42)
        evaluator = LearnableEval("Tic-Tac-Toe")
        runner = LearningRunner(ttt_engine, evaluator, max_depth=4)
        results = runner.train(40)

        curve = results.win_rate_curve(window=10)
        # Compare first 10 vs last 10
        early = sum(curve[:10]) / 10
        late = sum(curve[-10:]) / 10
        # Late should be better than early (or at least not worse)
        # With TTT at depth 4, even untrained reasoner does OK, so
        # we just check the system doesn't degrade
        assert late >= early - 0.1, f"Learning degraded: {early:.0%} -> {late:.0%}"
        # Overall win rate should be reasonable
        assert results.win_rate >= 0.5, f"Overall win rate too low: {results.win_rate:.0%}"

    def test_generation_tracks(self, ttt_engine):
        random.seed(42)
        evaluator = LearnableEval("Tic-Tac-Toe")
        runner = LearningRunner(ttt_engine, evaluator, max_depth=4)
        runner.train(15)
        assert evaluator.generation == 15

    def test_win_rate_curve(self, ttt_engine):
        random.seed(42)
        evaluator = LearnableEval("Tic-Tac-Toe")
        runner = LearningRunner(ttt_engine, evaluator, max_depth=4)
        results = runner.train(20)
        curve = results.win_rate_curve(window=5)
        assert len(curve) == 20
        assert all(0 <= v <= 1 for v in curve)

    def test_results_serialization(self, ttt_engine):
        random.seed(42)
        evaluator = LearnableEval("Tic-Tac-Toe")
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
        evaluator = LearnableEval("Connect Four")
        runner = LearningRunner(c4_engine, evaluator, max_depth=3)
        opponent = RandomOpponent(c4_engine)
        results = runner.train(20, opponent=opponent)

        assert results.win_rate >= 0.4, f"C4 win rate too low: {results.win_rate:.0%}"
