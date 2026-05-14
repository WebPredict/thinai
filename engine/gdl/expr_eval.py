"""Expression evaluator for ThinAI GDL.

Evaluates parsed AST nodes against a GameState with variable bindings.
Handles both conditions (return bool/value) and effects (modify state).
"""

from __future__ import annotations
from typing import Any, Optional

from engine.gdl.expr_parser import (
    Literal, Identifier, PropertyAccess, FuncCall, BinOp, UnaryOp,
    Quantified, SelectorExpr,
    PlaceEffect, SetEffect, RemoveEffect, MoveEffect, IfEffect, ForEffect,
    EffectFuncCall,
)
from engine.gdl.state import GameState, Piece
from engine.gdl.board import GridBoard, GridSpace, TrackBoard, TrackSpace


class EvalContext:
    """Context for evaluating expressions."""

    def __init__(self, state: GameState, bindings: Optional[dict] = None):
        self.state = state
        self.bindings = dict(bindings or {})

    def child(self, extra_bindings: dict) -> "EvalContext":
        """Create a child context with additional bindings."""
        new_bindings = {**self.bindings, **extra_bindings}
        return EvalContext(self.state, new_bindings)

    def resolve(self, name: str) -> Any:
        """Resolve a name to a value."""
        # Check local bindings first
        if name in self.bindings:
            return self.bindings[name]
        # Check state variables
        if name in self.state.state_vars:
            return self.state.state_vars[name]
        # Special identifiers
        if name == "current_player":
            return self.state.current_player
        if name == "opponent":
            return self.state.opponent()
        if name == "next_player":
            return self.state.next_player_alternating()
        if name == "same_player":
            return self.state.current_player
        if name == "last_placed":
            return self.state.last_placed
        if name == "empty":
            return None
        # Player identifiers
        if name in ("player1", "player2", "player3", "player4"):
            return name
        # Effect-local variables (prefixed with _) may not be set yet
        # (e.g., checking terminal on initial state). Return None gracefully.
        if name.startswith("_"):
            return None
        raise NameError(f"Undefined name: {name}")


def evaluate(node, ctx: EvalContext) -> Any:
    """Evaluate an AST node and return the result."""
    if isinstance(node, Literal):
        return node.value

    if isinstance(node, Identifier):
        return ctx.resolve(node.name)

    if isinstance(node, PropertyAccess):
        obj = evaluate(node.obj, ctx)
        if isinstance(obj, Piece):
            if node.prop == "owner":
                return obj.owner
            if node.prop == "name":
                return obj.name
        if isinstance(obj, GridSpace):
            if node.prop == "row":
                return obj.row
            if node.prop == "col":
                return obj.col
        if isinstance(obj, TrackSpace):
            if node.prop == "index":
                return obj.index
        raise AttributeError(f"Cannot access .{node.prop} on {type(obj)}")

    if isinstance(node, BinOp):
        return _eval_binop(node, ctx)

    if isinstance(node, UnaryOp):
        if node.op == "not":
            return not evaluate(node.operand, ctx)

    if isinstance(node, FuncCall):
        return _eval_func_call(node, ctx)

    if isinstance(node, Quantified):
        return _eval_quantified(node, ctx)

    if isinstance(node, SelectorExpr):
        return _eval_selector(node, ctx)

    raise TypeError(f"Cannot evaluate node type: {type(node)}")


def _eval_binop(node: BinOp, ctx: EvalContext) -> Any:
    if node.op == "and":
        return evaluate(node.left, ctx) and evaluate(node.right, ctx)
    if node.op == "or":
        return evaluate(node.left, ctx) or evaluate(node.right, ctx)

    left = evaluate(node.left, ctx)
    right = evaluate(node.right, ctx)

    if node.op == "==":
        return left == right
    if node.op == "!=":
        return left != right
    if node.op == ">=":
        return left >= right
    if node.op == "<=":
        return left <= right
    if node.op == ">":
        return left > right
    if node.op == "<":
        return left < right

    raise ValueError(f"Unknown operator: {node.op}")


