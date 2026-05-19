"""AI move commentary — explains why a move was chosen.

Generates human-readable explanations by comparing the game state
before and after the AI's move, looking at which features changed
and what patterns are visible.
"""

from __future__ import annotations
from typing import Optional

from engine.gdl.state import GameState
from engine.gdl.board import GridBoard, GridSpace


def generate_commentary(state_before: GameState, state_after: GameState,
                        move, engine, eval_fn=None, best_score=0,
                        second_score=0, depth=0) -> str:
    """Generate a brief explanation of why the AI chose this move.

    Returns a human-readable string like:
    "Blocked your 3-in-a-row threat" or "Took the center for positional advantage"
    """
    reasons = []
    player = state_before.current_player

    # 1. Check for terminal/near-terminal situations
    result_after = engine.check_terminal(state_after)
    if result_after and result_after.result_type == "win" and result_after.winner == player:
        return "Winning move!"

    if best_score >= 9000:
        return "Found a forced win"

    if best_score <= -9000:
        return "All moves lose — playing the best losing option"

    # 2. For grid games: check spatial patterns
    if isinstance(state_before.board, GridBoard):
        reasons.extend(_grid_commentary(state_before, state_after, move, player, engine))

    # 3. Feature-based commentary (if eval_fn is a LearnableEval)
    if eval_fn and hasattr(eval_fn, 'features') and hasattr(eval_fn, 'weights'):
        reasons.extend(_feature_commentary(state_before, state_after, eval_fn, player))

    # 4. Score-based commentary
    if not reasons:
        if best_score > 0 and second_score <= 0:
            reasons.append("Best available move by a clear margin")
        elif abs(best_score - second_score) < 0.5:
            reasons.append("Several equally good options — chose this one")
        elif best_score > second_score + 5:
            reasons.append("Significantly better than alternatives")

    # 5. Card game commentary
    if state_before.card_zones:
        reasons.extend(_card_commentary(state_before, state_after, move, player))

    if not reasons:
        reasons.append("Evaluated positions and picked the strongest")

    return reasons[0] if len(reasons) == 1 else " | ".join(reasons[:2])


def _grid_commentary(state_before, state_after, move, player, engine):
    """Commentary for grid-based games."""
    reasons = []
    board = state_before.board
    opponent = state_before.opponent(player)

    # Where did the AI place?
    target = move.params.get("target")
    if not target or not hasattr(target, "row"):
        return reasons

    row, col = target.row, target.col
    rows, cols = board.rows, board.cols
    center_r, center_c = rows / 2, cols / 2

    # Check if this blocks an opponent threat
    from engine.gdl.expr_eval import _line_length
    for direction in board.directions():
        # Check if opponent had a line near this space
        opp_line = 0
        dr, dc = direction
        for sign in [1, -1]:
            r, c = row + sign * dr, col + sign * dc
            while 0 <= r < rows and 0 <= c < cols:
                piece = state_before.get_piece(GridSpace(r, c))
                if piece and piece.owner == opponent:
                    opp_line += 1
                    r += sign * dr
                    c += sign * dc
                else:
                    break
        if opp_line >= 2:
            reasons.append(f"Blocked opponent's {opp_line}-in-a-row threat")
            return reasons

    # Check if AI extended its own line
    for direction in board.directions():
        length = _line_length(state_after, target, direction, player)
        if length >= 3:
            reasons.append(f"Extended line to {length} in a row")
            return reasons
        if length == 2:
            reasons.append("Building a 2-in-a-row")

    # Center control
    dist = abs(row - center_r) + abs(col - center_c)
    max_dist = center_r + center_c
    if dist < max_dist * 0.3:
        if not reasons:
            reasons.append("Took a central position for control")

    # Edge/corner
    if (row == 0 or row == rows - 1) and (col == 0 or col == cols - 1):
        if not reasons:
            reasons.append("Secured a corner position")

    return reasons[:1]  # keep it brief


def _feature_commentary(state_before, state_after, eval_fn, player):
    """Commentary based on which learned features improved most."""
    reasons = []

    try:
        features = eval_fn.features
        weights = eval_fn.weights

        if not features or not weights or len(features) != len(weights):
            return reasons

        # Compute feature deltas
        deltas = []
        for i, feat in enumerate(features):
            try:
                val_before = feat.extract(state_before, player)
                val_after = feat.extract(state_after, player)
                delta = val_after - val_before
                weighted_delta = delta * weights[i]
                if abs(weighted_delta) > 0.01:
                    deltas.append((feat.name, feat.description, weighted_delta, delta))
            except Exception:
                continue

        # Sort by impact
        deltas.sort(key=lambda x: abs(x[2]), reverse=True)

        if deltas:
            name, desc, w_delta, raw_delta = deltas[0]
            direction = "improved" if w_delta > 0 else "reduced"
            # Clean up feature name for display
            display_name = name.replace("_", " ")
            reasons.append(f"Best for {display_name} ({direction})")

    except Exception:
        pass

    return reasons


def _card_commentary(state_before, state_after, move, player):
    """Commentary for card games."""
    reasons = []
    last_action = state_after.state_vars.get("last_action", "")
    last_play = state_after.state_vars.get("last_play", "")

    if "knock" in last_action:
        reasons.append("Deadwood is low enough to knock!")
    elif "gin" in last_action:
        reasons.append("GIN! All cards melded!")
    elif "draw_discard" in last_action:
        reasons.append("Took from discard — that card helps build melds")
    elif "draw_deck" in last_action:
        reasons.append("Drew from deck — discard pile card wasn't useful")

    return reasons
