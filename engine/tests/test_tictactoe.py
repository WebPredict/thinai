"""End-to-end tests for Tic-Tac-Toe via the GDL engine."""

import os
import pytest
from engine.engine import GameEngine
from engine.gdl.board import GridSpace
from engine.gdl.state import Move


EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "games", "examples")


@pytest.fixture
def engine():
    return GameEngine.from_file(os.path.join(EXAMPLES_DIR, "tictactoe.json"))


@pytest.fixture
def state(engine):
    return engine.initial_state()


class TestInitialState:
    def test_empty_board(self, engine, state):
        for space in state.board.spaces:
            assert state.is_empty(space)

    def test_player1_starts(self, state):
        assert state.current_player == "player1"

    def test_nine_legal_moves(self, engine, state):
        moves = engine.legal_moves(state)
        assert len(moves) == 9

    def test_not_terminal(self, engine, state):
        assert engine.check_terminal(state) is None


class TestMoves:
    def test_place_reduces_legal_moves(self, engine, state):
        move = Move("place_mark", {"target": GridSpace(1, 1)})
        new_state = engine.apply_move(state, move)
        moves = engine.legal_moves(new_state)
        assert len(moves) == 8

    def test_place_sets_piece(self, engine, state):
        move = Move("place_mark", {"target": GridSpace(1, 1)})
        new_state = engine.apply_move(state, move)
        piece = new_state.get_piece(GridSpace(1, 1))
        assert piece is not None
        assert piece.name == "mark"
        assert piece.owner == "player1"

    def test_alternating_turns(self, engine, state):
        m1 = Move("place_mark", {"target": GridSpace(0, 0)})
        s1 = engine.apply_move(state, m1)
        assert s1.current_player == "player2"

        m2 = Move("place_mark", {"target": GridSpace(1, 1)})
        s2 = engine.apply_move(s1, m2)
        assert s2.current_player == "player1"

    def test_occupied_space_not_legal(self, engine, state):
        m1 = Move("place_mark", {"target": GridSpace(1, 1)})
        s1 = engine.apply_move(state, m1)
        moves = engine.legal_moves(s1)
        targets = [m.params["target"] for m in moves]
        assert GridSpace(1, 1) not in targets


class TestWinDetection:
    def _play_sequence(self, engine, state, spaces):
        """Play a sequence of moves alternating players."""
        s = state
        for space in spaces:
            move = Move("place_mark", {"target": space})
            s = engine.apply_move(s, move)
        return s

    def test_horizontal_win_row0(self, engine, state):
        # P1: (0,0), P2: (1,0), P1: (0,1), P2: (1,1), P1: (0,2) — P1 wins
        s = self._play_sequence(engine, state, [
            GridSpace(0, 0), GridSpace(1, 0),
            GridSpace(0, 1), GridSpace(1, 1),
            GridSpace(0, 2),
        ])
        result = engine.check_terminal(s)
        assert result is not None
        assert result.result_type == "win"
        assert result.winner == "player1"

    def test_horizontal_win_row1(self, engine, state):
        # P1: (1,0), P2: (0,0), P1: (1,1), P2: (0,1), P1: (1,2)
        s = self._play_sequence(engine, state, [
            GridSpace(1, 0), GridSpace(0, 0),
            GridSpace(1, 1), GridSpace(0, 1),
            GridSpace(1, 2),
        ])
        result = engine.check_terminal(s)
        assert result is not None
        assert result.winner == "player1"

    def test_vertical_win(self, engine, state):
        # P1: (0,0), P2: (0,1), P1: (1,0), P2: (1,1), P1: (2,0)
        s = self._play_sequence(engine, state, [
            GridSpace(0, 0), GridSpace(0, 1),
            GridSpace(1, 0), GridSpace(1, 1),
            GridSpace(2, 0),
        ])
        result = engine.check_terminal(s)
        assert result is not None
        assert result.winner == "player1"

    def test_diagonal_win(self, engine, state):
        # P1: (0,0), P2: (0,1), P1: (1,1), P2: (0,2), P1: (2,2)
        s = self._play_sequence(engine, state, [
            GridSpace(0, 0), GridSpace(0, 1),
            GridSpace(1, 1), GridSpace(0, 2),
            GridSpace(2, 2),
        ])
        result = engine.check_terminal(s)
        assert result is not None
        assert result.winner == "player1"

    def test_antidiagonal_win(self, engine, state):
        # P1: (0,2), P2: (0,0), P1: (1,1), P2: (1,0), P1: (2,0)
        s = self._play_sequence(engine, state, [
            GridSpace(0, 2), GridSpace(0, 0),
            GridSpace(1, 1), GridSpace(1, 0),
            GridSpace(2, 0),
        ])
        result = engine.check_terminal(s)
        assert result is not None
        assert result.winner == "player1"

    def test_player2_wins(self, engine, state):
        # P1: (0,0), P2: (1,0), P1: (0,1), P2: (1,1), P1: (2,2), P2: (1,2)
        s = self._play_sequence(engine, state, [
            GridSpace(0, 0), GridSpace(1, 0),
            GridSpace(0, 1), GridSpace(1, 1),
            GridSpace(2, 2), GridSpace(1, 2),
        ])
        result = engine.check_terminal(s)
        assert result is not None
        assert result.winner == "player2"

    def test_no_win_yet(self, engine, state):
        s = self._play_sequence(engine, state, [
            GridSpace(0, 0), GridSpace(1, 1),
        ])
        result = engine.check_terminal(s)
        assert result is None


class TestDraw:
    def test_draw_full_board(self, engine, state):
        """Play a game that ends in a draw.
           X O X
           X X O
           O X O
        """
        s = state
        moves = [
            GridSpace(0, 0),  # P1: X
            GridSpace(0, 1),  # P2: O
            GridSpace(0, 2),  # P1: X
            GridSpace(1, 2),  # P2: O
            GridSpace(1, 0),  # P1: X
            GridSpace(2, 0),  # P2: O
            GridSpace(1, 1),  # P1: X
            GridSpace(2, 2),  # P2: O
            GridSpace(2, 1),  # P1: X
        ]
        for space in moves:
            move = Move("place_mark", {"target": space})
            s = engine.apply_move(s, move)

        result = engine.check_terminal(s)
        assert result is not None
        assert result.result_type == "draw"


class TestFullGame:
    def test_play_random_game(self, engine, state):
        """Play a complete random game and verify it terminates."""
        import random
        random.seed(42)
        s = state
        for _ in range(9):  # Max 9 moves in TTT
            result = engine.check_terminal(s)
            if result:
                break
            moves = engine.legal_moves(s)
            assert len(moves) > 0
            move = random.choice(moves)
            s = engine.apply_move(s, move)

        # Game should have ended
        result = engine.check_terminal(s)
        assert result is not None

    def test_play_many_random_games(self, engine):
        """Play 100 random games — all should terminate properly."""
        import random
        random.seed(123)
        for _ in range(100):
            s = engine.initial_state()
            for _ in range(9):
                result = engine.check_terminal(s)
                if result:
                    break
                moves = engine.legal_moves(s)
                move = random.choice(moves)
                s = engine.apply_move(s, move)
            assert engine.check_terminal(s) is not None
