"""Tests for board model and game state."""

import json
import os
import pytest
from engine.gdl.board import GridBoard, TrackBoard, GridSpace, TrackSpace, create_board
from engine.gdl.state import Piece, GameState, Move, setup_initial_state


EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "games", "examples")


def load_gdl(name):
    with open(os.path.join(EXAMPLES_DIR, name)) as f:
        return json.load(f)


# --- Board tests ---

class TestGridBoard:
    def test_create_3x3(self):
        board = GridBoard(3, 3)
        assert len(board.spaces) == 9
        assert board.rows == 3
        assert board.cols == 3

    def test_create_6x7(self):
        board = GridBoard(6, 7)
        assert len(board.spaces) == 42

    def test_space_at(self):
        board = GridBoard(3, 3)
        assert board.space_at(0, 0) == GridSpace(0, 0)
        assert board.space_at(2, 2) == GridSpace(2, 2)
        assert board.space_at(3, 0) is None  # out of bounds
        assert board.space_at(-1, 0) is None

    def test_neighbors_center_rect8(self):
        board = GridBoard(3, 3, "rect8")
        center = GridSpace(1, 1)
        neighbors = board.neighbors(center)
        assert len(neighbors) == 8  # all 8 surrounding cells

    def test_neighbors_corner_rect8(self):
        board = GridBoard(3, 3, "rect8")
        corner = GridSpace(0, 0)
        neighbors = board.neighbors(corner)
        assert len(neighbors) == 3  # (0,1), (1,0), (1,1)

    def test_neighbors_rect4(self):
        board = GridBoard(3, 3, "rect4")
        center = GridSpace(1, 1)
        neighbors = board.neighbors(center)
        assert len(neighbors) == 4

    def test_directions_rect8(self):
        board = GridBoard(3, 3, "rect8")
        assert len(board.directions()) == 8

    def test_directions_rect4(self):
        board = GridBoard(3, 3, "rect4")
        assert len(board.directions()) == 4

    def test_from_gdl(self):
        gdl = load_gdl("tictactoe.json")
        board = GridBoard.from_gdl(gdl["board"])
        assert board.rows == 3
        assert board.cols == 3
        assert board.topology == "rect8"

    def test_from_gdl_connect_four(self):
        gdl = load_gdl("connect_four.json")
        board = GridBoard.from_gdl(gdl["board"])
        assert board.rows == 6
        assert board.cols == 7


class TestTrackBoard:
    def test_create(self):
        board = TrackBoard(14, loop=True)
        assert len(board.spaces) == 14
        assert board.loop is True

    def test_space_at_linear(self):
        board = TrackBoard(10, loop=False)
        assert board.space_at(0) == TrackSpace(0)
        assert board.space_at(9) == TrackSpace(9)
        assert board.space_at(10) is None

    def test_space_at_loop(self):
        board = TrackBoard(14, loop=True)
        assert board.space_at(14) == TrackSpace(0)  # wraps
        assert board.space_at(15) == TrackSpace(1)

    def test_next_space(self):
        board = TrackBoard(14, loop=True)
        assert board.next_space(TrackSpace(13)) == TrackSpace(0)

    def test_from_gdl(self):
        gdl = load_gdl("mancala.json")
        board = TrackBoard.from_gdl(gdl["board"])
        assert board.length == 14
        assert board.loop is True


class TestCreateBoard:
    def test_grid(self):
        board = create_board({"type": "grid", "grid": {"rows": 3, "cols": 3}})
        assert isinstance(board, GridBoard)

    def test_track(self):
        board = create_board({"type": "track", "track": {"length": 14, "loop": True}})
        assert isinstance(board, TrackBoard)

    def test_unsupported(self):
        with pytest.raises(ValueError):
            create_board({"type": "hexmap"})


# --- Piece tests ---

class TestPiece:
    def test_owned_piece(self):
        p = Piece("mark", "player1")
        assert p.name == "mark"
        assert p.owner == "player1"

    def test_unowned_piece(self):
        p = Piece("stone", None)
        assert p.owner is None

    def test_equality(self):
        assert Piece("mark", "player1") == Piece("mark", "player1")
        assert Piece("mark", "player1") != Piece("mark", "player2")

    def test_hashable(self):
        # Pieces are frozen dataclasses, should be hashable
        s = {Piece("mark", "player1"), Piece("mark", "player2")}
        assert len(s) == 2


# --- GameState tests ---

