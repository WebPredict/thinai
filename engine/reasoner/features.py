"""Feature extraction for learnable evaluation.

Each game has a set of features — numerical properties of a game state
that the evaluator uses to score positions. Features are hand-crafted
but their weights are learned through play.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Callable

from engine.gdl.state import GameState, Piece
from engine.gdl.board import GridBoard, GridSpace, TrackBoard, TrackSpace
from engine.gdl.expr_eval import _line_length


@dataclass
class FeatureSpec:
    """A named, extractable feature of a game state."""
    name: str
    description: str
    extract: Callable[[GameState, str], float]  # (state, player) -> float


# ============================================================
# Tic-Tac-Toe features
# ============================================================

def _ttt_center_control(state: GameState, player: str) -> float:
    """1.0 if player owns center, -1.0 if opponent, 0.0 if empty."""
    center = GridSpace(1, 1)
    piece = state.get_piece(center)
    if piece is None:
        return 0.0
    return 1.0 if piece.owner == player else -1.0


def _ttt_corner_count(state: GameState, player: str) -> float:
    """(player corners - opponent corners) / 4."""
    corners = [GridSpace(0, 0), GridSpace(0, 2), GridSpace(2, 0), GridSpace(2, 2)]
    score = 0
    for c in corners:
        piece = state.get_piece(c)
        if piece is not None:
            score += 1 if piece.owner == player else -1
    return score / 4.0


def _ttt_two_in_row(state: GameState, player: str) -> float:
    """Count open 2-in-a-rows (player minus opponent), normalized."""
    if not isinstance(state.board, GridBoard):
        return 0.0
    opponent = state.opponent(player)
    my_twos = 0
    opp_twos = 0
    for space in state.board.spaces:
        for d in state.board.directions():
            length = _line_length(state, space, d, player)
            if length == 2:
                my_twos += 1
            length = _line_length(state, space, d, opponent)
            if length == 2:
                opp_twos += 1
    # Each line counted twice (from each end), and from middle
    return (my_twos - opp_twos) / 16.0


def _ttt_threats(state: GameState, player: str) -> float:
    """Positions where player can win next move, minus opponent's."""
    if not isinstance(state.board, GridBoard):
        return 0.0
    opponent = state.opponent(player)
    my_threats = 0
    opp_threats = 0
    for space in state.board.spaces:
        if not state.is_empty(space):
            continue
        for d in state.board.directions():
            # Temporarily place piece and check line
            state.set_piece(space, Piece("mark", player))
            if _line_length(state, space, d, player) >= 3:
                my_threats += 1
            state.set_piece(space, Piece("mark", opponent))
            if _line_length(state, space, d, opponent) >= 3:
                opp_threats += 1
            state.set_piece(space, None)
    return (my_threats - opp_threats) / 8.0


TTT_FEATURES = [
    FeatureSpec("center_control", "Owns the center square", _ttt_center_control),
    FeatureSpec("corner_count", "Corners owned vs opponent", _ttt_corner_count),
    FeatureSpec("two_in_row", "Open 2-in-a-rows vs opponent", _ttt_two_in_row),
    FeatureSpec("threats", "Winning threats vs opponent", _ttt_threats),
]


# ============================================================
# Connect Four features
# ============================================================

def _c4_center_column(state: GameState, player: str) -> float:
    """Pieces in center 3 columns (player - opponent) / total on board."""
    if not isinstance(state.board, GridBoard):
        return 0.0
    opponent = state.opponent(player)
    center_cols = [2, 3, 4]
    score = 0
    total = 0
    for r in range(state.board.rows):
        for c in center_cols:
            piece = state.get_piece(GridSpace(r, c))
            if piece is not None:
                total += 1
                score += 1 if piece.owner == player else -1
    return score / max(total, 1)


def _c4_two_in_row(state: GameState, player: str) -> float:
    """Open 2-in-a-rows, normalized."""
    if not isinstance(state.board, GridBoard):
        return 0.0
    opponent = state.opponent(player)
    my_count = 0
    opp_count = 0
    for space in state.board.spaces:
        piece = state.get_piece(space)
        if piece is None:
            continue
        for d in state.board.directions():
            length = _line_length(state, space, d, piece.owner)
            if length == 2:
                if piece.owner == player:
                    my_count += 1
                else:
                    opp_count += 1
    return (my_count - opp_count) / 20.0


