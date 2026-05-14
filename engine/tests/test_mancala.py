"""End-to-end tests for Mancala via the GDL engine."""

import os
import random
import pytest
from engine.engine import GameEngine
from engine.gdl.board import TrackSpace
from engine.gdl.state import Move


EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "games", "examples")


@pytest.fixture
def engine():
    return GameEngine.from_file(os.path.join(EXAMPLES_DIR, "mancala.json"))


@pytest.fixture
def state(engine):
    return engine.initial_state()


class TestInitialState:
    def test_board_type(self, state):
        from engine.gdl.board import TrackBoard
        assert isinstance(state.board, TrackBoard)
        assert state.board.length == 14
        assert state.board.loop is True

    def test_pit_stones(self, state):
        """Each pit starts with 4 stones."""
        for i in range(6):
            assert state.count_pieces_at(TrackSpace(i)) == 4, f"Pit {i} should have 4 stones"
        for i in range(7, 13):
            assert state.count_pieces_at(TrackSpace(i)) == 4, f"Pit {i} should have 4 stones"

    def test_stores_empty(self, state):
        assert state.count_pieces_at(TrackSpace(6)) == 0   # P1 store
        assert state.count_pieces_at(TrackSpace(13)) == 0  # P2 store

    def test_state_vars(self, state):
        assert state.state_vars["last_pit_is_store"] is False
        assert state.state_vars["last_pit_index"] == -1

    def test_player1_starts(self, state):
        assert state.current_player == "player1"

    def test_has_legal_moves(self, engine, state):
        moves = engine.legal_moves(state)
        assert len(moves) == 6  # P1 can pick any of their 6 pits

    def test_not_terminal(self, engine, state):
        assert engine.check_terminal(state) is None


class TestSowing:
    def test_basic_sow(self, engine, state):
        """Sowing from pit 0 (4 stones) distributes to pits 1,2,3,4."""
        move = _find_pit_move(engine, state, 0)
        new_state = engine.apply_move(state, move)

        assert new_state.count_pieces_at(TrackSpace(0)) == 0  # emptied
        assert new_state.count_pieces_at(TrackSpace(1)) == 5  # 4+1
        assert new_state.count_pieces_at(TrackSpace(2)) == 5
        assert new_state.count_pieces_at(TrackSpace(3)) == 5
        assert new_state.count_pieces_at(TrackSpace(4)) == 5

    def test_sow_into_store(self, engine, state):
        """Sowing from pit 2 (4 stones) distributes to 3,4,5,store."""
        move = _find_pit_move(engine, state, 2)
        new_state = engine.apply_move(state, move)

        assert new_state.count_pieces_at(TrackSpace(2)) == 0
        assert new_state.count_pieces_at(TrackSpace(3)) == 5
        assert new_state.count_pieces_at(TrackSpace(4)) == 5
        assert new_state.count_pieces_at(TrackSpace(5)) == 5
        assert new_state.count_pieces_at(TrackSpace(6)) == 1  # P1 store


class TestExtraTurn:
    def test_extra_turn_when_ending_in_store(self, engine, state):
        """If last stone lands in own store, same player goes again."""
        # Pit 2 has 4 stones: lands on 3,4,5,6(store) — extra turn
        move = _find_pit_move(engine, state, 2)
        new_state = engine.apply_move(state, move)

        # Should still be player1's turn
        assert new_state.current_player == "player1"

    def test_normal_turn_advance(self, engine, state):
        """If last stone doesn't land in store, turn advances."""
        # Pit 0 has 4 stones: lands on 1,2,3,4 — not in store
        move = _find_pit_move(engine, state, 0)
        new_state = engine.apply_move(state, move)

        assert new_state.current_player == "player2"


class TestFullGame:
    def test_random_game_terminates(self, engine):
        """A random game should eventually terminate."""
        random.seed(42)
        state = engine.initial_state()
        for _ in range(200):
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
            for _ in range(200):
                result = engine.check_terminal(state)
                if result:
                    break
                moves = engine.legal_moves(state)
                if not moves:
                    break
                state = engine.apply_move(state, random.choice(moves))
            assert engine.check_terminal(state) is not None, f"Game {game_num} didn't terminate"


def _find_pit_move(engine, state, pit_index):
    """Find the legal move for picking a specific pit."""
    moves = engine.legal_moves(state)
    for m in moves:
        pit = m.params.get("pit")
        if pit is not None and pit.index == pit_index:
            return m
    raise ValueError(f"No legal move for pit {pit_index}. Legal: {moves}")