def _eval_func_call(node: FuncCall, ctx: EvalContext) -> Any:
    """Evaluate a built-in function call."""
    args = [evaluate(a, ctx) for a in node.args]
    name = node.name

    if name == "piece_at":
        return ctx.state.get_piece(args[0])

    if name == "pieces_at":
        return ctx.state.get_pieces(args[0])

    if name == "pieces_in":
        # pieces_in(region) — get all pieces in spaces matching selector
        selector = args[0]
        if isinstance(selector, list):
            result = []
            for space in selector:
                result.extend(ctx.state.get_pieces(space))
            return result
        return []

    if name == "count":
        val = args[0]
        if isinstance(val, (list, tuple)):
            return len(val)
        if isinstance(val, int):
            return val
        return 0

    if name == "space_at":
        board = ctx.state.board
        if isinstance(board, GridBoard):
            return board.space_at(args[0], args[1])
        if isinstance(board, TrackBoard):
            return board.space_at(args[0])
        return None

    if name == "owner":
        piece = args[0]
        if isinstance(piece, Piece):
            return piece.owner
        return None

    if name == "row":
        space = args[0]
        return space.row if isinstance(space, GridSpace) else None

    if name == "col":
        space = args[0]
        return space.col if isinstance(space, GridSpace) else None

    if name == "index":
        space = args[0]
        return space.index if isinstance(space, TrackSpace) else None

    if name == "line_length":
        return _line_length(ctx.state, args[0], args[1], args[2])

    if name == "lowest_empty_row":
        return _lowest_empty_row(ctx.state, args[0])

    if name == "flanks":
        return _flanks(ctx.state, args[0], args[1], args[2])

    if name == "has_legal_move":
        # This requires engine-level checking — will be injected
        checker = ctx.bindings.get("_has_legal_move_fn")
        if checker:
            return checker(args[0])
        return True  # default to true if not available

    # Chutes and Ladders built-ins
    if name == "chutes_and_ladders_winner":
        gdl = ctx.bindings.get("_gdl")
        return _chutes_and_ladders_winner(ctx.state, gdl)

    # Mancala-specific built-ins
    if name == "mancala_side_empty":
        return _mancala_side_empty(ctx.state)

    if name == "mancala_store_count":
        return _mancala_store_count(ctx.state, args[0])

    raise NameError(f"Unknown function: {name}")


def _eval_quantified(node: Quantified, ctx: EvalContext) -> Any:
    """Evaluate a quantified expression (any/all/no/count)."""
    items = _eval_selector(node.selector, ctx)

    if node.quantifier == "any":
        return any(
            evaluate(node.body, ctx.child({node.var: item}))
            for item in items
        )
    if node.quantifier == "all":
        return all(
            evaluate(node.body, ctx.child({node.var: item}))
            for item in items
        )
    if node.quantifier == "no":
        return not any(
            evaluate(node.body, ctx.child({node.var: item}))
            for item in items
        )
    if node.quantifier == "count":
        return sum(
            1 for item in items
            if evaluate(node.body, ctx.child({node.var: item}))
        )
    raise ValueError(f"Unknown quantifier: {node.quantifier}")


def _eval_selector(node, ctx: EvalContext) -> list:
    """Evaluate a selector expression to produce a list of items."""
    if not isinstance(node, SelectorExpr):
        # Could be a pre-evaluated list or a function call that returns a list
        result = evaluate(node, ctx)
        if isinstance(result, list):
            return result
        return [result]

    board = ctx.state.board

    if node.kind == "spaces":
        items = list(board.spaces)
        if node.filter:
            items = [
                s for s in items
                if evaluate(node.filter, ctx.child({"s": s}))
            ]
        return items

    if node.kind == "directions":
        if isinstance(board, GridBoard):
            items = board.directions()
            if node.filter:
                items = [
                    d for d in items
                    if evaluate(node.filter, ctx.child({"d": d}))
                ]
            return items
        return []

    if node.kind == "range":
        start = evaluate(node.args[0], ctx)
        end = evaluate(node.args[1], ctx)
        return list(range(start, end + 1))

    if node.kind == "region":
        region_name = evaluate(node.args[0], ctx)
        return _resolve_region(ctx.state, region_name, ctx)

    if node.kind == "neighbors":
        space = evaluate(node.args[0], ctx)
        if isinstance(board, GridBoard):
            items = board.neighbors(space)
            if node.filter:
                items = [
                    s for s in items
                    if evaluate(node.filter, ctx.child({"s": s}))
                ]
            return items
        return []

    if node.kind == "pieces":
        items = ctx.state.all_pieces()
        if node.filter:
            items = [
                (s, p) for s, p in items
                if evaluate(node.filter, ctx.child({
                    "s": s, "p": p,
                    # Convenience: bare 'owner' and 'name' resolve to piece properties
                    "owner": p.owner, "name": p.name,
                }))
            ]
        return items

    raise ValueError(f"Unknown selector kind: {node.kind}")