def _c4_three_in_row(state: GameState, player: str) -> float:
    """Open 3-in-a-rows — very valuable."""
    if not isinstance(state.board, GridBoard):
        return 0.0
    opponent = state.opponent(player)
    my_count = 0
    opp_count = 0
    for space in state.board.spaces:
        piece = state.get_piece(space)
        if piece is None:
            continue
        for d in state.board.directions():
            length = _line_length(state, space, d, piece.owner)
            if length == 3:
                if piece.owner == player:
                    my_count += 1
                else:
                    opp_count += 1
    return (my_count - opp_count) / 8.0


def _c4_height_control(state: GameState, player: str) -> float:
    """Lower pieces are more central/controlling. Normalized average height difference."""
    if not isinstance(state.board, GridBoard):
        return 0.0
    opponent = state.opponent(player)
    my_height_sum = 0
    my_count = 0
    opp_height_sum = 0
    opp_count = 0
    max_row = state.board.rows - 1
    for space in state.board.spaces:
        piece = state.get_piece(space)
        if piece is None:
            continue
        # Lower row number = higher on board = less central
        centrality = (max_row - space.row) / max_row
        if piece.owner == player:
            my_height_sum += centrality
            my_count += 1
        else:
            opp_height_sum += centrality
            opp_count += 1
    my_avg = my_height_sum / max(my_count, 1)
    opp_avg = opp_height_sum / max(opp_count, 1)
    return my_avg - opp_avg


C4_FEATURES = [
    FeatureSpec("center_column", "Control of center columns", _c4_center_column),
    FeatureSpec("two_in_row", "Open 2-in-a-rows", _c4_two_in_row),
    FeatureSpec("three_in_row", "Open 3-in-a-rows (strong threats)", _c4_three_in_row),
    FeatureSpec("height_control", "Average piece height advantage", _c4_height_control),
]


# ============================================================
# Mancala features
# ============================================================

def _mancala_store_lead(state: GameState, player: str) -> float:
    """Stone lead in stores, normalized to 48 (total stones)."""
    my_store = 6 if player == "player1" else 13
    opp_store = 13 if player == "player1" else 6
    my_count = state.count_pieces_at(TrackSpace(my_store))
    opp_count = state.count_pieces_at(TrackSpace(opp_store))
    return (my_count - opp_count) / 48.0


def _mancala_pit_total(state: GameState, player: str) -> float:
    """Total stones on my side vs opponent side, normalized."""
    if player == "player1":
        my_pits = range(0, 6)
        opp_pits = range(7, 13)
    else:
        my_pits = range(7, 13)
        opp_pits = range(0, 6)
    my_total = sum(state.count_pieces_at(TrackSpace(i)) for i in my_pits)
    opp_total = sum(state.count_pieces_at(TrackSpace(i)) for i in opp_pits)
    return (my_total - opp_total) / 48.0


def _mancala_capture_opportunities(state: GameState, player: str) -> float:
    """Count pits where sowing would end on empty own-side pit with opposite stones."""
    if player == "player1":
        my_pits = range(0, 6)
    else:
        my_pits = range(7, 13)
    opportunities = 0
    for i in my_pits:
        count = state.count_pieces_at(TrackSpace(i))
        if count == 0:
            continue
        # Where would the last stone land?
        landing = (i + count) % 14
        # Check if landing is on our side, empty, and opposite has stones
        if player == "player1" and 0 <= landing <= 5:
            if state.count_pieces_at(TrackSpace(landing)) == 0:
                opposite = 12 - landing
                if state.count_pieces_at(TrackSpace(opposite)) > 0:
                    opportunities += 1
        elif player == "player2" and 7 <= landing <= 12:
            if state.count_pieces_at(TrackSpace(landing)) == 0:
                opposite = 12 - (landing - 7) + 7  # map to opponent side
                # Actually, standard opposite: 12 - landing for p1 side
                opposite = 12 - landing
                if state.count_pieces_at(TrackSpace(opposite)) > 0:
                    opportunities += 1
    return opportunities / 6.0


def _mancala_extra_turn_opportunities(state: GameState, player: str) -> float:
    """Count pits where sowing would end in own store."""
    my_store = 6 if player == "player1" else 13
    if player == "player1":
        my_pits = range(0, 6)
    else:
        my_pits = range(7, 13)
    opportunities = 0
    for i in my_pits:
        count = state.count_pieces_at(TrackSpace(i))
        if count == 0:
            continue
        landing = (i + count) % 14
        if landing == my_store:
            opportunities += 1
    return opportunities / 6.0


