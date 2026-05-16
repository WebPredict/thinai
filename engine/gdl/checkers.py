"""Checkers (English Draughts) built-in functions for ThinAI.

Handles the complex move generation, execution, and game logic
that's specific to checkers:
- Diagonal movement (forward for men, any direction for kings)
- Mandatory captures (jumps)
- Multi-jump chains
- King promotion on reaching the far row
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from engine.gdl.state import GameState, Piece
from engine.gdl.board import GridBoard, GridSpace


@dataclass(frozen=True)
class CheckersMove:
    """A checkers move — either a simple step or a sequence of jumps."""
    move_id: int
    steps: list  # list of (from_space, to_space) pairs
    captures: list  # list of spaces where captured pieces are
    is_jump: bool

    def __repr__(self):
        if self.is_jump:
            path = " -> ".join(f"({s.row},{s.col})" for _, s in self.steps)
            return f"Jump({path}, captures {len(self.captures)})"
        fr, to = self.steps[0]
        return f"Move(({fr.row},{fr.col})->({to.row},{to.col}))"


def setup_checkers(state: GameState):
    """Place initial checkers pieces on the board."""
    # Player 1 (bottom): rows 5, 6, 7 on dark squares
    # Player 2 (top): rows 0, 1, 2 on dark squares
    for row in range(8):
        for col in range(8):
            # Only dark squares (where row+col is odd)
            if (row + col) % 2 == 1:
                if row < 3:
                    state.set_piece(GridSpace(row, col), Piece("man", "player2"))
                elif row > 4:
                    state.set_piece(GridSpace(row, col), Piece("man", "player1"))


def get_all_moves(state: GameState) -> list[CheckersMove]:
    """Get all legal moves for the current player.

    Enforces mandatory capture: if any jump exists, only jumps are legal.
    """
    player = state.current_player
    must_jump_from = state.state_vars.get("must_jump_from", "")

    # If in a multi-jump, only continue from that piece
    if must_jump_from:
        parts = must_jump_from.split(",")
        from_space = GridSpace(int(parts[0]), int(parts[1]))
        jumps = _get_jumps_from(state, from_space, player)
        return _assign_ids(jumps)

    all_jumps = []
    all_simple = []

    for space in state.board.spaces:
        piece = state.get_piece(space)
        if piece and piece.owner == player:
            jumps = _get_jumps_from(state, space, player)
            all_jumps.extend(jumps)
            if not jumps:  # only check simple moves if no jumps from this piece
                simple = _get_simple_moves(state, space, player)
                all_simple.extend(simple)

    # Mandatory capture: if any jump exists, must jump
    if all_jumps:
        return _assign_ids(all_jumps)
    return _assign_ids(all_simple)


def _assign_ids(moves: list[CheckersMove]) -> list[CheckersMove]:
    """Assign unique IDs to moves."""
    return [CheckersMove(
        move_id=i,
        steps=m.steps,
        captures=m.captures,
        is_jump=m.is_jump,
    ) for i, m in enumerate(moves)]


def _get_forward_dirs(player: str) -> list[tuple[int, int]]:
    """Get forward diagonal directions for a player."""
    if player == "player1":
        return [(-1, -1), (-1, 1)]  # up-left, up-right
    return [(1, -1), (1, 1)]  # down-left, down-right


def _get_all_dirs() -> list[tuple[int, int]]:
    """All four diagonal directions (for kings)."""
    return [(-1, -1), (-1, 1), (1, -1), (1, 1)]


def _get_simple_moves(state: GameState, space: GridSpace,
                       player: str) -> list[CheckersMove]:
    """Get simple (non-jump) moves for a piece."""
    piece = state.get_piece(space)
    if not piece:
        return []

    is_king = piece.name == "king"
    dirs = _get_all_dirs() if is_king else _get_forward_dirs(player)
    moves = []

    for dr, dc in dirs:
        nr, nc = space.row + dr, space.col + dc
        if 0 <= nr < 8 and 0 <= nc < 8:
            target = GridSpace(nr, nc)
            if state.is_empty(target):
                moves.append(CheckersMove(
                    move_id=0,
                    steps=[(space, target)],
                    captures=[],
                    is_jump=False,
                ))

    return moves


def _get_jumps_from(state: GameState, space: GridSpace,
                     player: str) -> list[CheckersMove]:
    """Get all jump sequences starting from a space (including multi-jumps)."""
    piece = state.get_piece(space)
    if not piece:
        return []

    is_king = piece.name == "king"
    dirs = _get_all_dirs() if is_king else _get_forward_dirs(player)
    opponent = "player2" if player == "player1" else "player1"

    results = []
    _find_jumps(state, space, dirs, opponent, is_king, [], [], results)
    return results


def _find_jumps(state: GameState, space: GridSpace,
                dirs: list, opponent: str, is_king: bool,
                steps_so_far: list, captures_so_far: list,
                results: list):
    """Recursively find all jump chains from a position."""
    found_jump = False

    for dr, dc in dirs:
        mid_r, mid_c = space.row + dr, space.col + dc
        land_r, land_c = space.row + 2 * dr, space.col + 2 * dc

        if not (0 <= land_r < 8 and 0 <= land_c < 8):
            continue

        mid = GridSpace(mid_r, mid_c)
        land = GridSpace(land_r, land_c)

        # Can jump: opponent piece in middle, empty landing, not already captured
        mid_piece = state.get_piece(mid)
        if (mid_piece and mid_piece.owner == opponent and
                mid not in captures_so_far and
                state.is_empty(land)):
            found_jump = True
            new_steps = steps_so_far + [(space, land)]
            new_captures = captures_so_far + [mid]

            # Temporarily move piece to check for more jumps
            piece = state.get_piece(space)
            state.set_piece(space, None)
            state.set_piece(land, piece)
            state.set_piece(mid, None)  # remove captured

            # Check for continuation jumps
            _find_jumps(state, land, dirs, opponent, is_king,
                       new_steps, new_captures, results)

            # Undo temporary move
            state.set_piece(space, piece)
            state.set_piece(land, None)
            state.set_piece(mid, mid_piece)

    # If no more jumps found, save the current chain (if any)
    if not found_jump and steps_so_far:
        results.append(CheckersMove(
            move_id=0,
            steps=list(steps_so_far),
            captures=list(captures_so_far),
            is_jump=True,
        ))


def execute_move(state: GameState, move: CheckersMove):
    """Execute a checkers move on the state."""
    if not move.steps:
        return

    # Get the piece being moved
    start = move.steps[0][0]
    end = move.steps[-1][1]
    piece = state.get_piece(start)

    if not piece:
        return

    # Move the piece
    state.set_piece(start, None)

    # Check for king promotion
    player = piece.owner
    promote_row = 0 if player == "player1" else 7
    if end.row == promote_row or piece.name == "king":
        piece = Piece("king", player)

    state.set_piece(end, piece)

    # Remove captured pieces
    for cap_space in move.captures:
        state.set_piece(cap_space, None)

    # Track moves since last capture (for draw detection)
    if move.captures:
        state.state_vars["moves_since_capture"] = 0
    else:
        state.state_vars["moves_since_capture"] = state.state_vars.get("moves_since_capture", 0) + 1

    # Store move description for UI
    state.state_vars["last_move_desc"] = repr(move)

    # Clear multi-jump state
    state.state_vars["must_jump_from"] = ""


def is_draw(state: GameState) -> bool:
    """Check for draw: 40 moves with no capture = draw."""
    return state.state_vars.get("moves_since_capture", 0) >= 40


def opponent_has_no_moves(state: GameState) -> bool:
    """Check if the opponent has no legal moves (current player wins)."""
    opponent = state.opponent()

    for space in state.board.spaces:
        piece = state.get_piece(space)
        if piece and piece.owner == opponent:
            # Check if this piece can move or jump
            is_king = piece.name == "king"
            dirs = _get_all_dirs() if is_king else _get_forward_dirs(opponent)

            for dr, dc in dirs:
                # Simple move
                nr, nc = space.row + dr, space.col + dc
                if 0 <= nr < 8 and 0 <= nc < 8 and state.is_empty(GridSpace(nr, nc)):
                    return False
                # Jump
                lr, lc = space.row + 2 * dr, space.col + 2 * dc
                if 0 <= lr < 8 and 0 <= lc < 8:
                    mid = GridSpace(nr, nc)
                    land = GridSpace(lr, lc)
                    mid_piece = state.get_piece(mid)
                    if mid_piece and mid_piece.owner != opponent and state.is_empty(land):
                        return False

    return True  # No moves found
