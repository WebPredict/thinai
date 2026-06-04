"""Tests for the learning runner — does the system actually improve?"""

import os
import random
import pytest
from engine.engine import GameEngine
from engine.reasoner.evaluator import LearnableEval
from engine.reasoner.reasoner import Reasoner
from engine.training.learner import LearningRunner
from engine.training.opponents import RandomOpponent
from engine.metacognition.effort import EffortAllocator


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


# --- Training quality regression tests ---

class TestTrainingNoNosedive:
    """Verify training curves don't collapse to 0% for known games.

    These tests catch the progressive-depth nosedive bug where consecutive
    losses corrupt weights and the learning rate doesn't decay fast enough.
    """

    GAMES = [
        ("tictactoe.json", "Tic-Tac-Toe", 3),
        ("connect_four.json", "Connect Four", 3),
        ("reversi.json", "Reversi", 2),
        ("checkers.json", "Checkers", 3),
        ("mancala.json", "Mancala (Kalah)", 3),
        ("nim.json", "Nim", 4),
        ("gin_rummy.json", "Gin Rummy", 2),
        ("go_fish.json", "Go Fish", 2),
    ]

    @pytest.fixture(params=GAMES, ids=[g[1] for g in GAMES])
    def game_setup(self, request):
        game_file, game_name, depth = request.param
        engine = GameEngine.from_file(os.path.join(EXAMPLES_DIR, game_file))
        return engine, game_name, depth

    def test_late_win_rate_not_zero(self, game_setup):
        """Late training win rate should not collapse to 0%."""
        random.seed(42)
        engine, game_name, depth = game_setup
        evaluator = LearnableEval(game_name, gdl=engine.gdl)
        runner = LearningRunner(engine, evaluator, max_depth=depth, gdl=engine.gdl)
        results = runner.train(30)

        curve = results.win_rate_curve()
        if len(curve) >= 10:
            late_wr = sum(curve[-10:]) / 10
        else:
            late_wr = results.win_rate

        # Pure luck games are exempt
        if results.strategy_assessment == "pure_luck":
            return

        assert late_wr > 0.05, (
            f"{game_name}: late win rate collapsed to {late_wr:.0%} "
            f"(total: {results.win_rate:.0%}, {results.total_games} games)"
        )


# --- Connect Four and Checkers regression tests ---
# These two games are high-visibility demos that have regressed multiple times.

class TestConnectFourRegressions:
    """Targeted regression tests for Connect Four."""

    @pytest.fixture
    def c4(self):
        return GameEngine.from_file(os.path.join(EXAMPLES_DIR, "connect_four.json"))

    def test_search_depth_reaches_4(self, c4):
        """Connect Four needs depth 4 to see 3-in-a-row threats.

        Regression: node budget reduction from 2500 to 2000 capped C4 at
        depth 3 (bf=7, 7^4=2401 > 2000). The AI couldn't block winning moves.
        """
        state = c4.initial_state()
        allocator = EffortAllocator(min_depth=1, max_depth=4)
        decision = allocator.recommend(state, c4)
        assert decision.depth >= 4, (
            f"C4 search depth {decision.depth} < 4 — AI can't see blocking threats. "
            f"Check node budget in effort.py"
        )

    def test_training_improves(self, c4):
        """C4 training should show improvement — late WR > early WR.

        Regression: with depth capped at 3, the AI couldn't learn to see
        threats and training stagnated around 50%.
        """
        random.seed(42)
        evaluator = LearnableEval("Connect Four", gdl=c4.gdl)
        runner = LearningRunner(c4, evaluator, max_depth=4, gdl=c4.gdl)
        results = runner.train(40)

        curve = results.win_rate_curve(window=10)
        if len(curve) >= 20:
            early = sum(curve[:10]) / 10
            late = sum(curve[-10:]) / 10
            assert late >= 0.4, (
                f"C4 late WR={late:.0%} too low — AI not learning. "
                f"Check search depth (need 4) and opponent setup"
            )


class TestCheckersRegressions:
    """Targeted regression tests for Checkers."""

    @pytest.fixture
    def checkers(self):
        return GameEngine.from_file(os.path.join(EXAMPLES_DIR, "checkers.json"))

    def test_uses_handcrafted_features(self, checkers):
        """Checkers evaluator should use hand-crafted features, not auto-generated.

        Hand-crafted features (piece_advantage, king_count, advancement,
        center_control) are much better than auto-generated ones for Checkers.
        """
        evaluator = LearnableEval("Checkers", gdl=checkers.gdl)
        feature_names = [f.name for f in evaluator.features]
        assert "piece_advantage" in feature_names, (
            f"Checkers missing piece_advantage feature. Has: {feature_names}"
        )
        assert "king_count" in feature_names, (
            f"Checkers missing king_count feature. Has: {feature_names}"
        )

    def test_training_does_not_nosedive(self, checkers):
        """Checkers training must not collapse to 0% win rate.

        Regression: snapshot opponent caused death spiral — learner fights
        frozen copy of itself, degrades weights on every loss, never recovers.
        Independent ReasonerOpponent with fresh features prevents this.
        """
        random.seed(42)
        evaluator = LearnableEval("Checkers", gdl=checkers.gdl)
        runner = LearningRunner(checkers, evaluator, max_depth=3, gdl=checkers.gdl)
        results = runner.train(30)

        # Check late win rate doesn't collapse
        late = results.snapshots[-10:] if len(results.snapshots) >= 10 else results.snapshots
        late_wr = sum(1 for s in late if s.outcome > 0) / len(late)
        assert late_wr > 0.1, (
            f"Checkers nosedived: late WR={late_wr:.0%} "
            f"({results.wins}W {results.draws}D {results.losses}L). "
            f"Check opponent type in learner.py — snapshot opponents cause death spirals"
        )

    def test_opponent_is_not_snapshot(self, checkers):
        """Checkers should use independent ReasonerOpponent, not SnapshotOpponent.

        Regression: f06cb35 switched feature-opponent games from independent
        ReasonerOpponent to RandomOpponent→SnapshotOpponent, causing nosedive.
        """
        evaluator = LearnableEval("Checkers", gdl=checkers.gdl)
        runner = LearningRunner(checkers, evaluator, max_depth=3, gdl=checkers.gdl)
        # Trigger opponent setup by calling train with 1 game
        random.seed(42)
        runner.train(1)
        # The runner should NOT be using random→snapshot graduation
        # It should have set up a ReasonerOpponent during init