def _resolve_region(state: GameState, region_name: str, ctx: EvalContext) -> list:
    """Resolve a region name to a list of spaces.

    Uses the engine-injected region resolver if available,
    falls back to a static lookup.
    """
    resolver = ctx.bindings.get("_region_resolver")
    if resolver:
        return resolver(region_name)

    regions = ctx.bindings.get("_regions", {})
    if region_name in regions:
        return regions[region_name]
    return []


# --- Built-in game functions ---

def _line_length(state: GameState, space, direction: tuple, player: str) -> int:
    """Count consecutive pieces owned by player through space in a direction.

    Counts in both the positive and negative direction from space,
    including the piece at space itself.
    """
    if not isinstance(state.board, GridBoard):
        return 0

    board = state.board
    dr, dc = direction
    count = 0

    # Check that the space itself has the player's piece
    piece = state.get_piece(space)
    if piece is None or piece.owner != player:
        return 0
    count = 1

    # Count in positive direction
    r, c = space.row + dr, space.col + dc
    while board.in_bounds(r, c):
        p = state.get_piece(GridSpace(r, c))
        if p is None or p.owner != player:
            break
        count += 1
        r += dr
        c += dc

    # Count in negative direction
    r, c = space.row - dr, space.col - dc
    while board.in_bounds(r, c):
        p = state.get_piece(GridSpace(r, c))
        if p is None or p.owner != player:
            break
        count += 1
        r -= dr
        c -= dc

    return count


def _lowest_empty_row(state: GameState, col: int) -> Optional[int]:
    """Find the lowest empty row in a column (for gravity)."""
    if not isinstance(state.board, GridBoard):
        return None
    board = state.board
    for row in range(board.rows - 1, -1, -1):
        if state.is_empty(GridSpace(row, col)):
            return row
    return None


def _flanks(state: GameState, space, direction: tuple, player: str) -> bool:
    """Check if placing at space would flank opponent pieces in direction.

    Returns True if: from space in direction, there is one or more opponent
    pieces followed by one of player's pieces.
    """
    if not isinstance(state.board, GridBoard):
        return False

    board = state.board
    dr, dc = direction
    opponent = state.opponent(player)
    r, c = space.row + dr, space.col + dc
    opponent_count = 0

    while board.in_bounds(r, c):
        p = state.get_piece(GridSpace(r, c))
        if p is None:
            return False
        if p.owner == opponent:
            opponent_count += 1
        elif p.owner == player:
            return opponent_count > 0
        else:
            return False
        r += dr
        c += dc

    return False


# --- Effect execution ---

def execute_effect(node, ctx: EvalContext):
    """Execute an effect AST node, modifying state."""

    if isinstance(node, PlaceEffect):
        owner = evaluate(node.piece_owner, ctx)
        target = evaluate(node.target, ctx)
        piece = Piece(node.piece_name, owner)
        ctx.state.set_piece(target, piece)
        ctx.state.last_placed = target
        return

    if isinstance(node, SetEffect):
        value = evaluate(node.value, ctx)
        # Effect-local variables (starting with _) go to bindings
        if node.target.startswith("_"):
            ctx.bindings[node.target] = value
            ctx.state.effect_bindings[node.target] = value
        else:
            ctx.state.state_vars[node.target] = value
        return

    if isinstance(node, RemoveEffect):
        target = evaluate(node.target, ctx)
        if isinstance(target, (GridSpace, TrackSpace)):
            ctx.state.remove_piece(target)
        return

    if isinstance(node, MoveEffect):
        source = evaluate(node.source, ctx)
        dest = evaluate(node.dest, ctx)
        # Move all pieces from source to dest
        pieces = ctx.state.get_pieces(source)
        ctx.state.remove_piece(source)
        for p in pieces:
            ctx.state.add_piece(dest, p)
        return

    if isinstance(node, IfEffect):
        if evaluate(node.condition, ctx):
            execute_effect(node.then_effect, ctx)
        elif node.else_effect:
            execute_effect(node.else_effect, ctx)
        return

    if isinstance(node, ForEffect):
        items = _eval_selector(node.selector, ctx)
        for item in items:
            child_ctx = ctx.child({node.var: item})
            child_ctx.state = ctx.state  # Share state for mutations
            execute_effect(node.body, child_ctx)
        return

    if isinstance(node, EffectFuncCall):
        _execute_effect_func(node, ctx)
        return

    raise TypeError(f"Cannot execute effect node type: {type(node)}")


