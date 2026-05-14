"""Tests for the constrained English parser."""

import random
import pytest
from engine.parser.parser import parse
from engine.parser.tokenizer import tokenize, get_section
from engine.engine import GameEngine
from engine.gdl.board import GridSpace
from engine.gdl.state import Move


TTT_ENGLISH = """
GAME: Tic-Tac-Toe
PLAYERS: 2, alternating turns

BOARD: 3x3 grid

PIECES: each player has a mark (X or O)

SETUP: board starts empty

MOVES:
  A player places their mark on any empty space.

WIN: A player wins by getting 3 of their marks in a row
     (horizontal, vertical, or diagonal).

DRAW: The game is a draw if the board is full with no winner.
"""

C4_ENGLISH = """
GAME: Connect Four
PLAYERS: 2, alternating turns

BOARD: 6x7 grid (6 rows, 7 columns)

PIECES: each player has discs

SETUP: board starts empty

MOVES:
  A player chooses a column that is not full.
  Their disc drops to the lowest empty row in that column.

WIN: A player wins by getting 4 of their discs in a row
     (horizontal, vertical, or diagonal).

DRAW: The game is a draw if the board is full with no winner.
"""


# --- Tokenizer tests ---

class TestTokenizer:
    def test_splits_sections(self):
        sections = tokenize(TTT_ENGLISH)
        keywords = [s.keyword for s in sections]
        assert "GAME" in keywords
        assert "BOARD" in keywords
        assert "WIN" in keywords

    def test_game_name(self):
        sections = tokenize(TTT_ENGLISH)
        game = get_section(sections, "GAME")
        assert "Tic-Tac-Toe" in game.content

    def test_all_sections_present_ttt(self):
        sections = tokenize(TTT_ENGLISH)
        expected = {"GAME", "PLAYERS", "BOARD", "PIECES", "SETUP", "MOVES", "WIN", "DRAW"}
        found = {s.keyword for s in sections}
        assert expected == found

    def test_multiline_content(self):
        sections = tokenize(C4_ENGLISH)
        moves = get_section(sections, "MOVES")
        lines = moves.lines()
        assert len(lines) == 2  # Two lines of move description


# --- Parser output tests ---

class TestParseTTT:
    def test_meta(self):
        gdl = parse(TTT_ENGLISH)
        assert gdl["meta"]["name"] == "Tic-Tac-Toe"
        assert gdl["meta"]["players"] == 2
        assert gdl["meta"]["turn_order"] == "alternating"

    def test_board(self):
        gdl = parse(TTT_ENGLISH)
        assert gdl["board"]["type"] == "grid"
        assert gdl["board"]["grid"]["rows"] == 3
        assert gdl["board"]["grid"]["cols"] == 3

    def test_pieces(self):
        gdl = parse(TTT_ENGLISH)
        assert len(gdl["pieces"]) == 1
        assert gdl["pieces"][0]["name"] == "mark"
        assert gdl["pieces"][0]["owner"] == "each"

    def test_setup_empty(self):
        gdl = parse(TTT_ENGLISH)
        assert gdl["setup"] == []

    def test_rules(self):
        gdl = parse(TTT_ENGLISH)
        assert len(gdl["rules"]) == 1
        rule = gdl["rules"][0]
        assert rule["action"] == "place"
        assert rule["params"][0]["select"] == "empty_space"

    def test_win_condition(self):
        gdl = parse(TTT_ENGLISH)
        wins = [ec for ec in gdl["end_conditions"] if ec["type"] == "win"]
        assert len(wins) == 1
        assert "line_length" in wins[0]["condition"]
        assert ">= 3" in wins[0]["condition"]

    def test_draw_condition(self):
        gdl = parse(TTT_ENGLISH)
        draws = [ec for ec in gdl["end_conditions"] if ec["type"] == "draw"]
        assert len(draws) == 1


