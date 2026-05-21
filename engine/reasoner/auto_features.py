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
from engine.gdl.board import GridBoard, GridSpace, TrackBoard, TrackSpace, CardBoard
from engine.reasoner.features import FeatureSpec


def generate_features(gdl: dict) -> list[FeatureSpec]:
    """Analyze a GDL spec and generate appropriate features.

    Returns a list of FeatureSpecs derived from the game's structure.
    These are universal — they work without knowing what the game is.
    """
    features = []
    board_spec = gdl.get("board", {})
    board_type = board_spec.get("type", "")

    # Detect game characteristics for smarter feature selection
    end_conditions = gdl.get("end_conditions", [])
    rules = gdl.get("rules", [])
    rules_text = str(rules)
    has_line_win = any("line_length" in str(ec.get("condition", ""))
                       for ec in end_conditions)
    has_capture = any(w in rules_text for w in ["capture", "remove", "jump", "flank"])
    is_placement = any(r.get("name") in ("place", "place_piece") for r in rules)

    # === Universal features (board games only — not card games) ===

    if board_type != "card_zones":
        # Piece advantage is only useful in capture games
        if has_capture:
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
        features.append(FeatureSpec(
            "center_control",
            "How many of my pieces are near the center",
            _center_control,
        ))

        # Edge/corner/spread are useful for territory games but noise for line games
        if not has_line_win:
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

        # Territory/area control: count pieces win condition
        ec_text = str(end_conditions)
        if any(w in ec_text for w in ["count_pieces", "territory", "majority"]):
            features.append(FeatureSpec(
                "territory_control",
                "How many spaces I control vs opponent",
                _piece_advantage,  # reuse piece_advantage as territory proxy
            ))

        # Line-based win conditions: add line features
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

        features.append(FeatureSpec(
            "position_lead",
            "Average position of my pieces vs opponent's",
            _position_lead_track,
        ))

    # === Card game features ===

    if board_type == "card_zones":
        zones = board_spec.get("zones", [])

        # Find hand zones (visible_to: "owner")
        hand_zones = [z for z in zones if z.get("visible_to") == "owner"]
        if hand_zones:
            features.append(FeatureSpec(
                "hand_size",
                "Cards in my hand (more options = better)",
                _card_hand_size,
            ))

            features.append(FeatureSpec(
                "hand_size_advantage",
                "My hand size minus opponent's",
                _card_hand_size_advantage,
            ))

            features.append(FeatureSpec(
                "rank_concentration",
                "Most cards of same rank in hand (pairs/triples)",
                _card_rank_concentration,
            ))

            features.append(FeatureSpec(
                "near_complete_sets",
                "Ranks where I hold 3+ cards (one away from a set)",
                _card_near_complete_sets,
            ))

            features.append(FeatureSpec(
                "pairs_held",
                "Number of ranks with 2+ cards (good ask targets)",
                _card_pairs_held,
            ))

        # Find score/set zones (visible_to: "all" with owner)
        score_zones = [z for z in zones if z.get("visible_to") == "all" and z.get("owner")]
        if len(score_zones) >= 2:
            features.append(FeatureSpec(
                "score_lead",
                "My score zone size minus opponent's",
                _card_score_lead,
            ))

            features.append(FeatureSpec(
                "singletons",
                "Ranks with only 1 card (hard to complete)",
                _card_singletons,
            ))

        # Find draw pile zones (visible_to: "none", no owner)
        draw_zones = [z for z in zones if z.get("visible_to") == "none" and not z.get("owner")]
        if draw_zones:
            features.append(FeatureSpec(
                "draw_pile_remaining",
                "Cards left in draw pile (game progress)",
                _card_draw_pile_remaining,
            ))

        # Don't add state var features for card games — they're transient
        return features

    # === Derived from state variables (board games only) ===

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
    """My centrality minus opponent's centrality."""
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


def _edge_presence(state: GameState, player: str) -> float:
    """My edge pieces minus opponent's edge pieces."""
    if not isinstance(state.board, GridBoard):
        return 0.0
    board = state.board
    opponent = state.opponent(player)
    my_edges = 0
    opp_edges = 0
    for space, piece in state.all_pieces():
        if space.row == 0 or space.row == board.rows - 1 or \
           space.col == 0 or space.col == board.cols - 1:
            if piece.owner == player:
                my_edges += 1
            elif piece.owner == opponent:
                opp_edges += 1
    total_edge = 2 * (board.rows + board.cols) - 4
    return (my_edges - opp_edges) / max(total_edge, 1)


