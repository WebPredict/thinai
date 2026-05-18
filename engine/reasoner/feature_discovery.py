"""Auto-feature discovery for ThinAI.

Two-level system that discovers useful evaluation features automatically:

Level 1 (Rule-structure analysis):
  Reads the GDL JSON and infers features from structural patterns --
  board type, zone names, end conditions, piece types, etc.

Level 2 (Correlation discovery):
  After training games, measures ~20 generic state properties and
  checks which ones correlate with winning. Features with significant
  correlation are promoted to the feature set.

This is exploratory / prototype code -- not yet wired into the engine.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Callable, Optional

from engine.gdl.state import GameState, Piece
from engine.gdl.board import GridBoard, GridSpace, TrackBoard, TrackSpace
from engine.reasoner.features import FeatureSpec


# ============================================================
# Level 1: Rule-structure analysis
# ============================================================

def discover_features_from_rules(gdl: dict) -> list[FeatureSpec]:
    """Analyze a GDL spec and infer features from its structure.

    Examines board type, zones, piece definitions, end conditions,
    and rule effects to decide which features are relevant.
    """
    features: list[FeatureSpec] = []
    board_spec = gdl.get("board", {})
    board_type = board_spec.get("type", "")
    pieces = gdl.get("pieces", [])
    rules = gdl.get("rules", [])
    end_conditions = gdl.get("end_conditions", [])
    setup = gdl.get("setup", [])
    comments = gdl.get("_comments", {})

    # Flatten all text from rules/conditions/effects/comments for keyword search
    all_text = _flatten_gdl_text(gdl)

    # --- Track board patterns ---
    if board_type == "track":
        track_len = board_spec.get("track", {}).get("length", 0)

        # Bear-off / goal zone detection
        if _has_pattern(all_text, r"bear.?off|goal|finish|home"):
            features.append(_make_relative_feature(
                "distance_to_goal",
                "Total distance of pieces from the goal (like pip count)",
                _distance_to_goal,
            ))

        # Bar/jail for hitting games
        if _has_pattern(all_text, r"bar|jail|hit|captured.*single"):
            features.append(_make_relative_feature(
                "exposed_singles",
                "Single pieces vulnerable to being hit (blots)",
                _exposed_singles,
            ))
            features.append(FeatureSpec(
                "bar_penalty",
                "Pieces stuck on bar/jail (relative: my penalty minus opponent's)",
                _bar_penalty_relative,
            ))

    # --- Grid board patterns ---
    if board_type == "grid":
        rows = board_spec.get("grid", {}).get("rows", 0)
        cols = board_spec.get("grid", {}).get("cols", 0)

    # --- Deck / dealing (card or card-like zones) ---
    if board_type == "card_zones":
        zones = board_spec.get("zones", [])
        has_deck = any(z.get("name") in ("deck", "pond", "draw_pile", "stock")
                       for z in zones)
        has_deal = any(a.get("action") == "deal" for a in setup)
        if has_deck or has_deal:
            features.append(FeatureSpec(
                "hand_size_advantage",
                "My hand size minus opponent's hand size",
                _hand_size_advantage,
            ))

    # --- End condition: score-based ---
    for ec in end_conditions:
        cond_text = str(ec.get("condition", "")) + str(ec.get("score", ""))
        if "score" in cond_text or "count_sets" in cond_text or "player_by_score" in ec.get("player", ""):
            features.append(FeatureSpec(
                "score_lead",
                "Score advantage over opponent (relative)",
                _score_lead,
            ))
            break

    # --- End condition: line-length based ---
    ec_text = " ".join(str(ec.get("condition", "")) for ec in end_conditions)
    if "line_length" in ec_text:
        features.append(FeatureSpec(
            "line_threats",
            "Spaces adjacent to my lines minus opponent's (relative)",
            _line_threats_relative,
        ))

    # --- End condition: hex connection ---
    if "hex_connected" in ec_text:
        features.append(FeatureSpec(
            "connection_progress",
            "How close to connecting my two sides (relative: mine minus opponent's)",
            _connection_progress_relative,
        ))

    # --- Promotion / kinging ---
    piece_names = [p.get("name", "") for p in pieces]
    if "king" in piece_names or _has_pattern(all_text, r"promot|king"):
        features.append(FeatureSpec(
            "promoted_pieces",
            "My promoted/kinged pieces minus opponent's",
            _promoted_pieces_relative,
        ))

    # --- Universal: piece advantage (always useful for capture games) ---
    if _has_pattern(all_text, r"captur|remov|jump|hit"):
        features.append(FeatureSpec(
            "piece_advantage",
            "My piece count minus opponent's, normalized",
            _piece_advantage,
        ))

    # --- Universal: center control (grid games) ---
    if board_type == "grid":
        features.append(FeatureSpec(
            "center_control",
            "How central my pieces are vs opponent's",
            _center_control_relative,
        ))

    return features


# ============================================================
# Level 2: Correlation discovery
# ============================================================

# Candidate measurement functions -- generic, work on any game.
# Each returns (name, description, function).

def _define_candidates() -> list[tuple[str, str, Callable[[GameState, str], float]]]:
    """Define ~20 candidate measurement functions for correlation analysis."""
    candidates = []

    # --- Piece-count candidates ---
    candidates.append((
        "total_my_pieces",
        "Total count of my pieces on the board",
        lambda s, p: sum(1 for _, pc in s.all_pieces() if pc.owner == p),
    ))
    candidates.append((
        "total_opp_pieces",
        "Total count of opponent's pieces",
        lambda s, p: sum(1 for _, pc in s.all_pieces() if pc.owner != p and pc.owner is not None),
    ))
    candidates.append((
        "piece_ratio",
        "Ratio of my pieces to total owned pieces",
        lambda s, p: _safe_ratio(
            sum(1 for _, pc in s.all_pieces() if pc.owner == p),
            sum(1 for _, pc in s.all_pieces() if pc.owner is not None),
        ),
    ))

    # --- Grid-specific candidates ---
    candidates.append((
        "center_distance_avg",
        "Average distance of my pieces from board center",
        _cand_center_distance,
    ))
    candidates.append((
        "edge_piece_count",
        "Number of my pieces on board edges",
        _cand_edge_pieces,
    ))
    candidates.append((
        "corner_piece_count",
        "Number of my pieces in corners",
        _cand_corner_pieces,
    ))
    candidates.append((
        "adjacency_count",
        "Number of my pieces adjacent to other my pieces",
        _cand_adjacency,
    ))
    candidates.append((
        "spread_variance",
        "How spread out my pieces are",
        _cand_spread,
    ))

    # --- Track-specific candidates ---
    candidates.append((
        "avg_position",
        "Average position index of my pieces on track",
        _cand_avg_position,
    ))
    candidates.append((
        "max_position",
        "Maximum (furthest) position of my pieces",
        _cand_max_position,
    ))
    candidates.append((
        "singles_count",
        "Number of spaces with exactly one of my pieces",
        _cand_singles,
    ))
    candidates.append((
        "stacks_count",
        "Number of spaces with 2+ of my pieces",
        _cand_stacks,
    ))
    candidates.append((
        "zone_front_half",
        "Pieces in the first half of the track",
        _cand_zone_front,
    ))
    candidates.append((
        "zone_back_half",
        "Pieces in the second half of the track",
        _cand_zone_back,
    ))

    # --- Card-game candidates ---
    candidates.append((
        "hand_size",
        "Number of cards in my hand",
        _cand_hand_size,
    ))
    candidates.append((
        "score_zone_size",
        "Cards in my score/sets zone",
        _cand_score_zone,
    ))

    # --- State variable candidates ---
    candidates.append((
        "turn_number",
        "Current turn number (game progress)",
        lambda s, p: float(s.turn_number),
    ))

    # --- Board coverage ---
    candidates.append((
        "board_occupancy",
        "Fraction of board spaces occupied",
        _cand_board_occupancy,
    ))
    candidates.append((
        "empty_neighbors",
        "Empty spaces adjacent to my pieces",
        _cand_empty_neighbors,
    ))
    candidates.append((
        "territory",
        "Spaces where I have more influence than opponent",
        _cand_territory,
    ))

    return candidates


def discover_features_from_play(
    engine,
    game_traces: list[dict],
    min_correlation: float = 0.15,
) -> list[FeatureSpec]:
    """Discover features by correlating measurements with game outcomes.

    Args:
        engine: Not used directly; reserved for future use.
        game_traces: List of {"states": [GameState, ...], "outcome": float}.
                     outcome > 0 means player1 won, < 0 means player1 lost,
                     0 means draw.
        min_correlation: Minimum |correlation| to include a feature.

    Returns:
        List of FeatureSpec objects for measurements that correlate with winning.
    """
    candidates = _define_candidates()

    if not game_traces:
        return []

    results: list[tuple[str, str, Callable, float]] = []

    for name, desc, func in candidates:
        # Collect (measurement_value, outcome) pairs across all traces
        values_win: list[float] = []
        values_lose: list[float] = []

        for trace in game_traces:
            states = trace.get("states", [])
            outcome = trace.get("outcome", 0.0)
            if not states or outcome == 0.0:
                continue

            player = "player1"  # We measure from player1's perspective
            # Sample states evenly (skip initial setup state, skip terminal)
            sample_indices = _sample_indices(len(states), max_samples=10)

            for idx in sample_indices:
                state = states[idx]
                try:
                    val = func(state, player)
                except Exception:
                    continue

                if outcome > 0:
                    values_win.append(val)
                else:
                    values_lose.append(val)

        # Compute correlation: is the mean higher in wins than losses?
        if len(values_win) < 3 or len(values_lose) < 3:
            continue

        mean_win = sum(values_win) / len(values_win)
        mean_lose = sum(values_lose) / len(values_lose)

        # Point-biserial-like correlation
        all_vals = values_win + values_lose
        grand_mean = sum(all_vals) / len(all_vals)
        variance = sum((v - grand_mean) ** 2 for v in all_vals) / len(all_vals)
        std = math.sqrt(variance) if variance > 0 else 0.0

        if std < 1e-9:
            continue

        # Effect size: standardized mean difference
        correlation = (mean_win - mean_lose) / std

        if abs(correlation) >= min_correlation:
            results.append((name, desc, func, correlation))

    # Sort by absolute correlation (strongest first)
    results.sort(key=lambda x: abs(x[3]), reverse=True)

    # Build FeatureSpec objects
    features = []
    for name, desc, func, corr in results:
        direction = "higher in wins" if corr > 0 else "lower in wins"
        sign = 1.0 if corr > 0 else -1.0
        # Wrap the function to flip sign if negatively correlated
        extract_fn = _make_signed_extractor(func, sign)
        features.append(FeatureSpec(
            name=name,
            description=f"{desc} (corr={corr:.3f}, {direction})",
            extract=extract_fn,
        ))

    return features


# ============================================================
# Helper: pattern detection in GDL text
# ============================================================

def _flatten_gdl_text(gdl: dict) -> str:
    """Recursively flatten all string values in a GDL dict into one text blob."""
    parts = []

    def _walk(obj):
        if isinstance(obj, str):
            parts.append(obj.lower())
        elif isinstance(obj, dict):
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    _walk(gdl)
    return " ".join(parts)


def _has_pattern(text: str, pattern: str) -> bool:
    """Check if a regex pattern matches anywhere in the text."""
    return bool(re.search(pattern, text, re.IGNORECASE))


# ============================================================
# Level 1 feature extractors
# ============================================================

def _distance_to_goal(state: GameState, player: str) -> float:
    """Total distance of pieces from goal zone, normalized."""
    if not isinstance(state.board, TrackBoard):
        return 0.0
    is_p1 = player == "player1"
    total = 0
    count = 0
    for i in range(state.board.length):
        pieces = state.get_pieces(TrackSpace(i))
        mine = sum(1 for p in pieces if p.owner == player)
        if mine > 0:
            # P1 moves toward index 0, P2 moves toward max index
            # (backgammon-style: lower = closer to bear-off for P1)
            dist = i + 1 if is_p1 else state.board.length - i
            total += mine * dist
            count += mine
    # Check bar/jail spaces (high indices beyond the board)
    for extra in range(24, state.board.length):
        pieces = state.get_pieces(TrackSpace(extra))
        mine = sum(1 for p in pieces if p.owner == player)
        if mine > 0:
            total += mine * 25
            count += mine
    return total / max(count * state.board.length, 1)


def _exposed_singles(state: GameState, player: str) -> float:
    """Count spaces with exactly one of player's pieces (blots)."""
    if not isinstance(state.board, TrackBoard):
        return 0.0
    blots = 0
    # Only count on the main playing area (first 24 for backgammon)
    main_length = min(state.board.length, 24)
    for i in range(main_length):
        pieces = state.get_pieces(TrackSpace(i))
        mine = sum(1 for p in pieces if p.owner == player)
        if mine == 1:
            blots += 1
    return blots / 15.0


