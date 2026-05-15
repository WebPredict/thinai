"""Auto-generated features for ThinAI.

Derives game-agnostic features from the GDL structure. These work
for ANY game without hand-crafted knowledge — the system figures
out what to pay attention to by examining the rules, board, and
end conditions.

This is how a kid approaches a new game: they don't know game-specific
strategy, but they notice universal things like "am I ahead?",
"do I have more options?", "am I close to winning?"
"""

from __future__ import annotations
from typing import Optional

from engine.gdl.state import GameState, Piece
from engine.gdl.board import GridBoard, GridSpace, TrackBoard, TrackSpace
from engine.reasoner.features import FeatureSpec


def generate_features(gdl: dict) -> list[FeatureSpec]:
    """Analyze a GDL spec and generate appropriate features.

    Returns a list of FeatureSpecs derived from the game's structure.
    These are universal — they work without knowing what the game is.
    """
    features = []
    board_spec = gdl.get("board", {})
    board_type = board_spec.get("type", "")

    # === Universal features (work for every game) ===

    features.append(FeatureSpec(
        "my_piece_count",
        "Number of my pieces on the board",
        _my_piece_count,
    ))

    features.append(FeatureSpec(
        "piece_advantage",
        "My pieces minus opponent's pieces",
        _piece_advantage,
    ))

    features.append(FeatureSpec(
        "mobility",
        "How many moves I have available",
        _mobility,
    ))

    # === Grid-specific features ===

    if board_type == "grid":
        rows = board_spec.get("grid", {}).get("rows", 0)
        cols = board_spec.get("grid", {}).get("cols", 0)

        features.append(FeatureSpec(
            "center_control",
            "How many of my pieces are near the center",
            _center_control,
        ))

        features.append(FeatureSpec(
            "edge_presence",
            "How many of my pieces are on edges",
            _edge_presence,
        ))

        features.append(FeatureSpec(
            "corner_presence",
            "How many of my pieces are in corners",
            _corner_presence,
        ))

        features.append(FeatureSpec(
            "spread",
            "How spread out my pieces are on the board",
            _spread,
        ))

        # If the game has line-based win conditions, add line features
        end_conditions = gdl.get("end_conditions", [])
        has_line_win = any("line_length" in str(ec.get("condition", ""))
                          for ec in end_conditions)
        if has_line_win:
            features.append(FeatureSpec(
                "longest_line",
                "My longest connected line of pieces",
                _longest_line,
            ))
            features.append(FeatureSpec(
                "line_threats",
                "Positions where I could extend a line",
                _line_threats,
            ))

    # === Track-specific features ===

    if board_type == "track":
        # Check for regions (mancala-style)
        if board_spec.get("regions"):
            features.append(FeatureSpec(
                "region_control",
                "Pieces in my regions vs opponent's regions",
                _region_control,
            ))

        features.append(FeatureSpec(
            "total_pieces",
            "Total pieces on the board",
            _total_pieces_track,
        ))

    # === Derived from state variables ===

    for var in gdl.get("state_vars", []):
        var_name = var["name"]
        features.append(FeatureSpec(
            f"var_{var_name}",
            f"Value of game variable '{var_name}'",
            _make_state_var_feature(var_name),
        ))

    return features


def describe_features(features: list[FeatureSpec], gdl: dict) -> list[dict]:
    """Describe the auto-generated features in human-readable form.

    Used by the UI to show 'here's what I'm paying attention to.'
    """
    board_type = gdl.get("board", {}).get("type", "unknown")
    descriptions = []
    for f in features:
        descriptions.append({
            "name": f.name,
            "description": f.description,
            "source": "auto-generated from game rules",
        })
    return descriptions


# === Feature implementations ===

def _my_piece_count(state: GameState, player: str) -> float:
    """Count of player's pieces, normalized."""
    count = sum(1 for _, p in state.all_pieces() if p.owner == player)
    total = len(state.all_pieces())
    return count / max(total, 1)


def _piece_advantage(state: GameState, player: str) -> float:
    """Difference between my pieces and opponent's, normalized."""
    opponent = state.opponent(player)
    my_count = sum(1 for _, p in state.all_pieces() if p.owner == player)
    opp_count = sum(1 for _, p in state.all_pieces() if p.owner == opponent)
    total = max(my_count + opp_count, 1)
    return (my_count - opp_count) / total


def _mobility(state: GameState, player: str) -> float:
    """Number of legal moves available, normalized.

    More options usually means a stronger position.
    """
    # We can't call engine.legal_moves without a circular import,
    # so approximate by counting empty adjacent spaces
    if isinstance(state.board, GridBoard):
        my_spaces = set()
        for space, piece in state.all_pieces():
            if piece.owner == player:
                for n in state.board.neighbors(space):
                    if state.is_empty(n):
                        my_spaces.add(n)
        total_spaces = state.board.rows * state.board.cols
        return len(my_spaces) / max(total_spaces, 1)
    return 0.5  # default for non-grid games


