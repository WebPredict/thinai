"""Expression parser for ThinAI GDL condition/effect language.

Parses condition and effect strings from GDL JSON into AST nodes
that can be evaluated by expr_eval.py.

Uses Lark for the core grammar, with a transformer to produce AST nodes.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from lark import Lark, Transformer, v_args, Token


# --- AST Node types ---

@dataclass
class Literal:
    value: Any

@dataclass
class Identifier:
    name: str

@dataclass
class PropertyAccess:
    obj: Any  # AST node
    prop: str

@dataclass
class FuncCall:
    name: str
    args: list

@dataclass
class BinOp:
    op: str
    left: Any
    right: Any

@dataclass
class UnaryOp:
    op: str
    operand: Any

@dataclass
class Quantified:
    quantifier: str  # "any", "all", "no", "count"
    var: str
    selector: Any  # AST node for the collection
    body: Any  # AST node for the condition

@dataclass
class SelectorExpr:
    kind: str  # "spaces", "directions", "pieces", "range", "region", "neighbors"
    args: list = field(default_factory=list)
    filter: Any = None  # optional filter expression

# --- Effect AST nodes ---

@dataclass
class PlaceEffect:
    piece_name: str
    piece_owner: Any  # AST node
    target: Any  # AST node

@dataclass
class SetEffect:
    target: str  # variable name
    value: Any  # AST node

@dataclass
class SetPropEffect:
    obj: Any
    prop: str
    value: Any

@dataclass
class RemoveEffect:
    target: Any

@dataclass
class MoveEffect:
    source: Any
    dest: Any

@dataclass
class IfEffect:
    condition: Any
    then_effect: Any
    else_effect: Any = None

@dataclass
class ForEffect:
    var: str
    selector: Any
    body: Any

@dataclass
class EffectFuncCall:
    name: str
    args: list


# --- Lark Grammar ---

GRAMMAR = r"""
    start: expr

    ?expr: or_expr
    ?or_expr: and_expr ("or" and_expr)*  -> or_expr
    ?and_expr: not_expr ("and" not_expr)*  -> and_expr
    ?not_expr: "not" atom  -> not_expr
             | atom

    ?atom: comparison
         | quantified
         | func_call
         | selector
         | "(" expr ")"  -> paren
         | value

    comparison: value comp_op value
    comp_op: "==" -> eq | "!=" -> neq | ">=" -> gte | "<=" -> lte | ">" -> gt | "<" -> lt

    quantified: quantifier IDENT "in" selector ":" expr
    quantifier: "all" -> q_all | "any" -> q_any | "no" -> q_no

    selector: "spaces" filter?             -> sel_spaces
            | "directions" filter?         -> sel_directions
            | "pieces" filter?             -> sel_pieces
            | "neighbors(" expr ")" filter? -> sel_neighbors
            | "region(" expr ")"           -> sel_region
            | "range(" expr "," expr ")"   -> sel_range

    filter: "[" expr "]"

    func_call: IDENT "(" (expr ("," expr)*)? ")"

    ?value: IDENT "." IDENT     -> prop_access
          | SIGNED_NUMBER       -> number
          | ESCAPED_STRING      -> string
          | "true"              -> true_val
          | "false"             -> false_val
          | "empty"             -> empty_val
          | "current_player"    -> current_player
          | "opponent"          -> opponent_val
          | "next_player"       -> next_player
          | "same_player"       -> same_player
          | func_call
          | IDENT               -> identifier

    IDENT: /[a-zA-Z_][a-zA-Z0-9_]*/

    %import common.SIGNED_NUMBER
    %import common.ESCAPED_STRING
    %import common.WS
    %ignore WS