def _bar_penalty_relative(state: GameState, player: str) -> float:
    """Pieces on bar: my penalty minus opponent's (negative = bad for me)."""
    if not isinstance(state.board, TrackBoard):
        return 0.0
    opponent = state.opponent(player)
    # Bar spaces are typically at indices 24, 25 for backgammon
    my_bar = 0
    opp_bar = 0
    for i in range(24, min(state.board.length, 28)):
        pieces = state.get_pieces(TrackSpace(i))
        my_bar += sum(1 for p in pieces if p.owner == player)
        opp_bar += sum(1 for p in pieces if p.owner == opponent)
    return (opp_bar - my_bar) / 15.0


def _score_lead(state: GameState, player: str) -> float:
    """Score advantage, checking state_vars and card zones."""
    opponent = state.opponent(player)
    # Try score state vars
    my_score = state.state_vars.get(f"score_{player}", 0)
    opp_score = state.state_vars.get(f"score_{opponent}", 0)
    if isinstance(my_score, (int, float)) and (my_score != 0 or opp_score != 0):
        return (my_score - opp_score) / max(abs(my_score) + abs(opp_score), 1)

    # Try card zones (sets/score zones)
    if state.card_zones:
        my_suffix = "p1" if player == "player1" else "p2"
        opp_suffix = "p2" if player == "player1" else "p1"
        my_total = 0
        opp_total = 0
        for name, zone in state.card_zones.items():
            if any(kw in name for kw in ("sets", "score", "won")):
                if my_suffix in name:
                    my_total = zone.size
                elif opp_suffix in name:
                    opp_total = zone.size
        if my_total > 0 or opp_total > 0:
            return (my_total - opp_total) / max(my_total + opp_total, 1)

    return 0.0