def _center_control(state: GameState, player: str) -> float:
    """Pieces near the center of the board."""
    if not isinstance(state.board, GridBoard):
        return 0.0
    board = state.board
    cx, cy = board.cols / 2, board.rows / 2
    max_dist = (cx ** 2 + cy ** 2) ** 0.5
    score = 0.0
    count = 0
    for space, piece in state.all_pieces():
        if piece.owner == player:
            dist = ((space.col - cx) ** 2 + (space.row - cy) ** 2) ** 0.5
            score += 1.0 - (dist / max_dist)
            count += 1
    return score / max(count, 1)


def _edge_presence(state: GameState, player: str) -> float:
    """Fraction of my pieces on board edges."""
    if not isinstance(state.board, GridBoard):
        return 0.0
    board = state.board
    edge_count = 0
    total = 0
    for space, piece in state.all_pieces():
        if piece.owner == player:
            total += 1
            if space.row == 0 or space.row == board.rows - 1 or \
               space.col == 0 or space.col == board.cols - 1:
                edge_count += 1
    return edge_count / max(total, 1)


def _corner_presence(state: GameState, player: str) -> float:
    """How many corners I occupy."""
    if not isinstance(state.board, GridBoard):
        return 0.0
    board = state.board
    corners = [
        GridSpace(0, 0), GridSpace(0, board.cols - 1),
        GridSpace(board.rows - 1, 0), GridSpace(board.rows - 1, board.cols - 1),
    ]
    count = sum(1 for c in corners
                if state.get_piece(c) and state.get_piece(c).owner == player)
    return count / 4.0


def _spread(state: GameState, player: str) -> float:
    """How spread out my pieces are (higher = more spread)."""
    if not isinstance(state.board, GridBoard):
        return 0.0
    positions = [(s.row, s.col) for s, p in state.all_pieces() if p.owner == player]
    if len(positions) < 2:
        return 0.0
    avg_r = sum(r for r, c in positions) / len(positions)
    avg_c = sum(c for r, c in positions) / len(positions)
    variance = sum((r - avg_r) ** 2 + (c - avg_c) ** 2 for r, c in positions) / len(positions)
    board = state.board
    max_var = (board.rows ** 2 + board.cols ** 2) / 4
    return variance / max(max_var, 1)


def _longest_line(state: GameState, player: str) -> float:
    """Longest connected line of my pieces in any direction."""
    if not isinstance(state.board, GridBoard):
        return 0.0
    from engine.gdl.expr_eval import _line_length
    board = state.board
    best = 0
    for space in board.spaces:
        piece = state.get_piece(space)
        if piece and piece.owner == player:
            for d in board.directions():
                length = _line_length(state, space, d, player)
                best = max(best, length)
    return best / max(board.rows, board.cols)


def _line_threats(state: GameState, player: str) -> float:
    """Empty spaces adjacent to my lines (potential extensions)."""
    if not isinstance(state.board, GridBoard):
        return 0.0
    board = state.board
    threats = set()
    for space in board.spaces:
        if not state.is_empty(space):
            continue
        for n in board.neighbors(space):
            piece = state.get_piece(n)
            if piece and piece.owner == player:
                threats.add(space)
                break
    total_empty = sum(1 for s in board.spaces if state.is_empty(s))
    return len(threats) / max(total_empty, 1)


def _region_control(state: GameState, player: str) -> float:
    """Pieces in player's regions vs opponent's (for track games with regions)."""
    if not isinstance(state.board, TrackBoard):
        return 0.0
    # Simple heuristic: first half of track = player1, second half = player2
    half = state.board.length // 2
    my_count = 0
    opp_count = 0
    for space, piece in state.all_pieces():
        if isinstance(space, TrackSpace):
            if player == "player1":
                if space.index < half:
                    my_count += state.count_pieces_at(space)
                else:
                    opp_count += state.count_pieces_at(space)
            else:
                if space.index >= half:
                    my_count += state.count_pieces_at(space)
                else:
                    opp_count += state.count_pieces_at(space)
    total = max(my_count + opp_count, 1)
    return (my_count - opp_count) / total


def _total_pieces_track(state: GameState, player: str) -> float:
    """Total pieces on track, normalized."""
    total = sum(state.count_pieces_at(s) for s in state.board.spaces)
    return total / max(state.board.length * 4, 1)


def _make_state_var_feature(var_name: str):
    """Create a feature function for a state variable."""
    def _extract(state: GameState, player: str) -> float:
        val = state.state_vars.get(var_name, 0)
        if isinstance(val, bool):
            return 1.0 if val else 0.0
        if isinstance(val, (int, float)):
            return float(val) / 10.0  # rough normalization
        return 0.0
    return _extract