def _mancala_empty_pits(state: GameState, player: str) -> float:
    """Opponent empty pits minus my empty pits (more opponent empties = closer to game end in our favor)."""
    if player == "player1":
        my_pits = range(0, 6)
        opp_pits = range(7, 13)
    else:
        my_pits = range(7, 13)
        opp_pits = range(0, 6)
    my_empty = sum(1 for i in my_pits if state.count_pieces_at(TrackSpace(i)) == 0)
    opp_empty = sum(1 for i in opp_pits if state.count_pieces_at(TrackSpace(i)) == 0)
    return (opp_empty - my_empty) / 6.0


MANCALA_FEATURES = [
    FeatureSpec("store_lead", "Stone lead in stores", _mancala_store_lead),
    FeatureSpec("pit_total", "Stones on own side vs opponent", _mancala_pit_total),
    FeatureSpec("capture_opportunities", "Available capture moves", _mancala_capture_opportunities),
    FeatureSpec("extra_turn_opportunities", "Moves ending in own store", _mancala_extra_turn_opportunities),
    FeatureSpec("empty_pits", "Opponent empty pits advantage", _mancala_empty_pits),
]


# ============================================================
# Reversi features
# ============================================================

def _reversi_disc_count(state: GameState, player: str) -> float:
    """Disc count advantage, normalized to 64."""
    opponent = state.opponent(player)
    my_count = sum(1 for _, p in state.all_pieces() if p.owner == player)
    opp_count = sum(1 for _, p in state.all_pieces() if p.owner == opponent)
    return (my_count - opp_count) / 64.0


def _reversi_corner_count(state: GameState, player: str) -> float:
    """Corner control (corners are extremely valuable in Reversi)."""
    corners = [GridSpace(0, 0), GridSpace(0, 7), GridSpace(7, 0), GridSpace(7, 7)]
    opponent = state.opponent(player)
    score = 0
    for c in corners:
        piece = state.get_piece(c)
        if piece is not None:
            score += 1 if piece.owner == player else -1
    return score / 4.0


def _reversi_edge_count(state: GameState, player: str) -> float:
    """Edge pieces (stable positions along borders)."""
    if not isinstance(state.board, GridBoard):
        return 0.0
    opponent = state.opponent(player)
    score = 0
    for r in range(8):
        for c in range(8):
            if r == 0 or r == 7 or c == 0 or c == 7:
                piece = state.get_piece(GridSpace(r, c))
                if piece is not None:
                    score += 1 if piece.owner == player else -1
    return score / 28.0


def _reversi_mobility(state: GameState, player: str) -> float:
    """Legal move count advantage. More options = better position."""
    # We can't easily call engine.legal_moves here without circular import,
    # so we approximate by counting empty spaces adjacent to opponent pieces
    if not isinstance(state.board, GridBoard):
        return 0.0
    opponent = state.opponent(player)
    my_adjacent = set()
    opp_adjacent = set()
    for space in state.board.spaces:
        if not state.is_empty(space):
            continue
        for n in state.board.neighbors(space):
            piece = state.get_piece(n)
            if piece is not None:
                if piece.owner == opponent:
                    my_adjacent.add(space)
                elif piece.owner == player:
                    opp_adjacent.add(space)
    return (len(my_adjacent) - len(opp_adjacent)) / 20.0


def _reversi_x_square_penalty(state: GameState, player: str) -> float:
    """Penalty for owning X-squares (diagonal to empty corners)."""
    x_squares = {
        GridSpace(0, 0): GridSpace(1, 1),
        GridSpace(0, 7): GridSpace(1, 6),
        GridSpace(7, 0): GridSpace(6, 1),
        GridSpace(7, 7): GridSpace(6, 6),
    }
    opponent = state.opponent(player)
    penalty = 0
    for corner, x_sq in x_squares.items():
        if state.is_empty(corner):
            piece = state.get_piece(x_sq)
            if piece is not None:
                penalty += 1 if piece.owner == player else -1
    return -penalty / 4.0  # Negative: owning X-squares near empty corners is bad


