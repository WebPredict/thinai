"""Tests for the expression parser and evaluator."""

import pytest
from engine.gdl.expr_parser import (
    parse_condition, parse_effect,
    Literal, Identifier, FuncCall, BinOp, Quantified, SelectorExpr,
    PlaceEffect, SetEffect, IfEffect, ForEffect,
)
from engine.gdl.expr_eval import evaluate, execute_effect, EvalContext, _line_length, _lowest_empty_row, _flanks
from engine.gdl.state import GameState, Piece
from engine.gdl.board import GridBoard, GridSpace


def make_ctx(rows=3, cols=3) -> EvalContext:
    """Create a test context with an empty grid board."""
    board = GridBoard(rows, cols)
    state = GameState(board)
    return EvalContext(state)


# --- Parser tests ---

class TestParseConditions:
    def test_literal_true(self):
        ast = parse_condition("true")
        assert isinstance(ast, Literal)
        assert ast.value is True

    def test_literal_false(self):
        ast = parse_condition("false")
        assert isinstance(ast, Literal)
        assert ast.value is False

    def test_literal_number(self):
        ast = parse_condition("42")
        assert isinstance(ast, Literal)
        assert ast.value == 42

    def test_identifier(self):
        ast = parse_condition("target")
        assert isinstance(ast, Identifier)
        assert ast.name == "target"

    def test_current_player(self):
        ast = parse_condition("current_player")
        assert isinstance(ast, Identifier)
        assert ast.name == "current_player"

    def test_empty(self):
        ast = parse_condition("empty")
        assert isinstance(ast, Literal)
        assert ast.value is None

    def test_comparison_eq(self):
        ast = parse_condition("piece_at(target) == empty")
        assert isinstance(ast, BinOp)
        assert ast.op == "=="

    def test_comparison_gte(self):
        ast = parse_condition("count(spaces[piece_at(s) == empty]) >= 3")
        assert isinstance(ast, BinOp)
        assert ast.op == ">="

    def test_func_call(self):
        ast = parse_condition("piece_at(target)")
        assert isinstance(ast, FuncCall)
        assert ast.name == "piece_at"

    def test_func_call_multi_arg(self):
        ast = parse_condition("space_at(0, 3)")
        assert isinstance(ast, FuncCall)
        assert ast.name == "space_at"
        assert len(ast.args) == 2

    def test_quantified_any(self):
        ast = parse_condition("any d in directions: line_length(target, d, current_player) >= 3")
        assert isinstance(ast, Quantified)
        assert ast.quantifier == "any"
        assert ast.var == "d"

    def test_and_expr(self):
        ast = parse_condition("true and false")
        assert isinstance(ast, BinOp)
        assert ast.op == "and"

    def test_or_expr(self):
        ast = parse_condition("true or false")
        assert isinstance(ast, BinOp)
        assert ast.op == "or"

    def test_not_expr(self):
        from engine.gdl.expr_parser import UnaryOp
        ast = parse_condition("not true")
        assert isinstance(ast, UnaryOp)
        assert ast.op == "not"

    def test_nested_comparison(self):
        ast = parse_condition("count(spaces[piece_at(s) == empty]) == 0")
        assert isinstance(ast, BinOp)
        assert ast.op == "=="

    def test_all_quantifier(self):
        ast = parse_condition("all c in range(0, 6): piece_at(space_at(0, c)) != empty")
        assert isinstance(ast, Quantified)
        assert ast.quantifier == "all"


class TestParseEffects:
    def test_place(self):
        ast = parse_effect("place mark(current_player) at target")
        assert isinstance(ast, PlaceEffect)
        assert ast.piece_name == "mark"

    def test_set_simple(self):
        ast = parse_effect("set _target = space_at(lowest_empty_row(column), column)")
        assert isinstance(ast, SetEffect)
        assert ast.target == "_target"

    def test_set_with_parens(self):
        ast = parse_effect("set last_pit_is_store = (last_pit_index == current_player_store_index)")
        assert isinstance(ast, SetEffect)
        assert ast.target == "last_pit_is_store"

    def test_if_effect(self):
        ast = parse_effect("if last_pit_is_store == false: set x = 1")
        assert isinstance(ast, IfEffect)

    def test_for_effect(self):
        ast = parse_effect("for d in directions[flanks(target, d, current_player)]: flip_line(target, d, current_player)")
        assert isinstance(ast, ForEffect)
        assert ast.var == "d"


# --- Evaluator tests ---