class TestParseC4:
    def test_meta(self):
        gdl = parse(C4_ENGLISH)
        assert gdl["meta"]["name"] == "Connect Four"

    def test_board_dimensions(self):
        gdl = parse(C4_ENGLISH)
        assert gdl["board"]["grid"]["rows"] == 6
        assert gdl["board"]["grid"]["cols"] == 7

    def test_gravity_rule(self):
        gdl = parse(C4_ENGLISH)
        rule = gdl["rules"][0]
        assert rule["params"][0]["select"] == "int_range(0, 6)"
        assert any("lowest_empty_row" in e for e in rule["effects"])

    def test_win_line_4(self):
        gdl = parse(C4_ENGLISH)
        wins = [ec for ec in gdl["end_conditions"] if ec["type"] == "win"]
        assert ">= 4" in wins[0]["condition"]


# --- Round-trip tests: English → GDL → Engine → Play ---

class TestRoundTripTTT:
    def test_engine_loads(self):
        gdl = parse(TTT_ENGLISH)
        engine = GameEngine(gdl)
        state = engine.initial_state()
        assert state is not None

    def test_nine_legal_moves(self):
        gdl = parse(TTT_ENGLISH)
        engine = GameEngine(gdl)
        state = engine.initial_state()
        assert len(engine.legal_moves(state)) == 9

    def test_win_detection(self):
        gdl = parse(TTT_ENGLISH)
        engine = GameEngine(gdl)
        state = engine.initial_state()
        # Play a P1 horizontal win
        for space in [GridSpace(0,0), GridSpace(1,0), GridSpace(0,1), GridSpace(1,1), GridSpace(0,2)]:
            state = engine.apply_move(state, Move("place_mark", {"target": space}))
        result = engine.check_terminal(state)
        assert result is not None
        assert result.winner == "player1"

    def test_draw_detection(self):
        gdl = parse(TTT_ENGLISH)
        engine = GameEngine(gdl)
        state = engine.initial_state()
        # Play a known draw
        for space in [
            GridSpace(0,0), GridSpace(0,1), GridSpace(0,2),
            GridSpace(1,2), GridSpace(1,0), GridSpace(2,0),
            GridSpace(1,1), GridSpace(2,2), GridSpace(2,1),
        ]:
            state = engine.apply_move(state, Move("place_mark", {"target": space}))
        result = engine.check_terminal(state)
        assert result is not None
        assert result.result_type == "draw"

    def test_random_games_complete(self):
        random.seed(42)
        gdl = parse(TTT_ENGLISH)
        engine = GameEngine(gdl)
        for _ in range(50):
            state = engine.initial_state()
            for _ in range(9):
                result = engine.check_terminal(state)
                if result:
                    break
                moves = engine.legal_moves(state)
                state = engine.apply_move(state, random.choice(moves))
            assert engine.check_terminal(state) is not None


class TestRoundTripC4:
    def test_engine_loads(self):
        gdl = parse(C4_ENGLISH)
        engine = GameEngine(gdl)
        state = engine.initial_state()
        assert len(engine.legal_moves(state)) == 7

    def _drop(self, engine, state, col):
        """Helper: find the drop rule and apply it."""
        moves = engine.legal_moves(state)
        for m in moves:
            if m.params.get("column") == col:
                return engine.apply_move(state, m)
        raise ValueError(f"No legal move for column {col}")

    def test_gravity(self):
        gdl = parse(C4_ENGLISH)
        engine = GameEngine(gdl)
        state = engine.initial_state()
        state = self._drop(engine, state, 3)
        assert state.get_piece(GridSpace(5, 3)) is not None
        assert state.get_piece(GridSpace(5, 3)).owner == "player1"

    def test_horizontal_win(self):
        gdl = parse(C4_ENGLISH)
        engine = GameEngine(gdl)
        state = engine.initial_state()
        # P1 bottom row: cols 0,1,2,3. P2 stacks on top.
        for col in [0, 0, 1, 1, 2, 2, 3]:
            state = self._drop(engine, state, col)
        result = engine.check_terminal(state)
        assert result is not None
        assert result.winner == "player1"

    def test_random_games_complete(self):
        random.seed(42)
        gdl = parse(C4_ENGLISH)
        engine = GameEngine(gdl)
        for _ in range(20):
            state = engine.initial_state()
            for _ in range(42):
                result = engine.check_terminal(state)
                if result:
                    break
                moves = engine.legal_moves(state)
                state = engine.apply_move(state, random.choice(moves))
            assert engine.check_terminal(state) is not None
