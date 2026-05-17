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
from engine.gdl.cards import CardZone


# Sentinel for safe zone lookups
class _EmptyZone:
    is_empty = True
    size = 0
    cards = []

_empty_zone = _EmptyZone()


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

    # Uno built-ins
    if name == "uno_must_draw":
        return _uno_must_draw(ctx.state)
    if name == "uno_opponent_skipped":
        action = ctx.state.state_vars.get("last_action", "")
        return action in ("skip", "reverse", "draw2", "wild_draw4")

    # Gin Rummy built-ins
    if name == "gin_rummy_can_draw_discard":
        return ctx.state.state_vars.get("phase") == "draw" and \
            ctx.state.card_zones and not ctx.state.card_zones.get("discard", _empty_zone).is_empty
    if name == "gin_rummy_can_draw_deck":
        return ctx.state.state_vars.get("phase") == "draw" and \
            ctx.state.card_zones and not ctx.state.card_zones.get("deck", _empty_zone).is_empty
    if name == "gin_rummy_can_discard":
        return ctx.state.state_vars.get("phase") == "discard"
    if name == "gin_rummy_can_knock":
        if ctx.state.state_vars.get("phase") != "discard":
            return False
        suffix = "p1" if ctx.state.current_player == "player1" else "p2"
        hand = ctx.state.card_zones.get(f"hand_{suffix}")
        if not hand:
            return False
        return _gin_rummy_deadwood(hand.cards) <= 10
    if name == "gin_rummy_turn_done":
        return ctx.state.state_vars.get("phase") == "draw"
    if name == "gin_rummy_round_over":
        return ctx.state.state_vars.get("round_over", False)
    if name == "gin_rummy_score":
        player = ctx.bindings.get("current_player", ctx.state.current_player)
        suffix = "p1" if player == "player1" else "p2"
        hand = ctx.state.card_zones.get(f"hand_{suffix}")
        if not hand:
            return 0
        # Lower deadwood is better — return negative deadwood
        return -_gin_rummy_deadwood(hand.cards)

    # Poker built-ins
    if name == "poker_can_discard":
        phase = ctx.state.state_vars.get("phase", "")
        suffix = "p1" if ctx.state.current_player == "player1" else "p2"
        return phase == f"discard_{suffix}" and ctx.state.state_vars.get(f"{suffix}_discards", 0) < 3
    if name == "poker_can_stand":
        phase = ctx.state.state_vars.get("phase", "")
        suffix = "p1" if ctx.state.current_player == "player1" else "p2"
        return phase == f"discard_{suffix}"
    if name == "poker_turn_done":
        phase = ctx.state.state_vars.get("phase", "")
        return phase == "discard_p2" and ctx.state.current_player == "player1"
    if name == "poker_round_over":
        return ctx.state.state_vars.get("round_over", False)
    if name == "poker_hand_score":
        player = ctx.bindings.get("current_player", ctx.state.current_player)
        suffix = "p1" if player == "player1" else "p2"
        reveal = ctx.state.card_zones.get(f"reveal_{suffix}")
        if reveal and reveal.cards:
            return _poker_hand_score(reveal.cards)
        hand = ctx.state.card_zones.get(f"hand_{suffix}")
        if hand and hand.cards:
            return _poker_hand_score(hand.cards)
        return 0

    # Blackjack built-ins
    if name == "blackjack_can_hit":
        phase = ctx.state.state_vars.get("phase", "player")
        if phase == "player":
            return not ctx.state.state_vars.get("p1_standing") and not ctx.state.state_vars.get("p1_bust")
        return False

    if name == "blackjack_can_stand":
        phase = ctx.state.state_vars.get("phase", "player")
        return phase == "player" and not ctx.state.state_vars.get("p1_standing") and not ctx.state.state_vars.get("p1_bust")

    if name == "blackjack_round_over":
        return _blackjack_round_over(ctx.state)

    if name == "blackjack_score":
        player = args[0]
        return _blackjack_score(ctx.state, player)

    # Crazy Eights built-ins
    if name == "crazy_eights_must_draw":
        return _crazy_eights_must_draw(ctx.state)

    if name == "crazy_eights_hand_empty":
        player = args[0]
        suffix = "p1" if player == "player1" else "p2"
        hand = ctx.state.get_zone(f"hand_{suffix}")
        return hand is not None and hand.is_empty

    if name == "crazy_eights_deck_empty":
        deck = ctx.state.get_zone("deck")
        return deck is not None and deck.is_empty

    if name == "crazy_eights_score":
        player = args[0]
        suffix = "p1" if player == "player1" else "p2"
        hand = ctx.state.get_zone(f"hand_{suffix}")
        # Fewer cards = higher score (invert)
        return 100 - (hand.size if hand else 0)

    # Checkers built-ins
    if name == "checkers_opponent_has_no_moves":
        from engine.gdl.checkers import opponent_has_no_moves
        return opponent_has_no_moves(ctx.state)

    if name == "checkers_stalemate":
        return ctx.state.state_vars.get("moves_since_capture", 0) >= 40

    if name == "checkers_piece_count":
        player = args[0]
        return sum(1 for _, p in ctx.state.all_pieces() if p.owner == player)

    # Card game built-ins
    if name == "zone_size":
        zone_name = args[0]
        zone = ctx.state.get_zone(zone_name)
        return zone.size if zone else 0

    if name == "zone_empty":
        zone_name = args[0]
        zone = ctx.state.get_zone(zone_name)
        return zone.is_empty if zone else True

    if name == "top_card_rank_value":
        zone_name = args[0]
        zone = ctx.state.get_zone(zone_name)
        if zone and not zone.is_empty:
            return zone.peek().value
        return 0

    if name == "compare_top_cards":
        zone_a = args[0]
        zone_b = args[1]
        za = ctx.state.get_zone(zone_a)
        zb = ctx.state.get_zone(zone_b)
        if za and zb and not za.is_empty and not zb.is_empty:
            from engine.gdl.cards import compare_cards
            return compare_cards(za.peek(), zb.peek())
        return 0

    # Go Fish built-ins
    if name == "has_rank_in_hand":
        player = args[0]
        rank = args[1]
        return _has_rank_in_hand(ctx.state, player, rank)

    if name == "hand_has_any_cards":
        player = args[0]
        return _hand_has_any_cards(ctx.state, player)

    if name == "count_sets":
        player = args[0]
        suffix = "p1" if player == "player1" else "p2"
        zone = ctx.state.get_zone(f"sets_{suffix}")
        return (zone.size // 4) if zone else 0

    if name == "all_sets_done":
        if not ctx.state.card_zones:
            return False
        sets_p1 = ctx.state.get_zone("sets_p1")
        sets_p2 = ctx.state.get_zone("sets_p2")
        total = (sets_p1.size if sets_p1 else 0) + (sets_p2.size if sets_p2 else 0)
        return total >= 52  # all 13 sets of 4

    if name == "go_fish_game_over":
        return _go_fish_game_over(ctx.state)

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

    if name == "war_battle":
        _war_battle(ctx.state)
        return

    if name == "card_move":
        args = [evaluate(a, ctx) for a in node.args]
        _card_move(ctx.state, args[0], args[1], int(args[2]) if len(args) > 2 else 1)
        return

    if name == "go_fish_ask":
        args = [evaluate(a, ctx) for a in node.args]
        _go_fish_ask(ctx.state, args[0])
        return

    if name == "checkers_execute":
        args = [evaluate(a, ctx) for a in node.args]
        _checkers_execute(ctx.state, int(args[0]))
        return

    # Gin Rummy effects
    if name == "gin_rummy_draw_discard":
        _gin_rummy_draw_discard(ctx.state)
        return
    if name == "gin_rummy_draw_deck":
        _gin_rummy_draw_deck(ctx.state)
        return
    if name == "gin_rummy_discard":
        args = [evaluate(a, ctx) for a in node.args]
        _gin_rummy_discard(ctx.state, int(args[0]))
        return
    if name == "gin_rummy_knock":
        args = [evaluate(a, ctx) for a in node.args]
        _gin_rummy_knock(ctx.state, int(args[0]))
        return

    # Poker effects
    if name == "poker_discard":
        args = [evaluate(a, ctx) for a in node.args]
        _poker_discard(ctx.state, int(args[0]))
        return
    if name == "poker_stand_pat":
        _poker_stand_pat(ctx.state)
        return

    if name == "uno_play":
        args = [evaluate(a, ctx) for a in node.args]
        _uno_play(ctx.state, int(args[0]))
        return

    if name == "uno_draw":
        _uno_draw(ctx.state)
        return

    if name == "blackjack_hit":
        _blackjack_hit(ctx.state)
        return

    if name == "blackjack_stand":
        _blackjack_stand(ctx.state)
        return

    if name == "crazy_eights_play":
        args = [evaluate(a, ctx) for a in node.args]
        _crazy_eights_play(ctx.state, int(args[0]))
        return

    if name == "crazy_eights_draw":
        _crazy_eights_draw(ctx.state)
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


# --- Card game built-ins ---

def _war_battle(state: GameState):
    """Execute one round of War: both players flip top card, higher wins both.

    If tie, each places 3 face-down and flips a 4th (recursive war).
    Winner collects all cards to bottom of their hand.
    """
    if not state.card_zones:
        return

    import random
    from engine.gdl.cards import compare_cards

    hand_p1 = state.card_zones.get("hand_p1")
    hand_p2 = state.card_zones.get("hand_p2")
    table = state.card_zones.get("table")

    if not hand_p1 or not hand_p2 or not table:
        return

    if hand_p1.is_empty or hand_p2.is_empty:
        return

    # Both flip top card
    card_p1 = hand_p1.draw()
    card_p2 = hand_p2.draw()
    table.add(card_p1)
    table.add(card_p2)

    # Store flipped cards in state vars for UI display
    state.state_vars["last_p1_card"] = f"{card_p1.rank}{card_p1.symbol}"
    state.state_vars["last_p2_card"] = f"{card_p2.rank}{card_p2.symbol}"

    cmp = compare_cards(card_p1, card_p2)

    if cmp > 0:
        _collect_war_table(state, "p1")
        state.state_vars["round_winner"] = "player1"
    elif cmp < 0:
        _collect_war_table(state, "p2")
        state.state_vars["round_winner"] = "player2"
    else:
        # War! Place 3 face-down each, flip 4th
        state.state_vars["round_winner"] = "war"
        _resolve_war(state)


def _resolve_war(state: GameState):
    """Resolve a war tie-break."""
    import random
    from engine.gdl.cards import compare_cards

    hand_p1 = state.card_zones["hand_p1"]
    hand_p2 = state.card_zones["hand_p2"]
    table = state.card_zones["table"]

    # Place 3 face-down each
    for _ in range(3):
        if not hand_p1.is_empty:
            table.add(hand_p1.draw())
        if not hand_p2.is_empty:
            table.add(hand_p2.draw())

    if hand_p1.is_empty:
        _collect_war_table(state, "p2")
        state.state_vars["round_winner"] = "player2"
        return
    if hand_p2.is_empty:
        _collect_war_table(state, "p1")
        state.state_vars["round_winner"] = "player1"
        return

    # Flip 4th
    card_p1 = hand_p1.draw()
    card_p2 = hand_p2.draw()
    table.add(card_p1)
    table.add(card_p2)

    state.state_vars["last_p1_card"] = f"{card_p1.rank}{card_p1.symbol}"
    state.state_vars["last_p2_card"] = f"{card_p2.rank}{card_p2.symbol}"

    cmp = compare_cards(card_p1, card_p2)
    if cmp > 0:
        _collect_war_table(state, "p1")
        state.state_vars["round_winner"] = "player1"
    elif cmp < 0:
        _collect_war_table(state, "p2")
        state.state_vars["round_winner"] = "player2"
    else:
        _resolve_war(state)  # Another tie


def _collect_war_table(state: GameState, winner_suffix: str):
    """Move all table cards to winner's hand (shuffled to bottom)."""
    import random
    table = state.card_zones["table"]
    hand = state.card_zones[f"hand_{winner_suffix}"]
    cards = list(table.cards)
    random.shuffle(cards)
    table.cards.clear()
    for card in cards:
        hand.add(card, to_top=False)


def _card_move(state: GameState, from_zone: str, to_zone: str, count: int = 1):
    """Move N cards from one zone to another."""
    if not state.card_zones:
        return
    source = state.card_zones.get(from_zone)
    dest = state.card_zones.get(to_zone)
    if source and dest:
        for _ in range(min(count, source.size)):
            card = source.draw()
            if card:
                dest.add(card)


# --- Go Fish built-ins ---

def _has_rank_in_hand(state: GameState, player: str, rank: str) -> bool:
    """Check if player has any cards of the given rank in their hand."""
    if not state.card_zones:
        return False
    suffix = "p1" if player == "player1" else "p2"
    hand = state.card_zones.get(f"hand_{suffix}")
    if not hand:
        return False
    return any(c.rank == rank for c in hand.cards)


def _hand_has_any_cards(state: GameState, player: str) -> bool:
    """Check if player has any cards in hand."""
    if not state.card_zones:
        return False
    suffix = "p1" if player == "player1" else "p2"
    hand = state.card_zones.get(f"hand_{suffix}")
    return hand is not None and not hand.is_empty


def _go_fish_ask(state: GameState, rank: str):
    """Execute a Go Fish ask: ask opponent for a rank.

    If opponent has cards of that rank, they give ALL to current player.
    If not, current player draws from the pond.
    After receiving cards, check for completed sets of 4.
    """
    if not state.card_zones:
        return

    cp = state.current_player
    opp = "player2" if cp == "player1" else "player1"
    cp_suffix = "p1" if cp == "player1" else "p2"
    opp_suffix = "p2" if cp == "player1" else "p1"

    my_hand = state.card_zones.get(f"hand_{cp_suffix}")
    opp_hand = state.card_zones.get(f"hand_{opp_suffix}")
    pond = state.card_zones.get("pond")

    if not my_hand or not opp_hand:
        return

    # Store what was asked for UI
    state.state_vars["last_ask_rank"] = rank
    state.state_vars["last_ask_player"] = cp

    # Check if opponent has the rank
    matching = [c for c in opp_hand.cards if c.rank == rank]

    if matching:
        # Opponent gives all matching cards
        for card in matching:
            opp_hand.remove(card)
            my_hand.add(card)
        state.state_vars["last_result"] = f"got {len(matching)} {rank}(s)"
        state.state_vars["extra_turn"] = True
    else:
        # Go Fish — draw from pond
        state.state_vars["extra_turn"] = False
        if pond and not pond.is_empty:
            drawn = pond.draw()
            if drawn:
                my_hand.add(drawn)
                state.state_vars["last_result"] = f"Go Fish! Drew a card"
                # If drawn card matches asked rank, get another turn
                if drawn.rank == rank:
                    state.state_vars["extra_turn"] = True
                    state.state_vars["last_result"] = f"Go Fish! Drew the {rank}!"
            else:
                state.state_vars["last_result"] = "Go Fish! Pond is empty"
        else:
            state.state_vars["last_result"] = "Go Fish! Pond is empty"

    # Check for completed sets of 4
    _check_go_fish_sets(state, cp_suffix)

    # If opponent's hand is empty and pond has cards, they draw
    if opp_hand.is_empty and pond and not pond.is_empty:
        drawn = pond.draw()
        if drawn:
            opp_hand.add(drawn)


def _go_fish_game_over(state: GameState) -> bool:
    """Go Fish ends when:
    1. All 13 sets are completed, OR
    2. A player has no cards and can't draw (pond empty), OR
    3. Both hands are empty

    Before declaring game over, try to draw from pond for empty-handed player.
    """
    if not state.card_zones:
        return False

    sets_p1 = state.get_zone("sets_p1")
    sets_p2 = state.get_zone("sets_p2")
    hand_p1 = state.get_zone("hand_p1")
    hand_p2 = state.get_zone("hand_p2")
    pond = state.get_zone("pond")

    total_sets = (sets_p1.size if sets_p1 else 0) + (sets_p2.size if sets_p2 else 0)
    if total_sets >= 52:
        return True

    # If a player's hand is empty, try to draw from pond
    if hand_p1 and hand_p1.is_empty and pond and not pond.is_empty:
        card = pond.draw()
        if card:
            hand_p1.add(card)
    if hand_p2 and hand_p2.is_empty and pond and not pond.is_empty:
        card = pond.draw()
        if card:
            hand_p2.add(card)

    # Game over if both hands empty, or one hand empty and pond empty
    p1_empty = hand_p1.is_empty if hand_p1 else True
    p2_empty = hand_p2.is_empty if hand_p2 else True
    pond_empty = pond.is_empty if pond else True

    if p1_empty and p2_empty:
        return True
    if (p1_empty or p2_empty) and pond_empty:
        return True

    return False


def _check_go_fish_sets(state: GameState, player_suffix: str):
    """Check if player has 4 of any rank — if so, move to sets zone."""
    hand = state.card_zones.get(f"hand_{player_suffix}")
    sets_zone = state.card_zones.get(f"sets_{player_suffix}")

    if not hand or not sets_zone:
        return

    from engine.gdl.cards import RANKS
    for rank in RANKS:
        matching = [c for c in hand.cards if c.rank == rank]
        if len(matching) >= 4:
            # Complete set! Move all 4 to sets zone
            for card in matching[:4]:
                hand.remove(card)
                sets_zone.add(card)
            state.state_vars[f"last_set_{player_suffix}"] = rank


# --- Checkers built-ins ---

def _checkers_execute(state: GameState, move_id: int):
    """Execute a checkers move by ID."""
    from engine.gdl.checkers import get_all_moves, execute_move
    moves = get_all_moves(state)
    if move_id < len(moves):
        execute_move(state, moves[move_id])


# --- Crazy Eights built-ins ---

def _crazy_eights_must_draw(state: GameState) -> bool:
    """Check if current player has no playable cards (must draw)."""
    if not state.card_zones:
        return False
    suffix = "p1" if state.current_player == "player1" else "p2"
    hand = state.card_zones.get(f"hand_{suffix}")
    discard = state.card_zones.get("discard")
    deck = state.card_zones.get("deck")

    if not hand or not discard or discard.is_empty:
        return False
    if deck and deck.is_empty:
        return False  # can't draw if deck is empty

    top = discard.peek()
    active_suit = state.state_vars.get("active_suit", "") or top.suit

    # Check if any card in hand is playable
    for card in hand.cards:
        if card.rank == "8" or card.suit == active_suit or card.rank == top.rank:
            return False  # has a playable card

    return True  # must draw


def _crazy_eights_play(state: GameState, card_id: int):
    """Play a card from hand to discard pile."""
    if not state.card_zones:
        return

    suffix = "p1" if state.current_player == "player1" else "p2"
    hand = state.card_zones.get(f"hand_{suffix}")
    discard = state.card_zones.get("discard")

    if not hand or not discard:
        return

    # Find the card by ID
    card = None
    for c in hand.cards:
        if c.id == card_id:
            card = c
            break

    if not card:
        return

    # Move card from hand to discard
    hand.remove(card)
    discard.add(card)

    # Update active suit
    if card.rank == "8":
        # When playing an 8, choose the most common suit in hand
        from collections import Counter
        if hand.cards:
            suits = Counter(c.suit for c in hand.cards)
            state.state_vars["active_suit"] = suits.most_common(1)[0][0]
        else:
            state.state_vars["active_suit"] = card.suit
    else:
        state.state_vars["active_suit"] = ""  # reset — use card's suit

    state.state_vars["last_play"] = f"{card.rank}{card.symbol}"
    state.state_vars["last_action"] = "play"


def _crazy_eights_draw(state: GameState):
    """Draw a card from the deck."""
    if not state.card_zones:
        return

    suffix = "p1" if state.current_player == "player1" else "p2"
    hand = state.card_zones.get(f"hand_{suffix}")
    deck = state.card_zones.get("deck")

    if not hand or not deck or deck.is_empty:
        return

    card = deck.draw()
    if card:
        hand.add(card)
        state.state_vars["last_action"] = "draw"
        state.state_vars["last_play"] = "drew a card"


# --- Blackjack built-ins ---

def _blackjack_hand_value(cards) -> int:
    """Calculate best hand value. Ace = 1 or 11."""
    value = 0
    aces = 0
    for card in cards:
        if card.rank in ('J', 'Q', 'K'):
            value += 10
        elif card.rank == 'A':
            value += 11
            aces += 1
        else:
            value += int(card.rank)
    # Reduce aces from 11 to 1 if busting
    while value > 21 and aces > 0:
        value -= 10
        aces -= 1
    return value


def _blackjack_hit(state: GameState):
    """Player draws a card."""
    if not state.card_zones:
        return
    deck = state.card_zones.get("deck")
    hand = state.card_zones.get("hand_p1")
    if not deck or not hand or deck.is_empty:
        return
    card = deck.draw()
    if card:
        hand.add(card)
        value = _blackjack_hand_value(hand.cards)
        state.state_vars["last_action"] = f"hit ({card.rank}{card.symbol}) — total {value}"
        if value > 21:
            state.state_vars["p1_bust"] = True
            state.state_vars["last_action"] += " BUST!"
            state.state_vars["phase"] = "done"
            # Dealer reveals hole card
            _blackjack_reveal_hole(state)


def _blackjack_stand(state: GameState):
    """Player stands — dealer plays."""
    if not state.card_zones:
        return
    state.state_vars["p1_standing"] = True
    state.state_vars["phase"] = "dealer"
    state.state_vars["last_action"] = "stand"

    # Reveal hole card
    _blackjack_reveal_hole(state)

    # Dealer plays by house rules: hit on 16 or below
    dealer_hand = state.card_zones.get("hand_p2")
    deck = state.card_zones.get("deck")
    if dealer_hand and deck:
        while _blackjack_hand_value(dealer_hand.cards) < 17 and not deck.is_empty:
            card = deck.draw()
            if card:
                dealer_hand.add(card)
        value = _blackjack_hand_value(dealer_hand.cards)
        if value > 21:
            state.state_vars["p2_bust"] = True
    state.state_vars["phase"] = "done"


def _blackjack_reveal_hole(state: GameState):
    """Move hole card to dealer's visible hand."""
    hole = state.card_zones.get("hole_card")
    hand = state.card_zones.get("hand_p2")
    if hole and hand and not hole.is_empty:
        card = hole.draw()
        if card:
            hand.add(card)


def _blackjack_round_over(state: GameState) -> bool:
    """Check if the round is over."""
    return state.state_vars.get("phase") == "done"


def _blackjack_score(state: GameState, player: str) -> int:
    """Score for comparison — higher is better, bust = 0."""
    suffix = "p1" if player == "player1" else "p2"
    hand = state.card_zones.get(f"hand_{suffix}")
    if not hand:
        return 0
    is_bust = state.state_vars.get(f"{suffix}_bust", False)
    if is_bust:
        return 0
    return _blackjack_hand_value(hand.cards)


# --- Uno built-ins ---

def _uno_must_draw(state: GameState) -> bool:
    """Check if current player has no playable cards."""
    if not state.card_zones:
        return False
    suffix = "p1" if state.current_player == "player1" else "p2"
    hand = state.card_zones.get(f"hand_{suffix}")
    discard = state.card_zones.get("discard")
    deck = state.card_zones.get("deck")

    if not hand or not discard or discard.is_empty:
        return False
    if deck and deck.is_empty:
        return False

    top = discard.peek()
    active_color = state.state_vars.get("active_color", "") or top.suit

    for card in hand.cards:
        if card.suit == "wild" or card.suit == active_color or card.rank == top.rank:
            return False
    return True


def _uno_play(state: GameState, card_id: int):
    """Play an Uno card."""
    if not state.card_zones:
        return

    # Clear previous action (turn rule already read it)
    state.state_vars["last_action"] = ""

    suffix = "p1" if state.current_player == "player1" else "p2"
    opp_suffix = "p2" if suffix == "p1" else "p1"
    hand = state.card_zones.get(f"hand_{suffix}")
    opp_hand = state.card_zones.get(f"hand_{opp_suffix}")
    discard = state.card_zones.get("discard")
    deck = state.card_zones.get("deck")

    if not hand or not discard:
        return

    card = None
    for c in hand.cards:
        if c.id == card_id:
            card = c
            break
    if not card:
        return

    hand.remove(card)
    discard.add(card)

    # Handle action cards
    from engine.gdl.cards import UNO_COLOR_SYMBOLS
    color_sym = UNO_COLOR_SYMBOLS.get(card.suit, card.suit)

    if card.rank == "Skip":
        state.state_vars["last_play"] = f"Skip {color_sym}"
        state.state_vars["last_action"] = "skip"

    elif card.rank == "Reverse":
        state.state_vars["last_play"] = f"Reverse {color_sym}"
        state.state_vars["last_action"] = "reverse"  # In 2-player, acts like Skip

    elif card.rank == "Draw2":
        state.state_vars["last_play"] = f"Draw Two {color_sym}"
        state.state_vars["last_action"] = "draw2"
        if opp_hand and deck:
            for _ in range(min(2, deck.size)):
                c = deck.draw()
                if c:
                    opp_hand.add(c)

    elif card.rank == "Wild" or card.rank == "WildDraw4":
        from collections import Counter
        if hand.cards:
            colors = Counter(c.suit for c in hand.cards if c.suit != "wild")
            if colors:
                state.state_vars["active_color"] = colors.most_common(1)[0][0]
            else:
                state.state_vars["active_color"] = "red"
        else:
            state.state_vars["active_color"] = "red"

        if card.rank == "WildDraw4" and opp_hand and deck:
            for _ in range(min(4, deck.size)):
                c = deck.draw()
                if c:
                    opp_hand.add(c)
            state.state_vars["last_play"] = "Wild Draw Four!"
            state.state_vars["last_action"] = "wild_draw4"
        else:
            state.state_vars["last_play"] = f"Wild → {state.state_vars['active_color']}"
            state.state_vars["last_action"] = "wild"

    else:
        state.state_vars["last_play"] = f"{card.rank} {color_sym}"
        state.state_vars["last_action"] = "play"
        state.state_vars["active_color"] = ""  # reset


def _uno_draw(state: GameState):
    """Draw a card in Uno."""
    if not state.card_zones:
        return
    # Clear previous action (turn rule already read it)
    state.state_vars["last_action"] = ""
    suffix = "p1" if state.current_player == "player1" else "p2"
    hand = state.card_zones.get(f"hand_{suffix}")
    deck = state.card_zones.get("deck")
    if hand and deck and not deck.is_empty:
        card = deck.draw()
        if card:
            hand.add(card)
    state.state_vars["last_action"] = "draw"
    state.state_vars["last_play"] = "drew a card"


# --- Gin Rummy built-ins ---

_GIN_RANK_VALUES = {
    "A": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7,
    "8": 8, "9": 9, "10": 10, "J": 10, "Q": 10, "K": 10,
}

_GIN_RANK_ORDER = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]


