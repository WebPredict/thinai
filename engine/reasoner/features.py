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
# Go Fish features
# ============================================================

def _gofish_near_sets(state: GameState, player: str) -> float:
    """How many ranks do I hold 3 of? (One card away from a set.)"""
    suffix = "p1" if player == "player1" else "p2"
    hand = state.get_zone(f"hand_{suffix}")
    if not hand:
        return 0.0
    from collections import Counter
    ranks = Counter(c.rank for c in hand.cards)
    triples = sum(1 for count in ranks.values() if count >= 3)
    return triples / 4.0


def _gofish_pairs(state: GameState, player: str) -> float:
    """How many ranks do I hold 2 of? (Good targets to ask for.)"""
    suffix = "p1" if player == "player1" else "p2"
    hand = state.get_zone(f"hand_{suffix}")
    if not hand:
        return 0.0
    from collections import Counter
    ranks = Counter(c.rank for c in hand.cards)
    pairs = sum(1 for count in ranks.values() if count >= 2)
    return pairs / 6.0


def _gofish_hand_size(state: GameState, player: str) -> float:
    """Cards in hand — more options = better."""
    suffix = "p1" if player == "player1" else "p2"
    hand = state.get_zone(f"hand_{suffix}")
    return (hand.size / 15.0) if hand else 0.0