REVERSI_FEATURES = [
    FeatureSpec("disc_count", "Total disc advantage", _reversi_disc_count),
    FeatureSpec("corner_count", "Corner control (very valuable)", _reversi_corner_count),
    FeatureSpec("edge_count", "Edge piece advantage", _reversi_edge_count),
    FeatureSpec("mobility", "Move option advantage", _reversi_mobility),
    FeatureSpec("x_square_penalty", "Penalty for X-squares near empty corners", _reversi_x_square_penalty),
]


# ============================================================
# Nim features
# ============================================================

def _nim_total_stones(state: GameState, player: str) -> float:
    """Total stones remaining, normalized. Fewer stones = closer to end."""
    if not isinstance(state.board, TrackBoard):
        return 0.0
    total = sum(state.count_pieces_at(TrackSpace(i)) for i in range(state.board.length))
    return total / 12.0  # 3+4+5 = 12 initial stones


def _nim_xor_position(state: GameState, player: str) -> float:
    """Nim-sum (XOR of pile sizes). 0 = losing position for player to move."""
    if not isinstance(state.board, TrackBoard):
        return 0.0
    xor = 0
    for i in range(state.board.length):
        xor ^= state.count_pieces_at(TrackSpace(i))
    # Non-zero XOR is winning for the player to move
    # Return positive if it's our turn (we're in a winning position)
    if state.current_player == player:
        return 1.0 if xor != 0 else -1.0
    else:
        return -1.0 if xor != 0 else 1.0


def _nim_pile_balance(state: GameState, player: str) -> float:
    """How balanced the piles are. More balanced = harder to play optimally."""
    if not isinstance(state.board, TrackBoard):
        return 0.0
    sizes = [state.count_pieces_at(TrackSpace(i)) for i in range(state.board.length)]
    non_zero = [s for s in sizes if s > 0]
    if len(non_zero) <= 1:
        return 0.0
    avg = sum(non_zero) / len(non_zero)
    variance = sum((s - avg) ** 2 for s in non_zero) / len(non_zero)
    return variance / 10.0  # Normalize


def _nim_single_pile_count(state: GameState, player: str) -> float:
    """Number of piles with exactly 1 stone. Important for endgame."""
    if not isinstance(state.board, TrackBoard):
        return 0.0
    count = sum(1 for i in range(state.board.length) if state.count_pieces_at(TrackSpace(i)) == 1)
    return count / state.board.length


NIM_FEATURES = [
    FeatureSpec("total_stones", "Total stones remaining", _nim_total_stones),
    # xor_position removed — it encodes the optimal strategy directly,
    # which means the system doesn't need to learn anything. A kid
    # wouldn't know the XOR trick; they'd notice simpler patterns.
    FeatureSpec("pile_balance", "Pile size variance", _nim_pile_balance),
    FeatureSpec("single_pile_count", "Piles with exactly 1 stone", _nim_single_pile_count),
]


# ============================================================
# Chutes and Ladders features
# ============================================================

def _cl_position_lead(state: GameState, player: str) -> float:
    """Position advantage — how far ahead of opponent."""
    if not isinstance(state.board, TrackBoard):
        return 0.0
    opponent = state.opponent(player)
    my_pos = 0
    opp_pos = 0
    for space, piece in state.all_pieces():
        if piece.name == "token":
            if piece.owner == player:
                my_pos = space.index
            elif piece.owner == opponent:
                opp_pos = space.index
    return (my_pos - opp_pos) / 25.0


def _cl_progress(state: GameState, player: str) -> float:
    """How close to the goal (0-1)."""
    if not isinstance(state.board, TrackBoard):
        return 0.0
    for space, piece in state.all_pieces():
        if piece.name == "token" and piece.owner == player:
            return space.index / 25.0
    return 0.0


CL_FEATURES = [
    FeatureSpec("position_lead", "Position advantage over opponent", _cl_position_lead),
    FeatureSpec("progress", "Progress toward goal", _cl_progress),
]


# ============================================================
# Feature Registry
# ============================================================

FEATURE_REGISTRY: dict[str, list[FeatureSpec]] = {
    "Tic-Tac-Toe": TTT_FEATURES,
    "Connect Four": C4_FEATURES,
    "Mancala (Kalah)": MANCALA_FEATURES,
    "Reversi": REVERSI_FEATURES,
    "Nim": NIM_FEATURES,
    "Chutes and Ladders": CL_FEATURES,
}


def get_features(game_name: str) -> list[FeatureSpec]:
    """Get features for a game by name. Returns empty list if unknown."""
    return FEATURE_REGISTRY.get(game_name, [])