def _gin_card_value(card) -> int:
    return _GIN_RANK_VALUES.get(card.rank, 0)


def _gin_rank_index(card) -> int:
    return _GIN_RANK_ORDER.index(card.rank) if card.rank in _GIN_RANK_ORDER else -1


def _gin_find_all_melds(cards: list) -> list:
    """Find all possible melds (sets and runs) from a list of cards."""
    melds = []

    # Sets: 3 or 4 cards of the same rank
    from collections import defaultdict
    by_rank = defaultdict(list)
    for c in cards:
        by_rank[c.rank].append(c)
    for rank, group in by_rank.items():
        if len(group) >= 3:
            # All combinations of 3
            from itertools import combinations
            for combo in combinations(group, 3):
                melds.append(list(combo))
            if len(group) >= 4:
                melds.append(list(group))

    # Runs: 3+ sequential cards of the same suit
    by_suit = defaultdict(list)
    for c in cards:
        by_suit[c.suit].append(c)
    for suit, group in by_suit.items():
        sorted_cards = sorted(group, key=lambda c: _gin_rank_index(c))
        # Find all runs of 3+
        for start in range(len(sorted_cards)):
            run = [sorted_cards[start]]
            for j in range(start + 1, len(sorted_cards)):
                if _gin_rank_index(sorted_cards[j]) == _gin_rank_index(run[-1]) + 1:
                    run.append(sorted_cards[j])
                else:
                    break
            if len(run) >= 3:
                # Add all sub-runs of length 3+
                for length in range(3, len(run) + 1):
                    for offset in range(len(run) - length + 1):
                        melds.append(run[offset:offset + length])

    return melds


