"""Tests for training infrastructure."""

import os
import random
import pytest
from engine.engine import GameEngine
from engine.training.runner import GameRunner, run_benchmark
from engine.training.opponents import RandomOpponent, ReasonerOpponent


EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "games", "examples")


@pytest.fixture
def ttt_engine():
    return GameEngine.from_file(os.path.join(EXAMPLES_DIR, "tictactoe.json"))


@pytest.fixture
def c4_engine():
    return GameEngine.from_file(os.path.join(EXAMPLES_DIR, "connect_four.json"))


class TestRandomOpponent:
    def test_chooses_legal_move(self, ttt_engine):
        random.seed(42)
        opp = RandomOpponent(ttt_engine)
        state = ttt_engine.initial_state()
        move = opp.choose_move(state)
        assert move is not None
        legal = ttt_engine.legal_moves(state)
        assert any(m.params == move.params for m in legal)


class TestGameRunner:
    def test_random_vs_random_ttt(self, ttt_engine):
        random.seed(42)
        runner = GameRunner(ttt_engine)
        p1 = RandomOpponent(ttt_engine)
        p2 = RandomOpponent(ttt_engine)
        results = runner.run(p1, p2, 20, "random", "random")

        assert results.total_games == 20
        assert results.player1_wins + results.player2_wins + results.draws == 20
        assert results.avg_game_length > 0

    def test_results_summary(self, ttt_engine):
        random.seed(42)
        runner = GameRunner(ttt_engine)
        p1 = RandomOpponent(ttt_engine)
        p2 = RandomOpponent(ttt_engine)
        results = runner.run(p1, p2, 5, "random", "random")
        summary = results.summary()
        assert "Tic-Tac-Toe" in summary
        assert "random" in summary

    def test_results_to_dict(self, ttt_engine):
        random.seed(42)
        runner = GameRunner(ttt_engine)
        p1 = RandomOpponent(ttt_engine)
        p2 = RandomOpponent(ttt_engine)
        results = runner.run(p1, p2, 5, "random", "random")
        d = results.to_dict()
        assert "player1_wins" in d
        assert "player1_win_rate" in d


class TestReasonerVsRandom:
    def test_reasoner_beats_random_ttt(self, ttt_engine):
        """Reasoner should dominate random in tic-tac-toe."""
        random.seed(42)
        runner = GameRunner(ttt_engine)
        p1 = ReasonerOpponent(ttt_engine, max_depth=9)
        p2 = RandomOpponent(ttt_engine)
        results = runner.run(p1, p2, 30, "reasoner", "random")

        assert results.player1_win_rate >= 0.80, \
            f"Reasoner win rate {results.player1_win_rate:.0%} too low"

    def test_reasoner_beats_random_c4(self, c4_engine):
        """Reasoner should beat random in connect four."""
        random.seed(42)
        runner = GameRunner(c4_engine)
        p1 = ReasonerOpponent(c4_engine, max_depth=4)
        p2 = RandomOpponent(c4_engine)
        results = runner.run(p1, p2, 10, "reasoner", "random")

        assert results.player1_win_rate >= 0.60, \
            f"Reasoner win rate {results.player1_win_rate:.0%} too low"
