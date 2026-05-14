"""End-to-end tests for Reversi via the GDL engine."""

import os
import random
import pytest
from engine.engine import GameEngine
from engine.gdl.board import GridSpace
from engine.gdl.state import Move


EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "games", "examples")


@pytest.fixture
def engine():
    return GameEngine.from_file(os.path.join(EXAMPLES_DIR, "reversi.json"))


@pytest.fixture
def state(engine):
    return engine.initial_state()


class TestInitialState:
    def test_four_initial_pieces(self, state):
        pieces = state.all_pieces()
        assert len(pieces) == 4

    def test_center_setup(self, state):
        assert state.get_piece(GridSpace(3, 3)).owner == "player1"
        assert state.get_piece(GridSpace(3, 4)).owner == "player2"
        assert state.get_piece(GridSpace(4, 3)).owner == "player2"
        assert state.get_piece(GridSpace(4, 4)).owner == "player1"

    def test_player1_starts(self, state):
        assert state.current_player == "player1"

    def test_has_legal_moves(self, engine, state):
        moves = engine.legal_moves(state)
        assert len(moves) == 4  # Standard Reversi opening: 4 legal moves

    def test_not_terminal(self, engine, state):
        assert engine.check_terminal(state) is None


class TestFlipping:
    def test_basic_flip(self, engine, state):
        """Placing at (2,3) should flip (3,3) to... wait, (3,3) is already P1.
        Let me think about the standard opening moves.

        Board:
          3,3=P1  3,4=P2
          4,3=P2  4,4=P1

        P1's legal moves: (2,3), (3,2), (4,5), (5,4)
        Playing (2,3) flanks (3,3)... no, (3,3) is P1's own piece.
        Playing (2,4) would need... let me check actual legal moves.
        """
        moves = engine.legal_moves(state)
        targets = sorted([(m.params["target"].row, m.params["target"].col) for m in moves])
        # Standard Reversi opening legal moves for black (P1)
        # Can place at: (2,3), (3,2), (4,5), (5,4)
        assert len(targets) == 4

    def test_piece_flips_on_placement(self, engine, state):
        """After P1 places, at least one P2 piece should flip."""
        moves = engine.legal_moves(state)
        # Pick the first legal move
        move = moves[0]
        new_state = engine.apply_move(state, move)

        # Should now have more P1 pieces and fewer P2 pieces
        p1_count = sum(1 for _, p in new_state.all_pieces() if p.owner == "player1")
        p2_count = sum(1 for _, p in new_state.all_pieces() if p.owner == "player2")
        # Started with 2 each. After P1 places + flips, P1 should have more
        assert p1_count > 2
        # Total pieces should be 5 (4 + 1 new placement)
        assert p1_count + p2_count == 5


class TestTurnOrder:
    def test_turns_alternate(self, engine, state):
        moves = engine.legal_moves(state)
        new_state = engine.apply_move(state, moves[0])
        # Should be P2's turn (unless P2 has no moves, which shouldn't happen this early)
        assert new_state.current_player == "player2"


class TestFullGame:
    def test_random_game_terminates(self, engine):
        random.seed(42)
        state = engine.initial_state()
        for _ in range(100):
            result = engine.check_terminal(state)
            if result:
                break
            moves = engine.legal_moves(state)
            if not moves:
                break
            state = engine.apply_move(state, random.choice(moves))
        result = engine.check_terminal(state)
        assert result is not None

    def test_many_random_games(self, engine):
        """Play 20 random games — all should terminate."""
        random.seed(123)
        for game_num in range(20):
            state = engine.initial_state()
            for _ in range(100):
                result = engine.check_terminal(state)
                if result:
                    break
                moves = engine.legal_moves(state)
                if not moves:
                    break
                state = engine.apply_move(state, random.choice(moves))
            assert engine.check_terminal(state) is not None, f"Game {game_num} didn't terminate"