def _gin_rummy_best_melds(cards: list):
    """Find the optimal set of non-overlapping melds minimizing deadwood."""
    all_melds = _gin_find_all_melds(cards)
    card_ids = {c.id for c in cards}

    best_deadwood = sum(_gin_card_value(c) for c in cards)
    best_combo = []

    def search(idx, used_ids, current_melds):
        nonlocal best_deadwood, best_combo
        # Calculate current deadwood
        remaining = [c for c in cards if c.id not in used_ids]
        dw = sum(_gin_card_value(c) for c in remaining)
        if dw < best_deadwood:
            best_deadwood = dw
            best_combo = list(current_melds)
        if dw == 0:
            return  # Can't do better than Gin

        for i in range(idx, len(all_melds)):
            meld = all_melds[i]
            meld_ids = {c.id for c in meld}
            if not meld_ids & used_ids:  # No overlap
                search(i + 1, used_ids | meld_ids, current_melds + [meld])

    search(0, set(), [])
    return best_combo, best_deadwood


def _gin_rummy_deadwood(cards: list) -> int:
    """Calculate minimum deadwood for a hand."""
    if not cards:
        return 0
    _, deadwood = _gin_rummy_best_melds(cards)
    return deadwood


def _gin_rummy_draw_discard(state: GameState):
    """Draw the top card from the discard pile."""
    if not state.card_zones:
        return
    suffix = "p1" if state.current_player == "player1" else "p2"
    hand = state.card_zones.get(f"hand_{suffix}")
    discard = state.card_zones.get("discard")
    if hand and discard and not discard.is_empty:
        card = discard.draw()
        if card:
            hand.add(card)
    state.state_vars["phase"] = "discard"
    state.state_vars["last_action"] = "draw_discard"


