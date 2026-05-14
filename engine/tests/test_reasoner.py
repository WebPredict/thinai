"""Tests for the strategic reasoner."""

import os
import pytest
from engine.engine import GameEngine
from engine.reasoner.reasoner import Reasoner
from engine.gdl.board import GridSpace
from engine.gdl.state import Move


EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "games", "examples")


@pytest.fixture
def ttt_engine():
    return GameEngine.from_file(os.path.join(EXAMPLES_DIR, "tictactoe.json"))


@pytest.fixture
def c4_engine():
    return GameEngine.from_file(os.path.join(EXAMPLES_DIR, "connect_four.json"))


class TestReasonerTTT:
    def test_chooses_a_move(self, ttt_engine):
        reasoner = Reasoner(ttt_engine, max_depth=4)
        state = ttt_engine.initial_state()
        move = reasoner.choose_move(state)
        assert move is not None

    def test_reasoner_wins_from_winning_position(self, ttt_engine):
        """From a position with an immediate win available, reasoner should win."""
        state = ttt_engine.initial_state()
        # P1 has (0,0) and (0,1) — can win at (0,2)
        state = ttt_engine.apply_move(state, Move("place_mark", {"target": GridSpace(0, 0)}))
        state = ttt_engine.apply_move(state, Move("place_mark", {"target": GridSpace(2, 0)}))
        state = ttt_engine.apply_move(state, Move("place_mark", {"target": GridSpace(0, 1)}))
        state = ttt_engine.apply_move(state, Move("place_mark", {"target": GridSpace(2, 1)}))
        # P1's move should lead to a P1 win
        reasoner = Reasoner(ttt_engine, max_depth=6)
        move = reasoner.choose_move(state)
        state = ttt_engine.apply_move(state, move)
        # Either P1 won immediately, or will win with continued play
        for _ in range(5):
            result = ttt_engine.check_terminal(state)
            if result:
                break
            m = Reasoner(ttt_engine, max_depth=6).choose_move(state)
            state = ttt_engine.apply_move(state, m)
        result = ttt_engine.check_terminal(state)
        assert result is not None
        assert result.winner == "player1"

    def test_takes_winning_move(self, ttt_engine):
        """If reasoner can win in one move, it should."""
        state = ttt_engine.initial_state()
        # Set up P1 with (0,0) and (0,1), P2 with (1,0) and (1,1)
        state = ttt_engine.apply_move(state, Move("place_mark", {"target": GridSpace(0, 0)}))
        state = ttt_engine.apply_move(state, Move("place_mark", {"target": GridSpace(1, 0)}))
        state = ttt_engine.apply_move(state, Move("place_mark", {"target": GridSpace(0, 1)}))
        state = ttt_engine.apply_move(state, Move("place_mark", {"target": GridSpace(1, 1)}))
        # P1's turn — should win at (0,2)
        reasoner = Reasoner(ttt_engine, max_depth=4)
        move = reasoner.choose_move(state)
        assert move.params["target"] == GridSpace(0, 2)

    def test_beats_random_ttt(self, ttt_engine):
        """Reasoner should beat random play >90% over 50 games."""
        import random
        random.seed(42)
        wins = 0
        games = 50

        for _ in range(games):
            state = ttt_engine.initial_state()
            reasoner = Reasoner(ttt_engine, max_depth=9)  # TTT is small enough for full search

            for _ in range(9):
                result = ttt_engine.check_terminal(state)
                if result:
                    if result.winner == "player1":
                        wins += 1
                    break

                if state.current_player == "player1":
                    move = reasoner.choose_move(state)
                else:
                    moves = ttt_engine.legal_moves(state)
                    move = random.choice(moves)
                state = ttt_engine.apply_move(state, move)

        win_rate = wins / games
        assert win_rate >= 0.85, f"Win rate too low: {win_rate:.0%}"


class TestReasonerC4:
    def test_chooses_a_move(self, c4_engine):
        reasoner = Reasoner(c4_engine, max_depth=4)
        state = c4_engine.initial_state()
        move = reasoner.choose_move(state)
        assert move is not None

    def test_beats_random_c4(self, c4_engine):
        """Reasoner should beat random play >80% over 20 games."""
        import random
        random.seed(42)
        wins = 0
        games = 20

        for _ in range(games):
            state = c4_engine.initial_state()
            reasoner = Reasoner(c4_engine, max_depth=4)

            for _ in range(42):
                result = c4_engine.check_terminal(state)
                if result:
                    if result.winner == "player1":
                        wins += 1
                    break

                if state.current_player == "player1":
                    move = reasoner.choose_move(state)
                else:
                    moves = c4_engine.legal_moves(state)
                    move = random.choice(moves)
                state = c4_engine.apply_move(state, move)

        win_rate = wins / games
        assert win_rate >= 0.70, f"Win rate too low: {win_rate:.0%}"
