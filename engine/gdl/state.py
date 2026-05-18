"""Game state representation for ThinAI.

GameState is the central data structure during play. It holds the board
contents, state variables, current player, and enough history to support
undo and terminal detection.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from copy import deepcopy
from typing import Any, Optional

from engine.gdl.board import GridBoard, TrackBoard, GridSpace, TrackSpace, create_board


@dataclass(frozen=True)
class Piece:
    """A game piece on the board."""
    name: str
    owner: Optional[str]  # "player1", "player2", or None for unowned


@dataclass
class Move:
    """A move a player can make."""
    rule_name: str
    params: dict[str, Any]  # param_name → chosen value

    def __repr__(self):
        params_str = ", ".join(f"{k}={v}" for k, v in self.params.items())
        return f"Move({self.rule_name}, {params_str})"


@dataclass
class GameResult:
    """Outcome of a finished game."""
    result_type: str  # "win", "loss", "draw"
    winner: Optional[str] = None  # "player1", "player2", or None for draw
    scores: Optional[dict[str, int]] = None


class GameState:
    """Complete game state at a point in time."""

    def __init__(self, board, players: int = 2):
        self.board = board
        self.players = players
        # Board contents: space → Piece or list[Piece] (for track/stacking)
        self.pieces: dict = {}
        # Card zones (for card games)
        self.card_zones: Optional[dict] = None  # zone_name → CardZone
        # State variables
        self.state_vars: dict[str, Any] = {}
        # Current player (1-indexed: "player1", "player2", ...)
        self.current_player: str = "player1"
        # Turn tracking
        self.turn_number: int = 1
        # Move history for undo
        self.move_history: list[dict] = []
        # Last placed space (set by place effects, used in end conditions)
        self.last_placed: Optional[Any] = None
        # Effect bindings from the most recent move (e.g., _target)
        self.effect_bindings: dict[str, Any] = {}

    def get_piece(self, space) -> Optional[Piece]:
        """Get the piece at a space (for single-piece-per-space boards)."""
        return self.pieces.get(space)

    def get_pieces(self, space) -> list[Piece]:
        """Get all pieces at a space (for stacking/multi-piece spaces)."""
        val = self.pieces.get(space)
        if val is None:
            return []
        if isinstance(val, list):
            return val
        return [val]

    def set_piece(self, space, piece: Optional[Piece]):
        """Set the piece at a space (single piece)."""
        if piece is None:
            self.pieces.pop(space, None)
        else:
            self.pieces[space] = piece

    def add_piece(self, space, piece: Piece):
        """Add a piece to a space (for stacking/multi-piece)."""
        existing = self.pieces.get(space)
        if existing is None:
            self.pieces[space] = [piece]
        elif isinstance(existing, list):
            existing.append(piece)
        else:
            self.pieces[space] = [existing, piece]

    def remove_piece(self, space, piece: Optional[Piece] = None):
        """Remove a piece from a space. If piece is None, remove all."""
        if piece is None:
            self.pieces.pop(space, None)
        else:
            existing = self.pieces.get(space)
            if isinstance(existing, list):
                existing.remove(piece)
                if not existing:
                    del self.pieces[space]
            elif existing == piece:
                del self.pieces[space]

    def count_pieces_at(self, space) -> int:
        """Count pieces at a space."""
        val = self.pieces.get(space)
        if val is None:
            return 0
        if isinstance(val, list):
            return len(val)
        return 1

    def is_empty(self, space) -> bool:
        """Check if a space has no pieces."""
        return space not in self.pieces

    def all_pieces(self) -> list[tuple[Any, Piece]]:
        """Return all (space, piece) pairs on the board."""
        result = []
        for space, val in self.pieces.items():
            if isinstance(val, list):
                for p in val:
                    result.append((space, p))
            else:
                result.append((space, val))
        return result

    def opponent(self, player: Optional[str] = None) -> str:
        """Get the opponent of a player (2-player games)."""
        p = player or self.current_player
        return "player2" if p == "player1" else "player1"

    def next_player_alternating(self) -> str:
        """Get the next player in alternating turn order."""
        if self.current_player == "player1":
            return "player2"
        return "player1"

    def get_zone(self, zone_name: str):
        """Get a card zone by name. Returns None if not a card game."""
        if self.card_zones:
            return self.card_zones.get(zone_name)
        return None

    def copy(self) -> "GameState":
        """Create a deep copy for search."""
        new = GameState.__new__(GameState)
        new.board = self.board  # Board structure is immutable, share it
        new.players = self.players
        new.pieces = dict(self.pieces)  # Shallow copy of pieces dict
        # Deep copy lists for track boards
        for k, v in new.pieces.items():
            if isinstance(v, list):
                new.pieces[k] = list(v)
        # Deep copy card zones
        if self.card_zones:
            from engine.gdl.cards import CardZone
            new.card_zones = {}
            for name, zone in self.card_zones.items():
                new_zone = CardZone(
                    name=zone.name, owner=zone.owner,
                    visible_to=zone.visible_to, ordered=zone.ordered,
                    capacity=zone.capacity,
                )
                new_zone.cards = list(zone.cards)
                new.card_zones[name] = new_zone
        else:
            new.card_zones = None
        new.state_vars = dict(self.state_vars)
        new.current_player = self.current_player
        new.turn_number = self.turn_number
        new.move_history = []  # Don't copy history for search nodes
        new.last_placed = self.last_placed
        new.effect_bindings = dict(self.effect_bindings)
        return new

    def board_hash(self) -> int:
        """Hash the board state for transposition tables."""
        # Convert pieces to a hashable form
        items = []
        for space in sorted(self.pieces.keys(), key=repr):
            val = self.pieces[space]
            if isinstance(val, list):
                items.append((space, tuple(val)))
            else:
                items.append((space, val))
        state_items = tuple(sorted(self.state_vars.items()))
        return hash((tuple(items), state_items, self.current_player))


def setup_initial_state(gdl: dict) -> GameState:
    """Create the initial game state from a GDL specification."""
    board = create_board(gdl["board"])
    state = GameState(board, players=gdl["meta"]["players"])

    # Initialize card zones if this is a card game
    if gdl["board"].get("type") == "card_zones":
        from engine.gdl.cards import CardZone, create_standard_deck
        state.card_zones = {}
        for zone_spec in gdl["board"].get("zones", []):
            zone = CardZone(
                name=zone_spec["name"],
                owner=zone_spec.get("owner"),
                visible_to=zone_spec.get("visible_to", "all"),
                ordered=zone_spec.get("ordered", False),
                capacity=zone_spec.get("capacity"),
            )
            state.card_zones[zone_spec["name"]] = zone

        # Create deck if specified
        deck_type = gdl.get("cards", {}).get("deck", "standard52")
        deck_zone_name = gdl.get("cards", {}).get("deck_zone", "deck")
        if deck_zone_name in state.card_zones:
            cards = create_standard_deck(deck_type)
            for card in cards:
                state.card_zones[deck_zone_name].add(card)

    # Initialize state variables
    for var in gdl.get("state_vars", []):
        state.state_vars[var["name"]] = var["initial"]

    # Apply setup actions
    for action in gdl.get("setup", []):
        _apply_setup_action(action, state, gdl)

    return state


def _apply_setup_action(action: dict, state: GameState, gdl: dict):
    """Apply a single setup action to the state."""
    action_type = action["action"]

    if action_type == "place":
        piece = _parse_piece_ref(action["piece"], gdl)
        space = _parse_space_ref(action["at"], state)
        if isinstance(state.board, GridBoard):
            state.set_piece(space, piece)
        else:
            state.add_piece(space, piece)

    elif action_type == "fill":
        piece_name = action["piece"]
        count = action.get("count", 1)
        # Parse the 'at' selector to find matching spaces
        spaces = _eval_space_selector(action["at"], state)
        for space in spaces:
            for _ in range(count):
                piece = Piece(name=piece_name, owner=None)
                state.add_piece(space, piece)

    elif action_type == "set":
        state.state_vars[action["var"]] = action["value"]

    elif action_type == "checkers_setup":
        from engine.gdl.checkers import setup_checkers
        setup_checkers(state)

    elif action_type == "backgammon_setup":
        _backgammon_setup(state)

    elif action_type == "shuffle":
        # Shuffle a card zone
        if state.card_zones and action["zone"] in state.card_zones:
            state.card_zones[action["zone"]].shuffle()

    elif action_type == "deal":
        # Deal cards from one zone to another
        if state.card_zones:
            from_zone = state.card_zones.get(action["from"])
            to_zone = state.card_zones.get(action["to"])
            count = action.get("count", 1)
            if from_zone and to_zone:
                for _ in range(min(count, from_zone.size)):
                    card = from_zone.draw()
                    if card:
                        to_zone.add(card)

    elif action_type == "reveal":
        # Move top card(s) from one zone to another (face-up)
        if state.card_zones:
            from_zone = state.card_zones.get(action["from"])
            to_zone = state.card_zones.get(action["to"])
            count = action.get("count", 1)
            if from_zone and to_zone:
                for _ in range(min(count, from_zone.size)):
                    card = from_zone.draw()
                    if card:
                        # For Uno: if first discard is an action card, reshuffle
                        action_ranks = {"Skip", "Reverse", "Draw2", "Wild", "WildDraw4"}
                        attempts = 0
                        while card.rank in action_ranks and attempts < 20:
                            from_zone.add(card)
                            import random
                            random.shuffle(from_zone.cards)
                            card = from_zone.draw()
                            attempts += 1
                        to_zone.add(card)


def _parse_piece_ref(piece_str: str, gdl: dict) -> Piece:
    """Parse a piece reference like 'disc(player1)' or 'stone'."""
    if "(" in piece_str:
        name, owner = piece_str.split("(")
        owner = owner.rstrip(")")
        return Piece(name=name, owner=owner)
    return Piece(name=piece_str, owner=None)


def _parse_space_ref(space_str: str, state: GameState):
    """Parse a space reference like 'space_at(3, 3)'."""
    if space_str.startswith("space_at("):
        inner = space_str[len("space_at("):-1]
        parts = [int(x.strip()) for x in inner.split(",")]
        if isinstance(state.board, GridBoard):
            return GridSpace(parts[0], parts[1])
        else:
            return TrackSpace(parts[0])
    raise ValueError(f"Cannot parse space reference: {space_str}")


def _eval_space_selector(selector: str, state: GameState) -> list:
    """Evaluate a simple space selector expression for setup.

    This handles the basic selectors used in setup actions. The full
    expression evaluator (in expr_eval.py) handles the complete language.
    """
    board = state.board
    if isinstance(board, TrackBoard):
        # Handle simple index-based selectors like "index >= 0 and index <= 5"
        result = []
        for space in board.spaces:
            if _eval_simple_index_condition(selector, space.index):
                result.append(space)
        return result
    elif isinstance(board, GridBoard):
        # For grids, return all spaces (setup fill on grids is less common)
        return list(board.spaces)
    return []


def _eval_simple_index_condition(selector: str, index: int) -> bool:
    """Evaluate a simple index-based condition for setup selectors.

    Handles patterns like 'index >= 0 and index <= 5'.
    This is a bootstrap evaluator for setup; the full expression
    evaluator handles the general case.
    """
    # Split on 'and'
    parts = [p.strip() for p in selector.split(" and ")]
    for part in parts:
        part = part.replace("index", str(index))
        # Evaluate simple comparisons
        for op in [">=", "<=", "==", "!=", ">", "<"]:
            if op in part:
                left, right = part.split(op)
                left, right = int(left.strip()), int(right.strip())
                if op == ">=" and not (left >= right):
                    return False
                elif op == "<=" and not (left <= right):
                    return False
                elif op == "==" and not (left == right):
                    return False
                elif op == "!=" and not (left != right):
                    return False
                elif op == ">" and not (left > right):
                    return False
                elif op == "<" and not (left < right):
                    return False
                break
    return True


def _backgammon_setup(state: GameState):
    """Set up the initial backgammon board position."""
    from engine.gdl.board import TrackSpace
    # Standard starting position
    # P1 (White) moves high→low (home = 0-5), P2 (Black) moves low→high (home = 18-23)
    p1_positions = {23: 2, 12: 5, 7: 3, 5: 5}
    p2_positions = {0: 2, 11: 5, 16: 3, 18: 5}
    for pos, count in p1_positions.items():
        for _ in range(count):
            state.add_piece(TrackSpace(pos), Piece("checker", "player1"))
    for pos, count in p2_positions.items():
        for _ in range(count):
            state.add_piece(TrackSpace(pos), Piece("checker", "player2"))