def _gin_rummy_draw_deck(state: GameState):
    """Draw a card from the deck."""
    if not state.card_zones:
        return
    suffix = "p1" if state.current_player == "player1" else "p2"
    hand = state.card_zones.get(f"hand_{suffix}")
    deck = state.card_zones.get("deck")
    if hand and deck and not deck.is_empty:
        card = deck.draw()
        if card:
            hand.add(card)
    state.state_vars["phase"] = "discard"
    state.state_vars["last_action"] = "draw_deck"

    # If deck is down to 2 cards, round is a draw
    if deck and deck.size <= 2:
        state.state_vars["round_over"] = True


def _gin_rummy_discard(state: GameState, card_id: int):
    """Discard a card from hand."""
    if not state.card_zones:
        return
    suffix = "p1" if state.current_player == "player1" else "p2"
    hand = state.card_zones.get(f"hand_{suffix}")
    discard = state.card_zones.get("discard")
    if not hand or not discard:
        return
    card = None
    for c in hand.cards:
        if c.id == card_id:
            card = c
            break
    if not card:
        return
    hand.remove(card)
    discard.add(card)
    state.state_vars["phase"] = "draw"
    state.state_vars["last_action"] = "discard"
    state.state_vars["last_play"] = f"discarded {card.rank} of {card.suit}"


