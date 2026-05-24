"""Generic grid movement engine for ThinAI.

Provides movement and capture primitives for grid-based games
that aren't using the specialized checkers engine. Supports:
- Orthogonal movement (up/down/left/right)
- Diagonal movement
- All-direction movement (8-way)
- Jump capture (hop over opponent to capture)
- Forward-only movement (toward opponent's side)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from engine.gdl.state import GameState, Piece
from engine.gdl.board import GridBoard, GridSpace


@dataclass
class GridMove:
    """A single movement action on a grid."""
    from_space: GridSpace
    to_space: GridSpace
    captured_space: Optional[GridSpace] = None  # space of captured piece (jump)
    move_id: int = 0


# Direction sets
ORTHOGONAL = [(0, 1), (0, -1), (1, 0), (-1, 0)]
DIAGONAL = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
ALL_DIRS = ORTHOGONAL + DIAGONAL


def get_grid_moves(state: GameState, player: str = None,
                   directions: str = "all", forward_only: bool = False) -> list[GridMove]:
    """Enumerate all valid moves for a player on a grid board.

    Args:
        state: Current game state
        player: Player whose moves to enumerate (default: current player)
        directions: "orthogonal", "diagonal", or "all"
        forward_only: If True, only allow moves toward opponent's side

    Returns:
        List of GridMove objects with assigned move_ids
    """
    if not isinstance(state.board, GridBoard):
        return []

    player = player or state.current_player
    opponent = state.opponent(player)
    board = state.board
    rows, cols = board.rows, board.cols

    # Select direction set
    if directions == "orthogonal":
        dirs = ORTHOGONAL
    elif directions == "diagonal":
        dirs = DIAGONAL
    else:
        dirs = ALL_DIRS

    moves = []
    jumps = []

    # During a jump chain, only the chain piece can move (and only jumps)
    chain_piece_key = state.state_vars.get("_chain_piece") if state.state_vars.get("_jump_chain") else None

    for space in board.spaces:
        piece = state.get_piece(space)
        if not piece or piece.owner != player:
            continue

        # During chain, skip all pieces except the chain piece
        if chain_piece_key and f"{space.row},{space.col}" != chain_piece_key:
            continue

        r, c = space.row, space.col

        # Kings can move in any direction even in forward-only games
        is_king = piece.name == "king"

        for dr, dc in dirs:
            # Forward-only: player1 moves toward row 0, player2 toward max row
            # Kings are exempt — they can move backward
            if forward_only and not is_king:
                if player == "player1" and dr > 0:
                    continue
                if player == "player2" and dr < 0:
                    continue

            nr, nc = r + dr, c + dc

            # Simple move to adjacent empty
            if 0 <= nr < rows and 0 <= nc < cols:
                target = GridSpace(nr, nc)
                if state.is_empty(target):
                    moves.append(GridMove(from_space=space, to_space=target))

            # Jump capture: hop over opponent to empty space beyond
            if 0 <= nr < rows and 0 <= nc < cols:
                mid = GridSpace(nr, nc)
                mid_piece = state.get_piece(mid)
                if mid_piece and mid_piece.owner == opponent:
                    jr, jc = r + 2 * dr, c + 2 * dc
                    if 0 <= jr < rows and 0 <= jc < cols:
                        landing = GridSpace(jr, jc)
                        if state.is_empty(landing):
                            jumps.append(GridMove(
                                from_space=space,
                                to_space=landing,
                                captured_space=mid,
                            ))

    # If jumps available, they're mandatory (like checkers)
    result = jumps if jumps else moves

    for i, m in enumerate(result):
        m.move_id = i

    return result


def execute_grid_move(state: GameState, move_id: int,
                      directions: str = "all", forward_only: bool = False):
    """Execute a grid move by ID."""
    player = state.current_player
    moves = get_grid_moves(state, player, directions, forward_only)

    move = None
    for m in moves:
        if m.move_id == move_id:
            move = m
            break

    if not move:
        return

    # Move the piece
    piece = state.get_piece(move.from_space)
    if not piece:
        return

    state.remove_piece(move.from_space)
    state.set_piece(move.to_space, piece)

    # Handle capture
    if move.captured_space:
        state.remove_piece(move.captured_space)
        state.state_vars["last_play"] = (
            f"{'You' if player == 'player1' else 'AI'} jumped "
            f"({move.from_space.row},{move.from_space.col}) → "
            f"({move.to_space.row},{move.to_space.col}), captured!"
        )
    else:
        state.state_vars["last_play"] = (
            f"{'You' if player == 'player1' else 'AI'} moved "
            f"({move.from_space.row},{move.from_space.col}) → "
            f"({move.to_space.row},{move.to_space.col})"
        )

    # Check for jump chain: if we just jumped and can jump again, flag extra turn
    state.state_vars["_jump_chain"] = False
    if move.captured_space:
        # Check if the piece at the landing square can make another jump
        updated_piece = state.get_piece(move.to_space)
        if updated_piece:
            is_king = updated_piece.name == "king"
            board = state.board
            rows, cols = board.rows, board.cols
            opponent = state.opponent(player)

            if directions == "orthogonal":
                dirs = ORTHOGONAL
            elif directions == "diagonal":
                dirs = DIAGONAL
            else:
                dirs = ALL_DIRS

            for dr, dc in dirs:
                if forward_only and not is_king:
                    if player == "player1" and dr > 0:
                        continue
                    if player == "player2" and dr < 0:
                        continue
                nr, nc = move.to_space.row + dr, move.to_space.col + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    mid = GridSpace(nr, nc)
                    mid_piece = state.get_piece(mid)
                    if mid_piece and mid_piece.owner == opponent:
                        jr, jc = move.to_space.row + 2*dr, move.to_space.col + 2*dc
                        if 0 <= jr < rows and 0 <= jc < cols:
                            landing = GridSpace(jr, jc)
                            if state.is_empty(landing):
                                state.state_vars["_jump_chain"] = True
                                state.state_vars["_chain_piece"] = f"{move.to_space.row},{move.to_space.col}"
                                break

    # Check for promotion: piece reaching back row becomes a king
    if state.state_vars.get("_promotion_enabled"):
        rows = state.board.rows
        promote_row = 0 if player == "player1" else rows - 1
        if move.to_space.row == promote_row and piece.name != "king":
            state.remove_piece(move.to_space)
            state.set_piece(move.to_space, Piece(name="king", owner=player))
            state.state_vars["last_play"] += " — promoted to King!"

    state.last_placed = move.to_space