class TestEvaluateBasics:
    def test_literal(self):
        ctx = make_ctx()
        assert evaluate(Literal(42), ctx) == 42
        assert evaluate(Literal(True), ctx) is True
        assert evaluate(Literal(None), ctx) is None

    def test_current_player(self):
        ctx = make_ctx()
        assert evaluate(Identifier("current_player"), ctx) == "player1"

    def test_opponent(self):
        ctx = make_ctx()
        assert evaluate(Identifier("opponent"), ctx) == "player2"

    def test_bindings(self):
        ctx = make_ctx()
        ctx.bindings["target"] = GridSpace(1, 1)
        assert evaluate(Identifier("target"), ctx) == GridSpace(1, 1)

    def test_binop_and(self):
        ctx = make_ctx()
        ast = BinOp("and", Literal(True), Literal(False))
        assert evaluate(ast, ctx) is False

    def test_binop_or(self):
        ctx = make_ctx()
        ast = BinOp("or", Literal(False), Literal(True))
        assert evaluate(ast, ctx) is True

    def test_binop_eq(self):
        ctx = make_ctx()
        ast = BinOp("==", Literal(3), Literal(3))
        assert evaluate(ast, ctx) is True

    def test_binop_neq(self):
        ctx = make_ctx()
        ast = BinOp("!=", Literal(3), Literal(4))
        assert evaluate(ast, ctx) is True


class TestEvaluateFunctions:
    def test_piece_at_empty(self):
        ctx = make_ctx()
        ast = FuncCall("piece_at", [Literal(GridSpace(0, 0))])
        assert evaluate(ast, ctx) is None

    def test_piece_at_occupied(self):
        ctx = make_ctx()
        ctx.state.set_piece(GridSpace(0, 0), Piece("mark", "player1"))
        ast = FuncCall("piece_at", [Literal(GridSpace(0, 0))])
        result = evaluate(ast, ctx)
        assert isinstance(result, Piece)
        assert result.owner == "player1"

    def test_space_at(self):
        ctx = make_ctx()
        ast = FuncCall("space_at", [Literal(1), Literal(2)])
        result = evaluate(ast, ctx)
        assert result == GridSpace(1, 2)

    def test_count_list(self):
        ctx = make_ctx()
        ast = FuncCall("count", [Literal([1, 2, 3])])
        assert evaluate(ast, ctx) == 3

    def test_lowest_empty_row_empty_board(self):
        ctx = make_ctx(6, 7)
        assert _lowest_empty_row(ctx.state, 3) == 5  # bottom row

    def test_lowest_empty_row_partially_filled(self):
        ctx = make_ctx(6, 7)
        ctx.state.set_piece(GridSpace(5, 3), Piece("disc", "player1"))
        assert _lowest_empty_row(ctx.state, 3) == 4

    def test_lowest_empty_row_full_column(self):
        ctx = make_ctx(6, 7)
        for r in range(6):
            ctx.state.set_piece(GridSpace(r, 3), Piece("disc", "player1"))
        assert _lowest_empty_row(ctx.state, 3) is None


class TestLineLength:
    def test_single_piece(self):
        ctx = make_ctx()
        ctx.state.set_piece(GridSpace(1, 1), Piece("mark", "player1"))
        # Horizontal direction (0, 1)
        assert _line_length(ctx.state, GridSpace(1, 1), (0, 1), "player1") == 1

    def test_horizontal_line_of_3(self):
        ctx = make_ctx()
        for c in range(3):
            ctx.state.set_piece(GridSpace(1, c), Piece("mark", "player1"))
        assert _line_length(ctx.state, GridSpace(1, 1), (0, 1), "player1") == 3

    def test_vertical_line_of_3(self):
        ctx = make_ctx()
        for r in range(3):
            ctx.state.set_piece(GridSpace(r, 1), Piece("mark", "player1"))
        assert _line_length(ctx.state, GridSpace(1, 1), (1, 0), "player1") == 3

    def test_diagonal_line(self):
        ctx = make_ctx()
        for i in range(3):
            ctx.state.set_piece(GridSpace(i, i), Piece("mark", "player1"))
        assert _line_length(ctx.state, GridSpace(1, 1), (1, 1), "player1") == 3

    def test_broken_line(self):
        ctx = make_ctx()
        ctx.state.set_piece(GridSpace(1, 0), Piece("mark", "player1"))
        ctx.state.set_piece(GridSpace(1, 2), Piece("mark", "player1"))
        # Gap at (1,1) — checking from (1,0), direction (0,1)
        assert _line_length(ctx.state, GridSpace(1, 0), (0, 1), "player1") == 1

    def test_wrong_player(self):
        ctx = make_ctx()
        ctx.state.set_piece(GridSpace(1, 1), Piece("mark", "player2"))
        assert _line_length(ctx.state, GridSpace(1, 1), (0, 1), "player1") == 0