def _gin_rummy_knock(state: GameState, card_id: int):
    """Knock — discard a card and end the round."""
    if not state.card_zones:
        return
    suffix = "p1" if state.current_player == "player1" else "p2"
    hand = state.card_zones.get(f"hand_{suffix}")
    discard = state.card_zones.get("discard")
    if not hand or not discard:
        return
    card = None
    for c in hand.cards:
        if c.id == card_id:
            card = c
            break
    if not card:
        return
    hand.remove(card)
    discard.add(card)
    dw = _gin_rummy_deadwood(hand.cards)
    state.state_vars["phase"] = "draw"
    state.state_vars["round_over"] = True
    state.state_vars["knocked_by"] = state.current_player
    if dw == 0:
        state.state_vars["last_action"] = "gin"
        state.state_vars["last_play"] = "GIN!"
    else:
        state.state_vars["last_action"] = "knock"
        state.state_vars["last_play"] = f"knocked with {dw} deadwood"


# --- Poker built-ins ---

_POKER_RANK_VALUES = {
    "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8,
    "9": 9, "10": 10, "J": 11, "Q": 12, "K": 13, "A": 14,
}

_POKER_HAND_NAMES = {
    8: "Straight Flush", 7: "Four of a Kind", 6: "Full House",
    5: "Flush", 4: "Straight", 3: "Three of a Kind",
    2: "Two Pair", 1: "One Pair", 0: "High Card",
}