def _line_threats_relative(state: GameState, player: str) -> float:
    """Empty spaces adjacent to my lines minus opponent's."""
    if not isinstance(state.board, GridBoard):
        return 0.0
    opponent = state.opponent(player)
    my_threats = set()
    opp_threats = set()
    for space in state.board.spaces:
        if not state.is_empty(space):
            continue
        for n in state.board.neighbors(space):
            piece = state.get_piece(n)
            if piece is None:
                continue
            if piece.owner == player:
                my_threats.add(space)
            elif piece.owner == opponent:
                opp_threats.add(space)
    total_empty = max(sum(1 for s in state.board.spaces if state.is_empty(s)), 1)
    return (len(my_threats) - len(opp_threats)) / total_empty


def _connection_progress(state: GameState, player: str) -> float:
    """How close player is to connecting their two sides (BFS-based)."""
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


def _connection_progress_relative(state: GameState, player: str) -> float:
    """My connection progress minus opponent's."""
    opponent = state.opponent(player)
    return _connection_progress(state, player) - _connection_progress(state, opponent)


def _promoted_pieces_relative(state: GameState, player: str) -> float:
    """My promoted/kinged pieces minus opponent's."""
    opponent = state.opponent(player)
    promoted_names = {"king", "queen", "promoted"}
    my_promoted = sum(1 for _, p in state.all_pieces()
                      if p.owner == player and p.name in promoted_names)
    opp_promoted = sum(1 for _, p in state.all_pieces()
                       if p.owner == opponent and p.name in promoted_names)
    return (my_promoted - opp_promoted) / 6.0