def _gofish_set_lead(state: GameState, player: str) -> float:
    """My completed sets minus opponent's."""
    opp = "p2" if player == "player1" else "p1"
    my_suffix = "p1" if player == "player1" else "p2"
    my_sets = state.get_zone(f"sets_{my_suffix}")
    opp_sets = state.get_zone(f"sets_{opp}")
    my_count = (my_sets.size // 4) if my_sets else 0
    opp_count = (opp_sets.size // 4) if opp_sets else 0
    return (my_count - opp_count) / 7.0


# ============================================================
# Checkers features
# ============================================================

def _checkers_piece_advantage(state: GameState, player: str) -> float:
    """My pieces minus opponent's pieces."""
    opponent = state.opponent(player)
    my_count = sum(1 for _, p in state.all_pieces() if p.owner == player)
    opp_count = sum(1 for _, p in state.all_pieces() if p.owner == opponent)
    return (my_count - opp_count) / 12.0


def _checkers_king_count(state: GameState, player: str) -> float:
    """My kings minus opponent's kings."""
    opponent = state.opponent(player)
    my_kings = sum(1 for _, p in state.all_pieces() if p.owner == player and p.name == "king")
    opp_kings = sum(1 for _, p in state.all_pieces() if p.owner == opponent and p.name == "king")
    return (my_kings - opp_kings) / 6.0


def _checkers_advancement(state: GameState, player: str) -> float:
    """How far forward my pieces are (closer to promotion)."""
    if not isinstance(state.board, GridBoard):
        return 0.0
    total = 0.0
    count = 0
    for space, piece in state.all_pieces():
        if piece.owner == player and piece.name == "man":
            if player == "player1":
                progress = (7 - space.row) / 7.0  # row 0 = promoted
            else:
                progress = space.row / 7.0  # row 7 = promoted
            total += progress
            count += 1
    return total / max(count, 1)


def _checkers_center_control(state: GameState, player: str) -> float:
    """Pieces in the center 4x4 area vs opponent."""
    if not isinstance(state.board, GridBoard):
        return 0.0
    opponent = state.opponent(player)
    my_center = 0
    opp_center = 0
    for space, piece in state.all_pieces():
        if 2 <= space.row <= 5 and 2 <= space.col <= 5:
            if piece.owner == player:
                my_center += 1
            elif piece.owner == opponent:
                opp_center += 1
    return (my_center - opp_center) / 8.0


CHECKERS_FEATURES = [
    FeatureSpec("piece_advantage", "My pieces minus opponent's", _checkers_piece_advantage),
    FeatureSpec("king_count", "My kings minus opponent's kings", _checkers_king_count),
    FeatureSpec("advancement", "How close my pieces are to promotion", _checkers_advancement),
    FeatureSpec("center_control", "Pieces in center area", _checkers_center_control),
]


GOFISH_FEATURES = [
    FeatureSpec("near_sets", "Ranks where I hold 3 cards (one away from set)", _gofish_near_sets),
    FeatureSpec("pairs", "Ranks where I hold 2 cards (good ask targets)", _gofish_pairs),
    FeatureSpec("hand_size", "Cards in hand (more options)", _gofish_hand_size),
    FeatureSpec("set_lead", "My sets minus opponent's sets", _gofish_set_lead),
]


# ============================================================

def _hex_connection_progress(state: GameState, player: str) -> float:
    """How close is the player to connecting their two sides (0 to 1)."""
    if not isinstance(state.board, GridBoard):
        return 0.0
    rows, cols = state.board.rows, state.board.cols
    owned = set()
    for space in state.board.spaces:
        pieces = state.get_pieces(space)
        if any(p.owner == player for p in pieces):
            owned.add((space.row, space.col))
    if not owned:
        return 0.0

    # BFS from start edge, measure how deep we reach toward target edge
    if player == "player1":
        start = {(r, c) for r, c in owned if r == 0}
        max_progress = lambda r, c: r / (rows - 1) if rows > 1 else 1
    else:
        start = {(r, c) for r, c in owned if c == 0}
        max_progress = lambda r, c: c / (cols - 1) if cols > 1 else 1

    if not start:
        return 0.0

    visited = set(start)
    queue = list(start)
    best = max(max_progress(r, c) for r, c in start)

    while queue:
        r, c = queue.pop(0)
        prog = max_progress(r, c)
        if prog > best:
            best = prog
        for dr, dc in state.board.direction_vectors:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and (nr, nc) not in visited and (nr, nc) in owned:
                visited.add((nr, nc))
                queue.append((nr, nc))

    return best


def _hex_center_mass(state: GameState, player: str) -> float:
    """How central are the player's pieces."""
    if not isinstance(state.board, GridBoard):
        return 0.0
    rows, cols = state.board.rows, state.board.cols
    center_r, center_c = rows / 2, cols / 2
    count = 0
    total_dist = 0
    for space in state.board.spaces:
        pieces = state.get_pieces(space)
        if any(p.owner == player for p in pieces):
            count += 1
            total_dist += abs(space.row - center_r) + abs(space.col - center_c)
    if count == 0:
        return 0.0
    max_dist = center_r + center_c
    return 1.0 - (total_dist / count) / max_dist


HEX_FEATURES = [
    FeatureSpec("connection_progress", "How close to connecting my two sides",
                lambda s, p: _hex_connection_progress(s, p)),
    FeatureSpec("opp_connection_progress", "How close opponent is to connecting",
                lambda s, p: -_hex_connection_progress(s, s.opponent(p))),
    FeatureSpec("piece_count", "Number of my pieces on the board",
                lambda s, p: sum(1 for sp in s.board.spaces if any(pc.owner == p for pc in s.get_pieces(sp))) / 49),
    FeatureSpec("center_control", "How central my pieces are",
                lambda s, p: _hex_center_mass(s, p)),
    FeatureSpec("blocking", "Opponent's connection is less than halfway",
                lambda s, p: 1.0 if _hex_connection_progress(s, s.opponent(p)) < 0.5 else 0.0),
]


def _bg_pip_count(state: GameState, player: str) -> float:
    """Total distance of player's checkers from bearing off (lower is better)."""
    total = 0
    is_p1 = player == "player1"
    for i in range(24):
        pieces = state.get_pieces(TrackSpace(i))
        count = sum(1 for p in pieces if p.owner == player)
        if count > 0:
            dist = i + 1 if is_p1 else 24 - i  # distance to bear-off
            total += count * dist
    # Bar checkers count as 25
    bar = 24 if is_p1 else 25
    bar_count = sum(1 for p in state.get_pieces(TrackSpace(bar)) if p.owner == player)
    total += bar_count * 25
    return total / 167.0  # normalize by starting pip count


def _bg_blots(state: GameState, player: str) -> float:
    """Number of single checkers (vulnerable to being hit)."""
    count = 0
    for i in range(24):
        pieces = state.get_pieces(TrackSpace(i))
        mine = sum(1 for p in pieces if p.owner == player)
        if mine == 1:
            count += 1
    return count / 15.0


def _bg_home_count(state: GameState, player: str) -> float:
    """How many checkers are in the home quadrant."""
    is_p1 = player == "player1"
    home = range(0, 6) if is_p1 else range(18, 24)
    count = 0
    for i in home:
        pieces = state.get_pieces(TrackSpace(i))
        count += sum(1 for p in pieces if p.owner == player)
    # Add borne off
    bear_off = 26 if is_p1 else 27
    count += sum(1 for p in state.get_pieces(TrackSpace(bear_off)) if p.owner == player)
    return count / 15.0


BACKGAMMON_FEATURES = [
    FeatureSpec("pip_advantage", "Lower pip count is closer to winning",
                lambda s, p: _bg_pip_count(s, s.opponent(p)) - _bg_pip_count(s, p)),
    FeatureSpec("blot_safety", "Fewer exposed single checkers is safer",
                lambda s, p: _bg_blots(s, s.opponent(p)) - _bg_blots(s, p)),
    FeatureSpec("home_progress", "More checkers in home quadrant = closer to bearing off",
                lambda s, p: _bg_home_count(s, p)),
    FeatureSpec("bearing_off", "Checkers already borne off",
                lambda s, p: sum(1 for pc in s.get_pieces(TrackSpace(26 if p == 'player1' else 27)) if pc.owner == p) / 15.0),
    FeatureSpec("bar_penalty", "Checkers on the bar is bad",
                lambda s, p: -sum(1 for pc in s.get_pieces(TrackSpace(24 if p == 'player1' else 25)) if pc.owner == p) / 15.0),
]


def _gin_deadwood(state: GameState, player: str) -> float:
    """Get deadwood for a player in Gin Rummy."""
    from engine.gdl.expr_eval import _gin_rummy_deadwood
    suffix = "p1" if player == "player1" else "p2"
    hand = state.card_zones.get(f"hand_{suffix}") if state.card_zones else None
    if not hand or not hand.cards:
        return 0.0
    return _gin_rummy_deadwood(hand.cards) / 100.0  # normalize


def _gin_melds(state: GameState, player: str) -> float:
    """Count melds in player's hand."""
    from engine.gdl.expr_eval import _gin_rummy_best_melds
    suffix = "p1" if player == "player1" else "p2"
    hand = state.card_zones.get(f"hand_{suffix}") if state.card_zones else None
    if not hand or not hand.cards:
        return 0.0
    melds, _ = _gin_rummy_best_melds(hand.cards)
    return len(melds) / 4.0  # normalize by max reasonable melds


GIN_RUMMY_FEATURES = [
    FeatureSpec("deadwood_advantage", "Lower deadwood than opponent",
                lambda s, p: _gin_deadwood(s, s.opponent(p)) - _gin_deadwood(s, p)),
    FeatureSpec("meld_count", "Number of melds formed",
                lambda s, p: _gin_melds(s, p)),
    FeatureSpec("near_knock", "How close to being able to knock (deadwood <= 10)",
                lambda s, p: max(0, 1.0 - _gin_deadwood(s, p) * 10)),
    FeatureSpec("hand_size", "Cards in hand (fewer after knock = better)",
                lambda s, p: -(_gin_deadwood(s, p))),
]


def _poker_hand_strength(state: GameState, player: str) -> float:
    """Poker hand rank for a player."""
    from engine.gdl.expr_eval import _poker_hand_rank
    suffix = "p1" if player == "player1" else "p2"
    hand = state.card_zones.get(f"hand_{suffix}") if state.card_zones else None
    if not hand or len(hand.cards) < 5:
        return 0.0
    rank = _poker_hand_rank(hand.cards)
    return rank[0] / 8.0  # normalize tier 0-8


POKER_FEATURES = [
    FeatureSpec("hand_strength", "How strong my poker hand is (pair, flush, etc.)",
                lambda s, p: _poker_hand_strength(s, p)),
    FeatureSpec("hand_advantage", "My hand rank minus opponent's",
                lambda s, p: _poker_hand_strength(s, p) - _poker_hand_strength(s, s.opponent(p))),
]


# ============================================================
# Wizard features
# ============================================================

def _wizard_trump_count(state: GameState, player: str) -> float:
    """Count of trump-suited cards in hand, normalized."""
    suffix = "p1" if player == "player1" else "p2"
    hand = state.card_zones.get(f"hand_{suffix}") if state.card_zones else None
    if not hand:
        return 0.0
    trump = state.state_vars.get("trump_suit", "")
    return sum(1 for c in hand.cards if c.suit == trump) / 5.0


def _wizard_high_cards(state: GameState, player: str) -> float:
    """Count of high cards (rank >= Q) in hand, normalized."""
    suffix = "p1" if player == "player1" else "p2"
    hand = state.card_zones.get(f"hand_{suffix}") if state.card_zones else None
    if not hand:
        return 0.0
    high_ranks = {"Q", "K", "A"}
    return sum(1 for c in hand.cards if c.rank in high_ranks) / 5.0


def _wizard_bid_match(state: GameState, player: str) -> float:
    """How well the bid matches hand strength (trump + high cards).
    During bidding, rewards bids that match estimated winning potential.
    During play, rewards being on track to hit the bid."""
    suffix = "p1" if player == "player1" else "p2"
    bid = state.state_vars.get(f"{suffix}_bid", -1)
    if bid < 0:
        return 0.0  # haven't bid yet

    # Estimate hand strength: trump cards + high cards (A, K, Q)
    hand = state.card_zones.get(f"hand_{suffix}") if state.card_zones else None
    if hand and hand.cards:
        trump = state.state_vars.get("trump_suit", "")
        high_ranks = {"A", "K", "Q"}
        expected = sum(1 for c in hand.cards if c.suit == trump or c.rank in high_ranks)
        # Reward bids close to expected tricks
        return -abs(bid - expected) / 5.0
    else:
        # During play: reward being on track
        tricks = state.state_vars.get(f"{suffix}_tricks_won", 0)
        return -abs(tricks - bid) / 5.0


def _wizard_score_lead(state: GameState, player: str) -> float:
    """Score advantage over opponent."""
    my = "p1" if player == "player1" else "p2"
    opp = "p2" if player == "player1" else "p1"
    return (state.state_vars.get(f"{my}_score", 0) - state.state_vars.get(f"{opp}_score", 0)) / 100.0


def _wizard_void_suits(state: GameState, player: str) -> float:
    """Count of suits with 0 cards (can trump in when void)."""
    suffix = "p1" if player == "player1" else "p2"
    hand = state.card_zones.get(f"hand_{suffix}") if state.card_zones else None
    if not hand:
        return 0.0
    suits_held = set(c.suit for c in hand.cards)
    return (4 - len(suits_held)) / 4.0


WIZARD_FEATURES = [
    FeatureSpec("trump_count", "Trump-suited cards in hand", _wizard_trump_count),
    FeatureSpec("high_cards", "High cards (Q, K, A) in hand", _wizard_high_cards),
    FeatureSpec("bid_match", "How well bid matches hand strength", _wizard_bid_match),
    FeatureSpec("score_lead", "Cumulative score advantage", _wizard_score_lead),
    FeatureSpec("void_suits", "Suits with no cards (can trump in)", _wizard_void_suits),
]


# ============================================================
# Scrabble features
# ============================================================

def _scrabble_score_lead(state: GameState, player: str) -> float:
    suffix = "p1" if player == "player1" else "p2"
    opp = "p2" if player == "player1" else "p1"
    return (state.state_vars.get(f"{suffix}_score", 0) - state.state_vars.get(f"{opp}_score", 0)) / 50.0


def _scrabble_rack_value(state: GameState, player: str) -> float:
    suffix = "p1" if player == "player1" else "p2"
    rack = state.state_vars.get(f"rack_{suffix}", [])
    return sum(t.get('value', 0) for t in rack) / 20.0


def _scrabble_rack_vowels(state: GameState, player: str) -> float:
    """Vowel/consonant balance — closer to 0.4 vowels is ideal."""
    suffix = "p1" if player == "player1" else "p2"
    rack = state.state_vars.get(f"rack_{suffix}", [])
    if not rack:
        return 0.0
    vowels = sum(1 for t in rack if t.get('letter', '') in 'AEIOU')
    ratio = vowels / len(rack)
    return -abs(ratio - 0.4)  # penalty for imbalance


def _scrabble_tiles_remaining(state: GameState, player: str) -> float:
    bag = state.state_vars.get("bag", [])
    return len(bag) / 70.0


SCRABBLE_FEATURES = [
    FeatureSpec("score_lead", "Score advantage over opponent", _scrabble_score_lead),
    FeatureSpec("rack_value", "Total point value of tiles in rack", _scrabble_rack_value),
    FeatureSpec("rack_vowels", "Vowel/consonant balance in rack", _scrabble_rack_vowels),
    FeatureSpec("tiles_remaining", "Tiles left in bag", _scrabble_tiles_remaining),
]


FEATURE_REGISTRY: dict[str, list[FeatureSpec]] = {
    "Tic-Tac-Toe": TTT_FEATURES,
    "Connect Four": C4_FEATURES,
    "Mancala (Kalah)": MANCALA_FEATURES,
    "Reversi": REVERSI_FEATURES,
    "Nim": NIM_FEATURES,
    "Go Fish": GOFISH_FEATURES,
    "Checkers": CHECKERS_FEATURES,
    "Hex": HEX_FEATURES,
    "Backgammon": BACKGAMMON_FEATURES,
    "Gin Rummy": GIN_RUMMY_FEATURES,
    "Five-Card Draw": POKER_FEATURES,
    "Wizard": WIZARD_FEATURES,
    "Simplified Scrabble": SCRABBLE_FEATURES,
}


def get_features(game_name: str) -> list[FeatureSpec]:
    """Get features for a game by name. Returns empty list if unknown."""
    return FEATURE_REGISTRY.get(game_name, [])