def _poker_hand_rank(cards: list) -> tuple:
    """Rank a 5-card poker hand. Returns (tier, *tiebreakers)."""
    if len(cards) < 5:
        return (0, 0)

    values = sorted([_POKER_RANK_VALUES.get(c.rank, 0) for c in cards], reverse=True)
    suits = [c.suit for c in cards]

    is_flush = len(set(suits)) == 1

    # Check straight (including A-2-3-4-5 low straight)
    is_straight = False
    straight_high = 0
    if values == list(range(values[0], values[0] - 5, -1)):
        is_straight = True
        straight_high = values[0]
    elif values == [14, 5, 4, 3, 2]:  # Ace-low straight
        is_straight = True
        straight_high = 5

    # Count rank groups
    from collections import Counter
    counts = Counter(values)
    groups = sorted(counts.items(), key=lambda x: (x[1], x[0]), reverse=True)

    if is_straight and is_flush:
        return (8, straight_high)
    if groups[0][1] == 4:
        return (7, groups[0][0], groups[1][0])
    if groups[0][1] == 3 and groups[1][1] == 2:
        return (6, groups[0][0], groups[1][0])
    if is_flush:
        return (5, *values)
    if is_straight:
        return (4, straight_high)
    if groups[0][1] == 3:
        return (3, groups[0][0], *sorted([g[0] for g in groups[1:]], reverse=True))
    if groups[0][1] == 2 and groups[1][1] == 2:
        pair1, pair2 = sorted([groups[0][0], groups[1][0]], reverse=True)
        kicker = groups[2][0]
        return (2, pair1, pair2, kicker)
    if groups[0][1] == 2:
        pair = groups[0][0]
        kickers = sorted([g[0] for g in groups[1:]], reverse=True)
        return (1, pair, *kickers)
    return (0, *values)