def _piece_advantage(state: GameState, player: str) -> float:
    """My piece count minus opponent's, normalized."""
    opponent = state.opponent(player)
    my_count = sum(1 for _, p in state.all_pieces() if p.owner == player)
    opp_count = sum(1 for _, p in state.all_pieces() if p.owner == opponent)
    total = max(my_count + opp_count, 1)
    return (my_count - opp_count) / total


def _center_control_relative(state: GameState, player: str) -> float:
    """How central my pieces are vs opponent's."""
    if not isinstance(state.board, GridBoard):
        return 0.0
    board = state.board
    opponent = state.opponent(player)
    cx, cy = board.cols / 2, board.rows / 2
    max_dist = max((cx ** 2 + cy ** 2) ** 0.5, 1)
    my_score = 0.0
    opp_score = 0.0
    my_count = 0
    opp_count = 0
    for space, piece in state.all_pieces():
        centrality = 1.0 - (((space.col - cx) ** 2 + (space.row - cy) ** 2) ** 0.5) / max_dist
        if piece.owner == player:
            my_score += centrality
            my_count += 1
        elif piece.owner == opponent:
            opp_score += centrality
            opp_count += 1
    my_avg = my_score / max(my_count, 1)
    opp_avg = opp_score / max(opp_count, 1)
    return my_avg - opp_avg