def _execute_effect_func(node: EffectFuncCall, ctx: EvalContext):
    """Execute an effect-only built-in function."""
    name = node.name

    if name == "flip_line":
        args = [evaluate(a, ctx) for a in node.args]
        _flip_line(ctx.state, args[0], args[1], args[2])
        return

    if name == "sow":
        args = [evaluate(a, ctx) for a in node.args]
        result = _sow(ctx.state, args[0], args[1], args[2])
        return result

    if name == "capture_with_opposite":
        args = [evaluate(a, ctx) for a in node.args]
        _capture_with_opposite(ctx.state, args[0])
        return

    if name == "mancala_sow_and_resolve":
        args = [evaluate(a, ctx) for a in node.args]
        _mancala_sow_and_resolve(ctx.state, args[0])
        return

    if name == "remove_n":
        args = [evaluate(a, ctx) for a in node.args]
        _remove_n(ctx.state, args[0], args[1])
        return

    if name == "chutes_and_ladders_move":
        args = [evaluate(a, ctx) for a in node.args]
        gdl = ctx.bindings.get("_gdl")
        _chutes_and_ladders_move(ctx.state, args[0], gdl)
        return

    raise NameError(f"Unknown effect function: {name}")


def _flip_line(state: GameState, space, direction: tuple, player: str):
    """Flip opponent pieces along a line from space in direction."""
    if not isinstance(state.board, GridBoard):
        return

    board = state.board
    dr, dc = direction
    opponent = state.opponent(player)
    r, c = space.row + dr, space.col + dc
    to_flip = []

    while board.in_bounds(r, c):
        p = state.get_piece(GridSpace(r, c))
        if p is None:
            break
        if p.owner == opponent:
            to_flip.append(GridSpace(r, c))
        elif p.owner == player:
            # Flip all collected opponent pieces
            for flip_space in to_flip:
                old = state.get_piece(flip_space)
                state.set_piece(flip_space, Piece(old.name, player))
            return
        else:
            break
        r += dr
        c += dc


def _sow(state: GameState, pit, count: int, skip) -> int:
    """Sow stones from a pit, skipping specified spaces. Returns last pit index."""
    # Implementation for mancala-style sowing
    if not isinstance(state.board, TrackBoard):
        return -1

    board = state.board
    # Pick up all stones
    stones = state.get_pieces(pit)
    num_stones = len(stones)
    state.remove_piece(pit)

    # Distribute one per space
    cursor = pit.index
    last_idx = cursor
    for _ in range(num_stones):
        cursor = (cursor + 1) % board.length
        # Skip logic — skip is a list of spaces (the opponent's store)
        if isinstance(skip, list):
            while TrackSpace(cursor) in [s for s in skip]:
                cursor = (cursor + 1) % board.length
        elif isinstance(skip, TrackSpace):
            if cursor == skip.index:
                cursor = (cursor + 1) % board.length

        state.add_piece(TrackSpace(cursor), Piece("stone", None))
        last_idx = cursor

    return last_idx


def _capture_with_opposite(state: GameState, last_pit_index: int):
    """Capture stones from last pit and opposite pit into player's store."""
    if not isinstance(state.board, TrackBoard):
        return

    # Standard mancala: opposite pit index = 12 - last_pit_index
    opposite_idx = 12 - last_pit_index

    # Determine current player's store
    cp = state.current_player
    store_idx = 6 if cp == "player1" else 13

    # Move pieces from last pit and opposite pit to store
    for idx in [last_pit_index, opposite_idx]:
        pieces = state.get_pieces(TrackSpace(idx))
        state.remove_piece(TrackSpace(idx))
        for p in pieces:
            state.add_piece(TrackSpace(store_idx), p)