class TestGameState:
    def test_empty_grid_state(self):
        board = GridBoard(3, 3)
        state = GameState(board)
        assert state.current_player == "player1"
        assert state.turn_number == 1
        for space in board.spaces:
            assert state.is_empty(space)

    def test_set_and_get_piece(self):
        board = GridBoard(3, 3)
        state = GameState(board)
        p = Piece("mark", "player1")
        space = GridSpace(1, 1)
        state.set_piece(space, p)
        assert state.get_piece(space) == p
        assert not state.is_empty(space)

    def test_remove_piece(self):
        board = GridBoard(3, 3)
        state = GameState(board)
        p = Piece("mark", "player1")
        space = GridSpace(1, 1)
        state.set_piece(space, p)
        state.set_piece(space, None)
        assert state.is_empty(space)

    def test_add_pieces_stacking(self):
        board = TrackBoard(14, loop=True)
        state = GameState(board)
        space = TrackSpace(0)
        for _ in range(4):
            state.add_piece(space, Piece("stone", None))
        assert state.count_pieces_at(space) == 4

    def test_opponent(self):
        board = GridBoard(3, 3)
        state = GameState(board)
        assert state.opponent("player1") == "player2"
        assert state.opponent("player2") == "player1"
        assert state.opponent() == "player2"  # default is current_player

    def test_copy(self):
        board = GridBoard(3, 3)
        state = GameState(board)
        state.set_piece(GridSpace(0, 0), Piece("mark", "player1"))
        state.state_vars["score"] = 10

        copy = state.copy()
        # Modify copy, original unchanged
        copy.set_piece(GridSpace(1, 1), Piece("mark", "player2"))
        copy.state_vars["score"] = 20

        assert state.get_piece(GridSpace(1, 1)) is None
        assert state.state_vars["score"] == 10

    def test_board_hash_deterministic(self):
        board = GridBoard(3, 3)
        s1 = GameState(board)
        s1.set_piece(GridSpace(0, 0), Piece("mark", "player1"))

        s2 = GameState(board)
        s2.set_piece(GridSpace(0, 0), Piece("mark", "player1"))

        assert s1.board_hash() == s2.board_hash()

    def test_board_hash_differs(self):
        board = GridBoard(3, 3)
        s1 = GameState(board)
        s1.set_piece(GridSpace(0, 0), Piece("mark", "player1"))

        s2 = GameState(board)
        s2.set_piece(GridSpace(0, 0), Piece("mark", "player2"))

        assert s1.board_hash() != s2.board_hash()

    def test_all_pieces(self):
        board = GridBoard(3, 3)
        state = GameState(board)
        state.set_piece(GridSpace(0, 0), Piece("X", "player1"))
        state.set_piece(GridSpace(1, 1), Piece("O", "player2"))
        pieces = state.all_pieces()
        assert len(pieces) == 2


# --- Setup tests ---

class TestSetup:
    def test_tictactoe_setup(self):
        gdl = load_gdl("tictactoe.json")
        state = setup_initial_state(gdl)
        assert isinstance(state.board, GridBoard)
        assert state.board.rows == 3
        # Board should be empty
        for space in state.board.spaces:
            assert state.is_empty(space)

    def test_connect_four_setup(self):
        gdl = load_gdl("connect_four.json")
        state = setup_initial_state(gdl)
        assert isinstance(state.board, GridBoard)
        assert state.board.rows == 6
        assert state.board.cols == 7
        for space in state.board.spaces:
            assert state.is_empty(space)

    def test_reversi_setup(self):
        gdl = load_gdl("reversi.json")
        state = setup_initial_state(gdl)
        assert isinstance(state.board, GridBoard)
        # Should have 4 initial pieces
        pieces = state.all_pieces()
        assert len(pieces) == 4
        # Center positions should be filled
        assert state.get_piece(GridSpace(3, 3)) is not None
        assert state.get_piece(GridSpace(3, 4)) is not None
        assert state.get_piece(GridSpace(4, 3)) is not None
        assert state.get_piece(GridSpace(4, 4)) is not None

    def test_mancala_setup(self):
        gdl = load_gdl("mancala.json")
        state = setup_initial_state(gdl)
        assert isinstance(state.board, TrackBoard)
        # Pits 0-5 should have 4 stones each
        for i in range(6):
            assert state.count_pieces_at(TrackSpace(i)) == 4
        # Stores should be empty
        assert state.count_pieces_at(TrackSpace(6)) == 0
        assert state.count_pieces_at(TrackSpace(13)) == 0
        # Pits 7-12 should have 4 stones each
        for i in range(7, 13):
            assert state.count_pieces_at(TrackSpace(i)) == 4
        # State vars initialized
        assert state.state_vars["last_pit_is_store"] is False
        assert state.state_vars["last_pit_index"] == -1