def _hand_size_advantage(state: GameState, player: str) -> float:
    """My hand size minus opponent's."""
    if not state.card_zones:
        return 0.0
    my_suffix = "p1" if player == "player1" else "p2"
    opp_suffix = "p2" if player == "player1" else "p1"
    my_hand = state.get_zone(f"hand_{my_suffix}")
    opp_hand = state.get_zone(f"hand_{opp_suffix}")
    my_size = my_hand.size if my_hand else 0
    opp_size = opp_hand.size if opp_hand else 0
    return (my_size - opp_size) / 15.0


def _make_relative_feature(
    name: str, desc: str, func: Callable[[GameState, str], float]
) -> FeatureSpec:
    """Create a relative feature (my value minus opponent's)."""
    def _relative(state: GameState, player: str) -> float:
        my_val = func(state, player)
        opp_val = func(state, state.opponent(player))
        return my_val - opp_val
    return FeatureSpec(
        name=name,
        description=f"{desc} (relative: mine minus opponent's)",
        extract=_relative,
    )


# ============================================================
# Level 2 candidate measurement functions
# ============================================================

def _safe_ratio(num: float, denom: float) -> float:
    return num / denom if denom > 0 else 0.0


def _cand_center_distance(state: GameState, player: str) -> float:
    if not isinstance(state.board, GridBoard):
        return 0.0
    board = state.board
    cx, cy = board.cols / 2, board.rows / 2
    total = 0.0
    count = 0
    for space, piece in state.all_pieces():
        if piece.owner == player:
            total += abs(space.col - cx) + abs(space.row - cy)
            count += 1
    if count == 0:
        return 0.0
    max_dist = cx + cy
    return (total / count) / max(max_dist, 1)


def _cand_edge_pieces(state: GameState, player: str) -> float:
    if not isinstance(state.board, GridBoard):
        return 0.0
    board = state.board
    count = 0
    for space, piece in state.all_pieces():
        if piece.owner == player:
            if space.row == 0 or space.row == board.rows - 1 or \
               space.col == 0 or space.col == board.cols - 1:
                count += 1
    return float(count)