class TestFlanks:
    def test_simple_flank(self):
        """X O _ → placing at _ should flank in direction W if X is player1."""
        ctx = make_ctx(1, 5)
        ctx.state.set_piece(GridSpace(0, 0), Piece("disc", "player1"))
        ctx.state.set_piece(GridSpace(0, 1), Piece("disc", "player2"))
        # Checking if placing at (0,2) flanks going west
        assert _flanks(ctx.state, GridSpace(0, 2), (0, -1), "player1") is True

    def test_no_flank_empty(self):
        """X _ _ → no flank because gap."""
        ctx = make_ctx(1, 5)
        ctx.state.set_piece(GridSpace(0, 0), Piece("disc", "player1"))
        assert _flanks(ctx.state, GridSpace(0, 2), (0, -1), "player1") is False

    def test_no_flank_same_color(self):
        """X X _ → no opponent pieces to flank."""
        ctx = make_ctx(1, 5)
        ctx.state.set_piece(GridSpace(0, 0), Piece("disc", "player1"))
        ctx.state.set_piece(GridSpace(0, 1), Piece("disc", "player1"))
        assert _flanks(ctx.state, GridSpace(0, 2), (0, -1), "player1") is False

    def test_multiple_opponent_pieces(self):
        """X O O _ → flanks with 2 opponent pieces."""
        ctx = make_ctx(1, 5)
        ctx.state.set_piece(GridSpace(0, 0), Piece("disc", "player1"))
        ctx.state.set_piece(GridSpace(0, 1), Piece("disc", "player2"))
        ctx.state.set_piece(GridSpace(0, 2), Piece("disc", "player2"))
        assert _flanks(ctx.state, GridSpace(0, 3), (0, -1), "player1") is True


class TestQuantifiers:
    def test_any_with_directions(self):
        """Test 'any d in directions: ...' pattern from tic-tac-toe."""
        ctx = make_ctx()
        # Place a winning line: row 0
        for c in range(3):
            ctx.state.set_piece(GridSpace(0, c), Piece("mark", "player1"))

        # Parse and evaluate the tic-tac-toe win condition
        ast = parse_condition("any d in directions: line_length(last_placed, d, current_player) >= 3")
        ctx.state.last_placed = GridSpace(0, 1)  # middle of the line
        ctx.bindings["last_placed"] = GridSpace(0, 1)
        result = evaluate(ast, ctx)
        assert result is True

    def test_any_no_win(self):
        ctx = make_ctx()
        ctx.state.set_piece(GridSpace(0, 0), Piece("mark", "player1"))
        ctx.state.set_piece(GridSpace(1, 1), Piece("mark", "player2"))

        ast = parse_condition("any d in directions: line_length(last_placed, d, current_player) >= 3")
        ctx.bindings["last_placed"] = GridSpace(0, 0)
        result = evaluate(ast, ctx)
        assert result is False

    def test_count_empty_spaces(self):
        ctx = make_ctx()
        # All 9 spaces empty
        ast = parse_condition("count(spaces[piece_at(s) == empty])")
        # This is a function call wrapping a selector — need to handle count differently
        # Actually count(selector) is a function call
        # Let's test the selector directly
        sel = SelectorExpr("spaces", filter=BinOp("==", FuncCall("piece_at", [Identifier("s")]), Literal(None)))
        items = evaluate(sel, ctx)
        assert len(items) == 9


class TestEffectExecution:
    def test_place_effect(self):
        ctx = make_ctx()
        ctx.bindings["target"] = GridSpace(1, 1)
        ast = parse_effect("place mark(current_player) at target")
        execute_effect(ast, ctx)
        piece = ctx.state.get_piece(GridSpace(1, 1))
        assert piece is not None
        assert piece.name == "mark"
        assert piece.owner == "player1"

    def test_set_effect_state_var(self):
        ctx = make_ctx()
        ctx.state.state_vars["score"] = 0
        ast = parse_effect("set score = 10")
        execute_effect(ast, ctx)
        assert ctx.state.state_vars["score"] == 10

    def test_set_effect_local_var(self):
        ctx = make_ctx()
        ast = parse_effect("set _target = space_at(2, 2)")
        execute_effect(ast, ctx)
        assert ctx.bindings["_target"] == GridSpace(2, 2)

    def test_if_effect_true(self):
        ctx = make_ctx()
        ctx.state.state_vars["x"] = 0
        ctx.bindings["cond"] = True
        ast = parse_effect("if cond == true: set x = 42")
        execute_effect(ast, ctx)
        assert ctx.state.state_vars["x"] == 42

    def test_if_effect_false(self):
        ctx = make_ctx()
        ctx.state.state_vars["x"] = 0
        ctx.bindings["cond"] = False
        ast = parse_effect("if cond == true: set x = 42")
        execute_effect(ast, ctx)
        assert ctx.state.state_vars["x"] == 0