def _corner_presence(state: GameState, player: str) -> float:
    """My corners minus opponent's corners."""
    if not isinstance(state.board, GridBoard):
        return 0.0
    board = state.board
    opponent = state.opponent(player)
    corners = [
        GridSpace(0, 0), GridSpace(0, board.cols - 1),
        GridSpace(board.rows - 1, 0), GridSpace(board.rows - 1, board.cols - 1),
    ]
    score = 0
    for c in corners:
        piece = state.get_piece(c)
        if piece:
            if piece.owner == player:
                score += 1
            elif piece.owner == opponent:
                score -= 1
    return score / 4.0


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


def _position_lead_track(state: GameState, player: str) -> float:
    """Average position of my pieces minus opponent's, normalized by track length."""
    opponent = state.opponent(player)
    my_total, my_count = 0, 0
    opp_total, opp_count = 0, 0
    for space in state.board.spaces:
        for piece in state.get_pieces(space):
            if piece.owner == player:
                my_total += space.index
                my_count += 1
            elif piece.owner == opponent:
                opp_total += space.index
                opp_count += 1
    my_avg = my_total / max(my_count, 1)
    opp_avg = opp_total / max(opp_count, 1)
    return (my_avg - opp_avg) / max(state.board.length, 1)


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


# === Card game feature implementations ===

def _get_my_hand(state: GameState, player: str):
    """Get the hand zone for a player."""
    if not state.card_zones:
        return None
    suffix = "p1" if player == "player1" else "p2"
    return state.get_zone(f"hand_{suffix}")


def _get_opp_hand(state: GameState, player: str):
    """Get the opponent's hand zone."""
    if not state.card_zones:
        return None
    suffix = "p2" if player == "player1" else "p1"
    return state.get_zone(f"hand_{suffix}")


def _card_hand_size(state: GameState, player: str) -> float:
    hand = _get_my_hand(state, player)
    return (hand.size / 15.0) if hand else 0.0


def _card_hand_size_advantage(state: GameState, player: str) -> float:
    my_hand = _get_my_hand(state, player)
    opp_hand = _get_opp_hand(state, player)
    my_size = my_hand.size if my_hand else 0
    opp_size = opp_hand.size if opp_hand else 0
    return (my_size - opp_size) / 15.0


def _card_rank_concentration(state: GameState, player: str) -> float:
    """Highest count of any single rank in hand."""
    hand = _get_my_hand(state, player)
    if not hand or hand.is_empty:
        return 0.0
    from collections import Counter
    ranks = Counter(c.rank for c in hand.cards)
    return max(ranks.values()) / 4.0


def _card_near_complete_sets(state: GameState, player: str) -> float:
    """Count of ranks with 3+ cards (one away from completing a set)."""
    hand = _get_my_hand(state, player)
    if not hand or hand.is_empty:
        return 0.0
    from collections import Counter
    ranks = Counter(c.rank for c in hand.cards)
    return sum(1 for c in ranks.values() if c >= 3) / 4.0


def _card_pairs_held(state: GameState, player: str) -> float:
    """Count of ranks with 2+ cards (good targets to ask/trade for)."""
    hand = _get_my_hand(state, player)
    if not hand or hand.is_empty:
        return 0.0
    from collections import Counter
    ranks = Counter(c.rank for c in hand.cards)
    return sum(1 for c in ranks.values() if c >= 2) / 6.0


def _card_singletons(state: GameState, player: str) -> float:
    """Ranks with only 1 card — spread thin, hard to complete sets."""
    hand = _get_my_hand(state, player)
    if not hand or hand.is_empty:
        return 0.0
    from collections import Counter
    ranks = Counter(c.rank for c in hand.cards)
    singles = sum(1 for c in ranks.values() if c == 1)
    return singles / 8.0  # normalize


def _card_score_lead(state: GameState, player: str) -> float:
    """Score zone advantage: my completed items minus opponent's."""
    if not state.card_zones:
        return 0.0
    my_suffix = "p1" if player == "player1" else "p2"
    opp_suffix = "p2" if player == "player1" else "p1"
    # Look for sets/score zones
    my_score = 0
    opp_score = 0
    for name, zone in state.card_zones.items():
        if "sets" in name or "score" in name or "won" in name:
            if my_suffix in name:
                my_score = zone.size
            elif opp_suffix in name:
                opp_score = zone.size
    return (my_score - opp_score) / 20.0


def _card_draw_pile_remaining(state: GameState, player: str) -> float:
    """Cards remaining in draw pile (game progress indicator)."""
    if not state.card_zones:
        return 0.0
    for name, zone in state.card_zones.items():
        if name in ("deck", "pond", "draw_pile", "stock"):
            return zone.size / 52.0
    return 0.0