def _cand_corner_pieces(state: GameState, player: str) -> float:
    if not isinstance(state.board, GridBoard):
        return 0.0
    board = state.board
    corners = {
        GridSpace(0, 0), GridSpace(0, board.cols - 1),
        GridSpace(board.rows - 1, 0), GridSpace(board.rows - 1, board.cols - 1),
    }
    count = 0
    for space, piece in state.all_pieces():
        if piece.owner == player and space in corners:
            count += 1
    return float(count)


def _cand_adjacency(state: GameState, player: str) -> float:
    if not isinstance(state.board, GridBoard):
        return 0.0
    count = 0
    for space, piece in state.all_pieces():
        if piece.owner == player:
            for n in state.board.neighbors(space):
                np = state.get_piece(n)
                if np and np.owner == player:
                    count += 1
                    break
    return float(count)


def _cand_spread(state: GameState, player: str) -> float:
    if not isinstance(state.board, GridBoard):
        return 0.0
    positions = [(s.row, s.col) for s, p in state.all_pieces() if p.owner == player]
    if len(positions) < 2:
        return 0.0
    avg_r = sum(r for r, c in positions) / len(positions)
    avg_c = sum(c for r, c in positions) / len(positions)
    variance = sum((r - avg_r) ** 2 + (c - avg_c) ** 2 for r, c in positions) / len(positions)
    return variance


def _cand_avg_position(state: GameState, player: str) -> float:
    if not isinstance(state.board, TrackBoard):
        return 0.0
    total = 0.0
    count = 0
    for i in range(state.board.length):
        pieces = state.get_pieces(TrackSpace(i))
        mine = sum(1 for p in pieces if p.owner == player)
        if mine > 0:
            total += i * mine
            count += mine
    return total / max(count, 1)


def _cand_max_position(state: GameState, player: str) -> float:
    if not isinstance(state.board, TrackBoard):
        return 0.0
    best = -1
    for i in range(state.board.length):
        pieces = state.get_pieces(TrackSpace(i))
        if any(p.owner == player for p in pieces):
            best = i
    return float(max(best, 0))


def _cand_singles(state: GameState, player: str) -> float:
    if not isinstance(state.board, TrackBoard):
        return 0.0
    count = 0
    for i in range(state.board.length):
        pieces = state.get_pieces(TrackSpace(i))
        mine = sum(1 for p in pieces if p.owner == player)
        if mine == 1:
            count += 1
    return float(count)


def _cand_stacks(state: GameState, player: str) -> float:
    if not isinstance(state.board, TrackBoard):
        return 0.0
    count = 0
    for i in range(state.board.length):
        pieces = state.get_pieces(TrackSpace(i))
        mine = sum(1 for p in pieces if p.owner == player)
        if mine >= 2:
            count += 1
    return float(count)


def _cand_zone_front(state: GameState, player: str) -> float:
    if not isinstance(state.board, TrackBoard):
        return 0.0
    half = state.board.length // 2
    count = 0
    for i in range(half):
        pieces = state.get_pieces(TrackSpace(i))
        count += sum(1 for p in pieces if p.owner == player)
    return float(count)


def _cand_zone_back(state: GameState, player: str) -> float:
    if not isinstance(state.board, TrackBoard):
        return 0.0
    half = state.board.length // 2
    count = 0
    for i in range(half, state.board.length):
        pieces = state.get_pieces(TrackSpace(i))
        count += sum(1 for p in pieces if p.owner == player)
    return float(count)


def _cand_hand_size(state: GameState, player: str) -> float:
    if not state.card_zones:
        return 0.0
    suffix = "p1" if player == "player1" else "p2"
    hand = state.get_zone(f"hand_{suffix}")
    return float(hand.size) if hand else 0.0


def _cand_score_zone(state: GameState, player: str) -> float:
    if not state.card_zones:
        return 0.0
    suffix = "p1" if player == "player1" else "p2"
    for name, zone in state.card_zones.items():
        if any(kw in name for kw in ("sets", "score", "won")) and suffix in name:
            return float(zone.size)
    return 0.0