def _mancala_sow_and_resolve(state: GameState, pit):
    """Compound Mancala operation: sow from pit, then handle extra turn and capture.

    1. Pick up all stones from the chosen pit
    2. Distribute one per space counter-clockwise, skipping opponent's store
    3. If last stone lands in own store → set extra turn flag
    4. If last stone lands in empty own-side pit → capture that stone + opposite pit's stones
    """
    if not isinstance(state.board, TrackBoard):
        return

    cp = state.current_player
    my_store_idx = 6 if cp == "player1" else 13
    opp_store_idx = 13 if cp == "player1" else 6
    my_pit_range = range(0, 6) if cp == "player1" else range(7, 13)

    # Pick up stones
    stones = state.get_pieces(pit)
    num_stones = len(stones)
    state.remove_piece(pit)

    # Sow counter-clockwise, skipping opponent store
    cursor = pit.index
    for _ in range(num_stones):
        cursor = (cursor + 1) % 14
        if cursor == opp_store_idx:
            cursor = (cursor + 1) % 14
        state.add_piece(TrackSpace(cursor), Piece("stone", None))

    last_idx = cursor

    # Set state vars for turn rule
    state.state_vars["last_pit_index"] = last_idx
    state.state_vars["last_pit_is_store"] = (last_idx == my_store_idx)

    # Capture: if last stone landed in empty own-side pit (now has exactly 1 stone)
    # and opposite pit has stones
    if last_idx != my_store_idx and last_idx in my_pit_range:
        if state.count_pieces_at(TrackSpace(last_idx)) == 1:
            opposite_idx = 12 - last_idx
            if state.count_pieces_at(TrackSpace(opposite_idx)) > 0:
                _capture_with_opposite(state, last_idx)


def _mancala_side_empty(state: GameState) -> bool:
    """Check if either player's pits are all empty (end condition)."""
    p1_empty = all(state.count_pieces_at(TrackSpace(i)) == 0 for i in range(0, 6))
    p2_empty = all(state.count_pieces_at(TrackSpace(i)) == 0 for i in range(7, 13))
    if p1_empty or p2_empty:
        # Collect remaining stones into respective stores
        _mancala_collect_remaining(state)
        return True
    return False


def _mancala_collect_remaining(state: GameState):
    """At game end, each player collects remaining stones on their side into their store."""
    for pit_idx in range(0, 6):
        pieces = state.get_pieces(TrackSpace(pit_idx))
        state.remove_piece(TrackSpace(pit_idx))
        for p in pieces:
            state.add_piece(TrackSpace(6), p)
    for pit_idx in range(7, 13):
        pieces = state.get_pieces(TrackSpace(pit_idx))
        state.remove_piece(TrackSpace(pit_idx))
        for p in pieces:
            state.add_piece(TrackSpace(13), p)


def _mancala_store_count(state: GameState, player: str) -> int:
    """Count stones in a player's store."""
    store_idx = 6 if player == "player1" else 13
    return state.count_pieces_at(TrackSpace(store_idx))


def _remove_n(state: GameState, space, count: int):
    """Remove exactly N pieces from a space."""
    pieces = state.get_pieces(space)
    for _ in range(min(count, len(pieces))):
        state.remove_piece(space, pieces[-1])
        pieces = state.get_pieces(space)


# --- Chutes and Ladders built-ins ---

def _find_player_token(state: GameState, player: str):
    """Find the space where a player's token is located."""
    for space, piece in state.all_pieces():
        if piece.name == "token" and piece.owner == player:
            return space
    return None


def _chutes_and_ladders_move(state: GameState, roll: int, gdl: dict = None):
    """Move current player's token forward by roll, then resolve chutes/ladders."""
    player = state.current_player
    current_space = _find_player_token(state, player)
    if current_space is None:
        return

    current_idx = current_space.index
    new_idx = current_idx + roll

    # Get board size and chutes/ladders map from GDL
    cl_spec = gdl.get("chutes_and_ladders", {}) if gdl else {}
    board_size = cl_spec.get("board_size", 25)

    # Cap at board size (need exact landing or overshoot stays)
    if new_idx > board_size:
        new_idx = board_size

    # Remove token from current position
    token = Piece("token", player)
    state.remove_piece(current_space, token)

    # Resolve chutes and ladders
    ladders = cl_spec.get("ladders", {})
    chutes = cl_spec.get("chutes", {})
    new_idx_str = str(new_idx)
    if new_idx_str in ladders:
        new_idx = ladders[new_idx_str]
    elif new_idx_str in chutes:
        new_idx = chutes[new_idx_str]

    # Place token at new position
    state.set_piece(TrackSpace(new_idx), token)


def _chutes_and_ladders_winner(state: GameState, gdl: dict = None) -> bool:
    """Check if the current player has reached the goal."""
    cl_spec = gdl.get("chutes_and_ladders", {}) if gdl else {}
    board_size = cl_spec.get("board_size", 25)
    player = state.current_player
    token_space = _find_player_token(state, player)
    if token_space is None:
        return False
    return token_space.index >= board_size
