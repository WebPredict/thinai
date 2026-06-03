"""Intuitive priors for ThinAI.

Derives basic "common sense" initial weight biases from the GDL
structure. This is what a kid figures out just by reading the rules
before playing a single game:

  "I win by getting 4 in a row → putting pieces near each other is probably good"
  "I win when opponent can't move → capturing their pieces is probably good"
  "Getting a king is special → advancing pieces is probably good"

These are small biases, not strategies — just enough to avoid
completely aimless play on game 1.
"""

from __future__ import annotations
import re
from engine.reasoner.features import FeatureSpec


def generate_priors(features: list[FeatureSpec], gdl: dict) -> list[float]:
    """Generate initial weight biases from GDL structure.

    Returns a list of weights (one per feature) with small biases
    based on what the win conditions and rules suggest is valuable.

    Biases are intentionally small (0.1-0.5) — enough to break
    ties meaningfully but not so strong that learning can't override them.
    """
    end_conditions = gdl.get("end_conditions", [])
    rules = gdl.get("rules", [])
    board = gdl.get("board", {})

    # Analyze what the game rewards
    signals = _analyze_gdl(end_conditions, rules, board, gdl)

    # Map signals to feature weights
    weights = []
    for f in features:
        bias = _prior_for_feature(f.name, signals)
        weights.append(bias)

    return weights


def describe_priors(features: list[FeatureSpec], weights: list[float],
                     gdl: dict) -> list[dict]:
    """Describe the reasoning behind each prior for the UI."""
    signals = _analyze_gdl(
        gdl.get("end_conditions", []),
        gdl.get("rules", []),
        gdl.get("board", {}),
        gdl,
    )

    descriptions = []
    for f, w in zip(features, weights):
        if abs(w) > 0.05:
            reason = _explain_prior(f.name, w, signals)
            descriptions.append({
                "feature": f.name,
                "prior": round(w, 3),
                "reason": reason,
            })
    return descriptions


def _analyze_gdl(end_conditions, rules, board, gdl) -> dict:
    """Analyze GDL to determine what the game rewards."""
    signals = {
        "piece_count_matters": False,
        "lines_matter": False,
        "capture_matters": False,
        "sets_matter": False,
        "advancement_matters": False,
        "mobility_matters": False,
        "score_comparison": False,
        "opponent_blocked": False,
        "has_promotion": False,
    }

    # Analyze end conditions
    for ec in end_conditions:
        cond = str(ec.get("condition", ""))
        score = str(ec.get("score", ""))
        player = str(ec.get("player", ""))

        # Piece counting in win condition
        if "count" in cond or "count" in score:
            if "pieces" in cond or "pieces" in score:
                signals["piece_count_matters"] = True

        # Line-based wins
        if "line_length" in cond:
            signals["lines_matter"] = True

        # Score comparison (player_by_score)
        if player == "player_by_score":
            signals["score_comparison"] = True

        # Sets/collections
        if "sets" in cond or "sets" in score:
            signals["sets_matter"] = True

        # Opponent can't move
        if "no_moves" in cond or "has_legal_move" in cond:
            signals["opponent_blocked"] = True
            signals["capture_matters"] = True  # usually the way to block

        # All spaces empty (Nim-style)
        if "all" in cond and "empty" in cond:
            signals["piece_count_matters"] = True

    # Analyze rules for capture/promotion mechanics
    for rule in rules:
        effects = rule.get("effects", [])
        for effect in effects:
            effect_str = str(effect)
            # Capture/removal effects
            if "remove" in effect_str or "capture" in effect_str or "jump" in effect_str:
                signals["capture_matters"] = True
            # Promotion
            if "king" in effect_str or "promote" in effect_str:
                signals["has_promotion"] = True
                signals["advancement_matters"] = True

        # Check for built-in effects that imply capture
        for effect in effects:
            if "checkers" in str(effect) or "flip" in str(effect):
                signals["capture_matters"] = True

    # Check pieces list for promotion hints
    piece_names = [p.get("name", "").lower() for p in gdl.get("pieces", [])]
    if "king" in piece_names and "man" in piece_names:
        signals["has_promotion"] = True
        signals["advancement_matters"] = True

    # Check end conditions for opponent-blocking patterns
    for ec in end_conditions:
        cond = str(ec.get("condition", ""))
        if "opponent" in cond and ("no_moves" in cond or "has_no" in cond):
            signals["opponent_blocked"] = True
            signals["capture_matters"] = True

    # If opponent being blocked matters, mobility is relevant
    if signals["opponent_blocked"]:
        signals["mobility_matters"] = True

    return signals