"""


@v_args(inline=True)
class ASTTransformer(Transformer):
    """Transform Lark parse tree into our AST nodes."""

    def start(self, expr):
        return expr

    def or_expr(self, *args):
        result = args[0]
        for arg in args[1:]:
            result = BinOp("or", result, arg)
        return result

    def and_expr(self, *args):
        result = args[0]
        for arg in args[1:]:
            result = BinOp("and", result, arg)
        return result

    def not_expr(self, operand):
        return UnaryOp("not", operand)

    def paren(self, expr):
        return expr

    def comparison(self, left, op, right):
        return BinOp(op, left, right)

    def eq(self): return "=="
    def neq(self): return "!="
    def gte(self): return ">="
    def lte(self): return "<="
    def gt(self): return ">"
    def lt(self): return "<"

    def quantified(self, quant, var, selector, body):
        return Quantified(quant, str(var), selector, body)

    def q_all(self): return "all"
    def q_any(self): return "any"
    def q_no(self): return "no"

    def sel_spaces(self, *args):
        filt = args[0] if args else None
        return SelectorExpr("spaces", filter=filt)

    def sel_directions(self, *args):
        filt = args[0] if args else None
        return SelectorExpr("directions", filter=filt)

    def sel_pieces(self, *args):
        filt = args[0] if args else None
        return SelectorExpr("pieces", filter=filt)

    def sel_neighbors(self, *args):
        space = args[0]
        filt = args[1] if len(args) > 1 else None
        return SelectorExpr("neighbors", [space], filt)

    def sel_region(self, name):
        return SelectorExpr("region", [name])

    def sel_range(self, start, end):
        return SelectorExpr("range", [start, end])

    def filter(self, expr):
        return expr

    def func_call(self, name, *args):
        return FuncCall(str(name), list(args))

    def prop_access(self, obj, prop):
        return PropertyAccess(Identifier(str(obj)), str(prop))

    def number(self, token):
        n = int(token) if "." not in str(token) else float(token)
        return Literal(n)

    def string(self, token):
        return Literal(str(token)[1:-1])  # strip quotes

    def true_val(self):
        return Literal(True)

    def false_val(self):
        return Literal(False)

    def empty_val(self):
        return Literal(None)  # empty is represented as None

    def current_player(self):
        return Identifier("current_player")

    def opponent_val(self):
        return Identifier("opponent")

    def next_player(self):
        return Identifier("next_player")

    def same_player(self):
        return Identifier("same_player")

    def identifier(self, token):
        return Identifier(str(token))


# Singleton parser instance (compiled once)
_condition_parser = Lark(GRAMMAR, parser="earley", ambiguity="resolve")
_transformer = ASTTransformer()


def parse_condition(text: str):
    """Parse a condition expression string into an AST."""
    tree = _condition_parser.parse(text)
    return _transformer.transform(tree)


def parse_effect(text: str):
    """Parse an effect expression string into an AST.

    Effects have imperative syntax (place, set, if, for) that
    the condition grammar doesn't handle. We parse these with
    a specialized approach.
    """
    text = text.strip()

    # place PIECE(OWNER) at TARGET
    if text.startswith("place "):
        return _parse_place_effect(text)

    # set VAR = EXPR
    if text.startswith("set "):
        return _parse_set_effect(text)

    # remove EXPR
    if text.startswith("remove "):
        return _parse_remove_effect(text)

    # move EXPR to EXPR
    if text.startswith("move "):
        return _parse_move_effect(text)

    # if COND: EFFECT [else: EFFECT]
    if text.startswith("if "):
        return _parse_if_effect(text)

    # for VAR in SELECTOR: EFFECT
    if text.startswith("for "):
        return _parse_for_effect(text)

    # Fallback: treat as a function call effect
    return EffectFuncCall(text.split("(")[0], _parse_func_args(text))


def _parse_place_effect(text: str) -> PlaceEffect:
    """Parse 'place piece_name(owner) at target'."""
    # Remove "place "
    rest = text[6:]
    # Split on " at "
    parts = rest.split(" at ", 1)
    piece_part = parts[0].strip()
    target_str = parts[1].strip()

    # Parse piece reference: "mark(current_player)" or "disc(player1)"
    if "(" in piece_part:
        paren_idx = piece_part.index("(")
        piece_name = piece_part[:paren_idx]
        owner_str = piece_part[paren_idx + 1:-1]
        owner = parse_condition(owner_str)
    else:
        piece_name = piece_part
        owner = Literal(None)

    target = parse_condition(target_str)
    return PlaceEffect(piece_name, owner, target)


def _parse_set_effect(text: str) -> SetEffect:
    """Parse 'set var = expr' or 'set var = (expr)'."""
    # Remove "set "
    rest = text[4:]
    eq_idx = rest.index("=")
    var_name = rest[:eq_idx].strip()
    value_str = rest[eq_idx + 1:].strip()

    # Strip outer parens if present
    if value_str.startswith("(") and value_str.endswith(")"):
        value_str = value_str[1:-1]

    value = parse_condition(value_str)
    return SetEffect(var_name, value)


def _parse_remove_effect(text: str) -> RemoveEffect:
    """Parse 'remove expr'."""
    target_str = text[7:].strip()
    return RemoveEffect(parse_condition(target_str))


def _parse_move_effect(text: str) -> MoveEffect:
    """Parse 'move expr to expr'."""
    rest = text[5:]
    parts = rest.split(" to ", 1)
    source = parse_condition(parts[0].strip())
    dest = parse_condition(parts[1].strip())
    return MoveEffect(source, dest)


def _parse_if_effect(text: str) -> IfEffect:
    """Parse 'if condition: effect [else: effect]'."""
    rest = text[3:]

    # Find the colon that separates condition from effect
    # Need to handle nested parens
    depth = 0
    colon_idx = None
    for i, ch in enumerate(rest):
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == ":" and depth == 0:
            colon_idx = i
            break

    if colon_idx is None:
        raise ValueError(f"Cannot parse if effect: {text}")

    cond_str = rest[:colon_idx].strip()
    then_str = rest[colon_idx + 1:].strip()

    condition = parse_condition(cond_str)
    then_effect = parse_effect(then_str)
    return IfEffect(condition, then_effect)


def _parse_for_effect(text: str) -> ForEffect:
    """Parse 'for var in selector: effect'."""
    rest = text[4:]

    # "var in selector: effect"
    in_idx = rest.index(" in ")
    var = rest[:in_idx].strip()
    after_in = rest[in_idx + 4:]

    # Find the colon
    depth = 0
    colon_idx = None
    for i, ch in enumerate(after_in):
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == ":" and depth == 0:
            colon_idx = i
            break

    selector_str = after_in[:colon_idx].strip()
    body_str = after_in[colon_idx + 1:].strip()

    selector = parse_condition(selector_str)
    body = parse_effect(body_str)
    return ForEffect(var, selector, body)


def _parse_func_args(text: str) -> list:
    """Extract function call arguments from text."""
    if "(" not in text:
        return []
    inner = text[text.index("(") + 1:text.rindex(")")]
    if not inner.strip():
        return []
    # Simple split on commas (doesn't handle nested commas)
    return [parse_condition(a.strip()) for a in inner.split(",")]
