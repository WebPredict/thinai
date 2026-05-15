"""Game engine for ThinAI.

Loads a GDL specification and provides the core game loop:
initial state, legal move generation, move application, and
terminal detection.
"""

from __future__ import annotations
import json
from typing import Any, Optional

from engine.gdl.board import GridBoard, GridSpace, TrackBoard, TrackSpace
from engine.gdl.state import GameState, Piece, Move, GameResult, setup_initial_state
from engine.gdl.expr_parser import parse_condition, parse_effect
from engine.gdl.expr_eval import evaluate, execute_effect, EvalContext


class GameEngine:
    """Execute games from GDL specifications."""

    def __init__(self, gdl: dict):
        self.gdl = gdl
        self.meta = gdl["meta"]
        # Pre-parse all condition and effect expressions (parse once, evaluate many)
        self._parsed_rules = []
        for rule in gdl["rules"]:
            parsed = {
                "name": rule["name"],
                "action": rule["action"],
                "params": rule["params"],
                "conditions": [parse_condition(c) for c in rule["conditions"]],
                "effects": [parse_effect(e) for e in rule["effects"]],
                "turn_after": rule.get("turn_after"),
            }
            self._parsed_rules.append(parsed)

        self._parsed_end_conditions = []
        for ec in gdl["end_conditions"]:
            parsed = {
                "type": ec["type"],
                "player": ec.get("player"),
                "condition": parse_condition(ec["condition"]),
                "score": parse_condition(ec["score"]) if "score" in ec else None,
            }
            self._parsed_end_conditions.append(parsed)

        # Parse turn rule if conditional
        self._turn_rule = None
        if self.meta.get("turn_order") == "conditional" and "turn_rule" in self.meta:
            self._turn_rule = self._parse_turn_rule(self.meta["turn_rule"])

    def initial_state(self) -> GameState:
        """Create the starting game state from the GDL setup."""
        return setup_initial_state(self.gdl)

    def _make_context(self, state: GameState, extra_bindings: dict = None) -> EvalContext:
        """Create an EvalContext with engine-level resolvers injected."""
        bindings = dict(extra_bindings or {})
        bindings["_region_resolver"] = lambda name: self._get_region_spaces(name, state)
        bindings["_has_legal_move_fn"] = lambda player: self._has_legal_move(state, player)
        bindings["_gdl"] = self.gdl
        return EvalContext(state, bindings)

    def _has_legal_move(self, state: GameState, player: str) -> bool:
        """Check if a player has any legal move."""
        temp = state.copy()
        temp.current_player = player
        return len(self.legal_moves(temp)) > 0

    def legal_moves(self, state: GameState) -> list[Move]:
        """Generate all legal moves for the current player."""
        moves = []
        for rule in self._parsed_rules:
            for param_combo in self._enumerate_params(rule["params"], state):
                bindings = {p["name"]: v for p, v in zip(rule["params"], param_combo)}
                ctx = self._make_context(state, bindings)
                if all(evaluate(cond, ctx) for cond in rule["conditions"]):
                    moves.append(Move(
                        rule_name=rule["name"],
                        params={p["name"]: v for p, v in zip(rule["params"], param_combo)},
                    ))
        return moves

    def apply_move(self, state: GameState, move: Move) -> GameState:
        """Apply a move to produce a new state."""
        new_state = state.copy()
        new_state.effect_bindings = {}

        # Find the rule
        rule = None
        for r in self._parsed_rules:
            if r["name"] == move.rule_name:
                rule = r
                break
        if rule is None:
            raise ValueError(f"Unknown rule: {move.rule_name}")

        # Build bindings from move params
        bindings = dict(move.params)
        ctx = self._make_context(new_state, bindings)

        # Execute effects in order
        for effect in rule["effects"]:
            execute_effect(effect, ctx)

        # Propagate effect bindings to state for end condition evaluation
        new_state.effect_bindings = dict(ctx.bindings)

        # Check terminal conditions
        result = self._check_terminal(new_state, ctx)
        if result:
            new_state.game_result = result

        # Always advance turn (needed for negamax sign convention)
        self._advance_turn(new_state, rule, ctx)
        new_state.turn_number += 1
        return new_state

    def check_terminal(self, state: GameState) -> Optional[GameResult]:
        """Check if the state is terminal.

        Returns the stored game_result if one was set by apply_move
        (which evaluates with the correct current_player before turn advance).
        Falls back to re-evaluation only if no stored result exists.
        """
        # Use stored result from apply_move (evaluated before turn advance)
        result = getattr(state, 'game_result', None)
        if result is not None:
            return result
        # Fall back to re-evaluation (e.g., for initial state checks)
        ctx = self._make_context(state, state.effect_bindings)
        return self._check_terminal(state, ctx)

    def _check_terminal(self, state: GameState, ctx: EvalContext) -> Optional[GameResult]:
        """Internal terminal check with context."""
        for ec in self._parsed_end_conditions:
            if evaluate(ec["condition"], ctx):
                return self._make_result(ec, state, ctx)
        return None

    def _make_result(self, ec: dict, state: GameState, ctx: EvalContext) -> GameResult:
        """Create a GameResult from a matched end condition."""
        result_type = ec["type"]
        player_spec = ec.get("player")

        if result_type == "draw":
            return GameResult("draw")

        if player_spec == "current_player":
            return GameResult("win", winner=state.current_player)

        if player_spec == "player_by_score":
            # Evaluate score for each player
            scores = {}
            for p in ["player1", "player2"]:
                score_ctx = self._make_context(state, {**ctx.bindings, "current_player": p})
                scores[p] = evaluate(ec["score"], score_ctx)

            if scores["player1"] > scores["player2"]:
                return GameResult("win", winner="player1", scores=scores)
            elif scores["player2"] > scores["player1"]:
                return GameResult("win", winner="player2", scores=scores)
            else:
                return GameResult("draw", scores=scores)

        if player_spec in ("player1", "player2"):
            return GameResult("win", winner=player_spec)

        return GameResult(result_type)

    def _advance_turn(self, state: GameState, rule: dict, ctx: EvalContext):
        """Determine and set the next player."""
        if self.meta["turn_order"] == "alternating":
            state.current_player = state.next_player_alternating()
        elif self._turn_rule:
            next_p = self._eval_turn_rule(state, ctx)
            state.current_player = next_p

    def _parse_turn_rule(self, rule_str: str):
        """Parse a turn rule like 'if has_legal_move(next_player): next_player else: same_player'."""
        # Simple if/else pattern
        rule_str = rule_str.strip()
        if rule_str.startswith("if "):
            rest = rule_str[3:]
            colon_idx = rest.index(":")
            cond_str = rest[:colon_idx].strip()
            rest = rest[colon_idx + 1:].strip()

            if " else:" in rest:
                parts = rest.split(" else:")
                then_str = parts[0].strip()
                else_str = parts[1].strip()
            elif " else: " in rest:
                parts = rest.split(" else: ")
                then_str = parts[0].strip()
                else_str = parts[1].strip()
            else:
                then_str = rest.strip()
                else_str = "next_player"

            return {
                "condition": parse_condition(cond_str),
                "then": then_str,
                "else": else_str,
            }
        return None

    def _eval_turn_rule(self, state: GameState, ctx: EvalContext) -> str:
        """Evaluate the turn rule to determine next player."""
        if self._turn_rule is None:
            return state.next_player_alternating()

        # Inject has_legal_move function
        def has_legal_move_fn(player):
            temp_state = state.copy()
            temp_state.current_player = player
            return len(self.legal_moves(temp_state)) > 0

        eval_ctx = EvalContext(state, {**ctx.bindings, "_has_legal_move_fn": has_legal_move_fn})
        result = evaluate(self._turn_rule["condition"], eval_ctx)

        target = self._turn_rule["then"] if result else self._turn_rule["else"]

        if target == "next_player":
            return state.next_player_alternating()
        elif target == "same_player":
            return state.current_player
        else:
            return target

    def _enumerate_params(self, params: list[dict], state: GameState):
        """Generate all valid parameter combinations."""
        if not params:
            yield ()
            return

        first = params[0]
        rest = params[1:]

        for value in self._enumerate_single_param(first, state):
            if rest:
                for rest_values in self._enumerate_params(rest, state):
                    yield (value,) + rest_values
            else:
                yield (value,)

    def _enumerate_single_param(self, param: dict, state: GameState):
        """Generate valid values for a single parameter."""
        select = param["select"]

        if select == "empty_space":
            board = state.board
            for space in board.spaces:
                if state.is_empty(space):
                    yield space

        elif select == "space":
            board = state.board
            # If there's a 'from' constraint, filter
            from_constraint = param.get("from")
            if from_constraint:
                # Simplified: handle region references
                spaces = self._resolve_param_from(from_constraint, state)
                yield from spaces
            else:
                yield from board.spaces

        elif select.startswith("int_range("):
            inner = select[len("int_range("):-1]
            parts = [int(x.strip()) for x in inner.split(",")]
            yield from range(parts[0], parts[1] + 1)

        elif select == "card_rank":
            # Yield all 13 standard card ranks (used in Go Fish)
            from engine.gdl.cards import RANKS
            yield from RANKS

        else:
            # Unknown selector type
            pass

    def _resolve_param_from(self, from_str: str, state: GameState) -> list:
        """Resolve a 'from' constraint for parameter enumeration."""
        # Handle region(current_player_pits) pattern
        if from_str.startswith("region("):
            region_name = from_str[7:-1]
            return self._get_region_spaces(region_name, state)
        return list(state.board.spaces)

    def _get_region_spaces(self, region_name: str, state: GameState) -> list:
        """Get spaces in a named region, resolving player-relative names."""
        board_spec = self.gdl.get("board", {})
        regions = board_spec.get("regions", [])

        # Direct name match first
        for region in regions:
            if region["name"] == region_name:
                return self._eval_region_spaces(region, state)

        # Resolve player-relative names:
        # "current_player_pits" → "pits_p1" or "pits_p2"
        # "current_player_store" → "store_p1" or "store_p2"
        if "current_player" in region_name:
            suffix = "_p1" if state.current_player == "player1" else "_p2"
            # Try: replace "current_player_X" with "X_pN"
            base = region_name.replace("current_player_", "")
            candidate = f"{base}{suffix}"
            for region in regions:
                if region["name"] == candidate:
                    return self._eval_region_spaces(region, state)

        if "opponent" in region_name:
            suffix = "_p2" if state.current_player == "player1" else "_p1"
            base = region_name.replace("opponent_", "")
            candidate = f"{base}{suffix}"
            for region in regions:
                if region["name"] == candidate:
                    return self._eval_region_spaces(region, state)

        return []

    def _eval_region_spaces(self, region: dict, state: GameState) -> list:
        """Evaluate a region's space selector."""
        from engine.gdl.state import _eval_space_selector
        return _eval_space_selector(region["spaces"], state)

    @classmethod
    def from_file(cls, path: str) -> "GameEngine":
        """Load a GDL specification from a JSON file."""
        with open(path) as f:
            gdl = json.load(f)
        return cls(gdl)