def _prior_for_feature(feature_name: str, signals: dict) -> float:
    """Assign an initial bias to a feature based on game signals.

    Biases are small — a gentle nudge, not a strong opinion.
    Positive = "this is probably good", negative = "probably bad".
    """
    name = feature_name.lower()

    # Piece-related features — gentle bias, easily overridden
    if signals["piece_count_matters"] or signals["capture_matters"]:
        if any(w in name for w in ["piece_advantage", "piece_count", "disc_count"]):
            return 0.15  # having more pieces is probably good (but not always)

    if signals["capture_matters"]:
        if "advantage" in name:
            return 0.1

    # Line-related features — stronger priors since these directly relate to winning
    if signals["lines_matter"]:
        if any(w in name for w in ["three_in_row", "longest_line", "line_threat"]):
            return 0.5  # building lines toward the win condition
        if any(w in name for w in ["two_in_row"]):
            return 0.3  # partial progress

    # Set/collection features
    if signals["sets_matter"]:
        if any(w in name for w in ["set_lead", "score_lead", "near_set", "near_complete"]):
            return 0.15  # collecting sets is the goal
        if "pairs" in name:
            return 0.1  # pairs are progress toward sets

    # Advancement/promotion
    if signals["advancement_matters"]:
        if "advancement" in name:
            return 0.1
        if "king" in name:
            return 0.15  # kings are valuable

    # Mobility
    if signals["mobility_matters"]:
        if "mobility" in name:
            return 0.1

    # Card conservation — save high cards for later when stakes escalate
    if "conservation" in name:
        return 0.5  # strong prior: saving high cards is almost always right

    # Score-racing features — being ahead and making progress are good
    if signals.get("score_comparison"):
        if "score_racing_lead" in name:
            return 0.3  # being ahead on score is good
        if "score_racing_progress" in name:
            return 0.2  # making progress toward target is good
        if name == "is_dealer":
            return 0.1  # slight dealer advantage in many card games

    # Center control — moderate bias, usually helpful
    if "center" in name:
        return 0.2

    # Corner features — depends on game, stay neutral
    if "corner" in name:
        return 0.0  # could be good (Reversi) or irrelevant

    # Default: near zero, slight random perturbation
    return 0.0


# ======================================================================
# Strategy hints: user-provided plain English → feature prior boosts
# ======================================================================

# Maps hint keywords to feature name patterns and boost amounts
HINT_KEYWORDS = {
    # Positional
    "center": [("center", 0.5)],
    "middle": [("center", 0.5)],
    "corner": [("corner", 0.4)],
    "edge": [("edge", 0.3)],

    # Lines and threats
    "line": [("line", 0.4), ("longest", 0.3)],
    "row": [("line", 0.4)],
    "block": [("line_threat", 0.4), ("line", 0.3)],
    "threat": [("line_threat", 0.5)],

    # Pieces and capture
    "capture": [("piece_advantage", 0.5), ("piece", 0.3)],
    "pieces": [("piece_advantage", 0.3)],
    "advantage": [("advantage", 0.4)],
    "protect": [("blot", 0.4), ("exposed", 0.4), ("safety", 0.4)],
    "exposed": [("blot", 0.5), ("exposed", 0.5), ("safety", 0.4)],
    "single": [("blot", 0.4), ("exposed", 0.4), ("singles", 0.4)],
    "together": [("adjacency", 0.4), ("spread", -0.3)],
    "group": [("adjacency", 0.4), ("spread", -0.3)],

    # Card games
    "save": [("conservation", 0.5)],
    "high card": [("conservation", 0.4), ("high_card", 0.3)],
    "trump": [("trump", 0.5)],
    "bid": [("bid", 0.4)],

    # General strategy
    "mobility": [("mobility", 0.4)],
    "options": [("mobility", 0.3)],
    "territory": [("territory", 0.4), ("piece_advantage", 0.3)],
    "control": [("center", 0.3), ("territory", 0.3)],
    "advance": [("advancement", 0.4), ("progress", 0.3)],
    "forward": [("advancement", 0.3), ("progress", 0.3)],
    "king": [("king", 0.4), ("promoted", 0.4)],
    "promote": [("promoted", 0.5), ("advancement", 0.3)],
}


def apply_hints(features: list, weights: list[float], hint_text: str) -> list[float]:
    """Apply user strategy hints to boost feature weights.

    Args:
        features: list of FeatureSpec objects
        weights: current weight list (modified in place and returned)
        hint_text: plain English strategy hint from user

    Returns:
        Modified weights list
    """
    if not hint_text or not features:
        return weights

    hint_lower = hint_text.lower()
    boosted = set()

    for keyword, mappings in HINT_KEYWORDS.items():
        if keyword in hint_lower:
            for feature_pattern, boost in mappings:
                for i, feat in enumerate(features):
                    if feature_pattern in feat.name.lower() and i not in boosted:
                        weights[i] += boost
                        boosted.add(i)

    return weights


def _explain_prior(feature_name: str, weight: float, signals: dict) -> str:
    """Generate a human-readable explanation for a prior."""
    name = feature_name.lower()
    direction = "good" if weight > 0 else "bad"

    if "advantage" in name or "piece_count" in name or "disc_count" in name:
        if signals["capture_matters"]:
            return f"Having more pieces is probably {direction} since opponents can be captured"
        return f"Having more pieces is probably {direction}"

    if "king" in name:
        return f"Kings are special pieces — probably {direction} to have more"

    if "advancement" in name:
        return f"Moving pieces forward toward promotion is probably {direction}"

    if "line" in name or "row" in name or "threat" in name:
        return f"Building lines is probably {direction} since you win by getting N in a row"

    if "set" in name or "score" in name:
        return f"Completing sets is probably {direction} since that's how you score"

    if "pairs" in name or "near" in name:
        return f"Having pairs/near-complete collections is probably {direction}"

    if "center" in name:
        return f"Controlling the center is probably slightly {direction}"

    if "mobility" in name:
        return f"Having more move options is probably {direction}"

    return f"Initial guess: probably slightly {direction}"