def _cand_board_occupancy(state: GameState, player: str) -> float:
    total_pieces = len(state.all_pieces())
    if isinstance(state.board, GridBoard):
        total_spaces = state.board.rows * state.board.cols
    elif isinstance(state.board, TrackBoard):
        total_spaces = state.board.length
    else:
        return 0.0
    return total_pieces / max(total_spaces, 1)


def _cand_empty_neighbors(state: GameState, player: str) -> float:
    if not isinstance(state.board, GridBoard):
        return 0.0
    empty_near_me = set()
    for space, piece in state.all_pieces():
        if piece.owner == player:
            for n in state.board.neighbors(space):
                if state.is_empty(n):
                    empty_near_me.add(n)
    return float(len(empty_near_me))


def _cand_territory(state: GameState, player: str) -> float:
    """Count spaces where player has more adjacent pieces than opponent."""
    if not isinstance(state.board, GridBoard):
        return 0.0
    opponent = state.opponent(player)
    territory = 0
    for space in state.board.spaces:
        if not state.is_empty(space):
            continue
        my_adj = 0
        opp_adj = 0
        for n in state.board.neighbors(space):
            piece = state.get_piece(n)
            if piece:
                if piece.owner == player:
                    my_adj += 1
                elif piece.owner == opponent:
                    opp_adj += 1
        if my_adj > opp_adj:
            territory += 1
    return float(territory)


# ============================================================
# Level 2 helpers
# ============================================================

def _sample_indices(n: int, max_samples: int = 10) -> list[int]:
    """Pick evenly-spaced indices from [1, n-1) (skip first and last)."""
    if n <= 2:
        return []
    usable = n - 2  # skip index 0 (setup) and n-1 (terminal)
    if usable <= max_samples:
        return list(range(1, n - 1))
    step = usable / max_samples
    return [int(1 + i * step) for i in range(max_samples)]


def _make_signed_extractor(
    func: Callable[[GameState, str], float], sign: float
) -> Callable[[GameState, str], float]:
    """Wrap a function to flip its sign if negatively correlated."""
    if sign >= 0:
        return func

    def _flipped(state: GameState, player: str) -> float:
        return -func(state, player)
    return _flipped


# ============================================================
# Test harness
# ============================================================

def _print_features(label: str, features: list[FeatureSpec]):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    if not features:
        print("  (no features discovered)")
    for i, f in enumerate(features, 1):
        print(f"  {i}. {f.name}")
        print(f"     {f.description}")
    print()