def _poker_hand_score(cards: list) -> int:
    """Convert hand rank tuple to a single comparable integer."""
    rank = _poker_hand_rank(cards)
    score = 0
    for i, v in enumerate(rank):
        score += v * (15 ** (10 - i))
    return score


def _poker_hand_name(cards: list) -> str:
    """Human-readable name for a poker hand."""
    rank = _poker_hand_rank(cards)
    return _POKER_HAND_NAMES.get(rank[0], "Unknown")


def _poker_discard(state: GameState, card_id: int):
    """Discard a card in poker."""
    if not state.card_zones:
        return
    suffix = "p1" if state.current_player == "player1" else "p2"
    hand = state.card_zones.get(f"hand_{suffix}")
    discard = state.card_zones.get("discard")
    if not hand or not discard:
        return
    card = None
    for c in hand.cards:
        if c.id == card_id:
            card = c
            break
    if not card:
        return
    hand.remove(card)
    discard.add(card)
    state.state_vars[f"{suffix}_discards"] = state.state_vars.get(f"{suffix}_discards", 0) + 1
    state.state_vars["last_action"] = "discard"


def _poker_stand_pat(state: GameState):
    """Finalize discard phase — draw replacements and advance."""
    if not state.card_zones:
        return
    suffix = "p1" if state.current_player == "player1" else "p2"
    hand = state.card_zones.get(f"hand_{suffix}")
    deck = state.card_zones.get("deck")
    num_discarded = state.state_vars.get(f"{suffix}_discards", 0)

    # Draw replacements
    if hand and deck:
        for _ in range(min(num_discarded, deck.size)):
            card = deck.draw()
            if card:
                hand.add(card)

    # Advance phase
    phase = state.state_vars.get("phase", "")
    if phase == "discard_p1":
        state.state_vars["phase"] = "discard_p2"
        state.state_vars["last_action"] = "stand"
    elif phase == "discard_p2":
        # Both done — showdown
        _poker_showdown(state)


def _poker_showdown(state: GameState):
    """Reveal hands and determine winner."""
    hand_p1 = state.card_zones.get("hand_p1")
    hand_p2 = state.card_zones.get("hand_p2")
    reveal_p1 = state.card_zones.get("reveal_p1")
    reveal_p2 = state.card_zones.get("reveal_p2")

    if hand_p1 and reveal_p1:
        for c in list(hand_p1.cards):
            hand_p1.remove(c)
            reveal_p1.add(c)
    if hand_p2 and reveal_p2:
        for c in list(hand_p2.cards):
            hand_p2.remove(c)
            reveal_p2.add(c)

    # Set hand rank names for display
    if reveal_p1 and reveal_p1.cards:
        state.state_vars["p1_hand_rank"] = _poker_hand_name(reveal_p1.cards)
    if reveal_p2 and reveal_p2.cards:
        state.state_vars["p2_hand_rank"] = _poker_hand_name(reveal_p2.cards)

    state.state_vars["round_over"] = True
    state.state_vars["phase"] = "showdown"
    state.state_vars["last_action"] = "showdown"