def _test_level1():
    """Test Level 1: discover features from rule structure."""
    examples_dir = Path(__file__).parent.parent / "games" / "examples"

    # --- Backgammon ---
    bg_path = examples_dir / "backgammon.json"
    if bg_path.exists():
        with open(bg_path) as f:
            bg_gdl = json.load(f)
        bg_features = discover_features_from_rules(bg_gdl)
        _print_features("Backgammon -- discovered features", bg_features)

        # Verify expected features
        names = {f.name for f in bg_features}
        expected = {"distance_to_goal", "exposed_singles", "bar_penalty"}
        found = expected & names
        missing = expected - names
        print(f"  Expected: {expected}")
        print(f"  Found:    {found}")
        if missing:
            print(f"  MISSING:  {missing}")
        else:
            print("  All expected backgammon features discovered.")
    else:
        print(f"  Backgammon GDL not found at {bg_path}")

    # --- Hex ---
    hex_path = examples_dir / "hex.json"
    if hex_path.exists():
        with open(hex_path) as f:
            hex_gdl = json.load(f)
        hex_features = discover_features_from_rules(hex_gdl)
        _print_features("Hex -- discovered features", hex_features)

        names = {f.name for f in hex_features}
        expected = {"connection_progress", "center_control"}
        found = expected & names
        missing = expected - names
        print(f"  Expected: {expected}")
        print(f"  Found:    {found}")
        if missing:
            print(f"  MISSING:  {missing}")
        else:
            print("  All expected hex features discovered.")
    else:
        print(f"  Hex GDL not found at {hex_path}")

    # --- Checkers ---
    ck_path = examples_dir / "checkers.json"
    if ck_path.exists():
        with open(ck_path) as f:
            ck_gdl = json.load(f)
        ck_features = discover_features_from_rules(ck_gdl)
        _print_features("Checkers -- discovered features", ck_features)

        names = {f.name for f in ck_features}
        expected = {"promoted_pieces", "piece_advantage", "center_control"}
        found = expected & names
        missing = expected - names
        print(f"  Expected: {expected}")
        print(f"  Found:    {found}")
        if missing:
            print(f"  MISSING:  {missing}")
        else:
            print("  All expected checkers features discovered.")
    else:
        print(f"  Checkers GDL not found at {ck_path}")

    # --- Connect Four ---
    c4_path = examples_dir / "connect_four.json"
    if c4_path.exists():
        with open(c4_path) as f:
            c4_gdl = json.load(f)
        c4_features = discover_features_from_rules(c4_gdl)
        _print_features("Connect Four -- discovered features", c4_features)

        names = {f.name for f in c4_features}
        expected = {"line_threats", "center_control"}
        found = expected & names
        missing = expected - names
        print(f"  Expected: {expected}")
        print(f"  Found:    {found}")
        if missing:
            print(f"  MISSING:  {missing}")
        else:
            print("  All expected connect four features discovered.")

    # --- Go Fish (card game) ---
    gf_path = examples_dir / "go_fish.json"
    if gf_path.exists():
        with open(gf_path) as f:
            gf_gdl = json.load(f)
        gf_features = discover_features_from_rules(gf_gdl)
        _print_features("Go Fish -- discovered features", gf_features)

        names = {f.name for f in gf_features}
        expected = {"hand_size_advantage", "score_lead"}
        found = expected & names
        missing = expected - names
        print(f"  Expected: {expected}")
        print(f"  Found:    {found}")
        if missing:
            print(f"  MISSING:  {missing}")
        else:
            print("  All expected Go Fish features discovered.")


def _test_level2_synthetic():
    """Test Level 2 with synthetic game traces.

    Creates fake traces where piece_advantage correlates with winning
    to verify the correlation machinery works.
    """
    from engine.gdl.board import GridBoard

    print(f"\n{'='*60}")
    print("  Level 2: Correlation discovery (synthetic data)")
    print(f"{'='*60}")

    board = GridBoard(rows=3, cols=3, topology="rect8")
    traces = []

    # Generate winning traces: player1 has more pieces
    for _ in range(20):
        state = GameState(board)
        state.set_piece(GridSpace(0, 0), Piece("stone", "player1"))
        state.set_piece(GridSpace(1, 1), Piece("stone", "player1"))
        state.set_piece(GridSpace(2, 2), Piece("stone", "player1"))
        state.set_piece(GridSpace(0, 2), Piece("stone", "player2"))
        state.turn_number = 5
        traces.append({"states": [state, state, state], "outcome": 1.0})

    # Generate losing traces: player1 has fewer pieces
    for _ in range(20):
        state = GameState(board)
        state.set_piece(GridSpace(0, 0), Piece("stone", "player2"))
        state.set_piece(GridSpace(1, 1), Piece("stone", "player2"))
        state.set_piece(GridSpace(2, 2), Piece("stone", "player2"))
        state.set_piece(GridSpace(0, 2), Piece("stone", "player1"))
        state.turn_number = 5
        traces.append({"states": [state, state, state], "outcome": -1.0})

    features = discover_features_from_play(engine=None, game_traces=traces)
    _print_features("Synthetic 3x3 grid -- correlated features", features)

    # Verify piece_ratio or total_my_pieces shows up
    names = {f.name for f in features}
    piece_features = names & {"piece_ratio", "total_my_pieces", "total_opp_pieces"}
    if piece_features:
        print(f"  Piece-count features correctly discovered: {piece_features}")
    else:
        print("  WARNING: No piece-count features found in synthetic test")


if __name__ == "__main__":
    _test_level1()
    _test_level2_synthetic()
