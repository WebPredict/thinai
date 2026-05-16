#!/usr/bin/env python3
"""Validate auto-generated features quickly — no full training needed.

Plays a handful of random games and checks:
1. Do features vary across states? (constant features are useless)
2. Do features differ between winning and losing positions?
3. How do auto features compare to hand-crafted ones?

Usage:
    python3 scripts/validate_features.py
    python3 scripts/validate_features.py --game reversi
"""

import argparse
import os
import sys
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.engine import GameEngine
from engine.reasoner.features import get_features
from engine.reasoner.auto_features import generate_features

EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "engine", "games", "examples")

GAMES = {
    "tictactoe": "Tic-Tac-Toe",
    "connect_four": "Connect Four",
    "mancala": "Mancala (Kalah)",
    "reversi": "Reversi",
    "nim": "Nim",
    "go_fish": "Go Fish",
}


def play_random_game(engine, max_moves=200):
    """Play a random game, collecting feature snapshots at each state.
    Returns: (states, outcome) where outcome is +1 (p1 wins), -1, or 0.
    """
    state = engine.initial_state()
    states = [state]

    for _ in range(max_moves):
        result = engine.check_terminal(state)
        if result:
            if result.result_type == "draw":
                return states, 0
            return states, 1 if result.winner == "player1" else -1
        moves = engine.legal_moves(state)
        if not moves:
            return states, 0
        state = engine.apply_move(state, random.choice(moves))
        states.append(state)

    return states, 0


def evaluate_features(features, states, player="player1"):
    """Extract feature values across all states."""
    results = {f.name: [] for f in features}
    for state in states:
        for f in features:
            try:
                val = f.extract(state, player)
                results[f.name].append(val)
            except Exception:
                results[f.name].append(0.0)
    return results


def analyze_feature_quality(name, values):
    """Analyze if a feature is useful: variance, range, non-constant."""
    if not values:
        return {"name": name, "useful": False, "reason": "no values"}

    min_v = min(values)
    max_v = max(values)
    mean_v = sum(values) / len(values)
    variance = sum((v - mean_v) ** 2 for v in values) / len(values)
    range_v = max_v - min_v

    if range_v < 0.001:
        return {"name": name, "useful": False, "reason": "constant",
                "value": round(mean_v, 4)}

    return {
        "name": name,
        "useful": True,
        "min": round(min_v, 4),
        "max": round(max_v, 4),
        "mean": round(mean_v, 4),
        "variance": round(variance, 4),
        "range": round(range_v, 4),
    }


def check_win_correlation(features, engine, num_games=5):
    """Check if features differ between winning and losing final positions."""
    win_features = {f.name: [] for f in features}
    loss_features = {f.name: [] for f in features}

    for _ in range(num_games):
        states, outcome = play_random_game(engine)
        if outcome == 0 or len(states) < 3:
            continue

        # Sample a late-game state (70% through)
        late_idx = int(len(states) * 0.7)
        late_state = states[late_idx]

        for f in features:
            try:
                val = f.extract(late_state, "player1")
            except Exception:
                val = 0.0

            if outcome > 0:
                win_features[f.name].append(val)
            else:
                loss_features[f.name].append(val)

    correlations = {}
    for f in features:
        wins = win_features[f.name]
        losses = loss_features[f.name]
        if wins and losses:
            win_avg = sum(wins) / len(wins)
            loss_avg = sum(losses) / len(losses)
            diff = win_avg - loss_avg
            correlations[f.name] = {
                "win_avg": round(win_avg, 4),
                "loss_avg": round(loss_avg, 4),
                "diff": round(diff, 4),
                "predictive": abs(diff) > 0.05,
            }
        else:
            correlations[f.name] = {"predictive": False, "reason": "not enough data"}

    return correlations


def validate_game(game_key, game_name, seed=42):
    """Validate features for one game."""
    game_path = os.path.join(EXAMPLES_DIR, f"{game_key}.json")
    if not os.path.exists(game_path):
        return

    random.seed(seed)
    engine = GameEngine.from_file(game_path)

    hc_features = get_features(game_name)
    auto_features = generate_features(engine.gdl)

    print(f"\n{'='*70}")
    print(f"  {game_name}")
    print(f"{'='*70}")

    # Play a few random games for state samples
    all_states = []
    for _ in range(5):
        states, _ = play_random_game(engine)
        all_states.extend(states[::max(1, len(states)//10)])  # sample ~10 per game

    for label, features in [("HAND-CRAFTED", hc_features), ("AUTO-GENERATED", auto_features)]:
        if not features:
            print(f"\n  {label}: (none)")
            continue

        print(f"\n  {label} ({len(features)} features):")

        # 1. Check variance
        values = evaluate_features(features, all_states)
        useful_count = 0
        for f in features:
            analysis = analyze_feature_quality(f.name, values[f.name])
            status = "OK" if analysis["useful"] else f"USELESS ({analysis.get('reason', '')})"
            if analysis["useful"]:
                useful_count += 1
                print(f"    {f.name:<25} range [{analysis['min']:.3f}, {analysis['max']:.3f}]  var={analysis['variance']:.4f}  {status}")
            else:
                print(f"    {f.name:<25} {status} = {analysis.get('value', '?')}")

        # 2. Check win correlation
        random.seed(seed)
        correlations = check_win_correlation(features, engine, num_games=5)
        predictive = sum(1 for c in correlations.values() if c.get("predictive"))

        print(f"\n    Useful: {useful_count}/{len(features)} vary across states")
        print(f"    Predictive: {predictive}/{len(features)} differ between wins/losses")

        if correlations:
            print(f"    Win/loss signal:")
            for fname, corr in sorted(correlations.items(), key=lambda x: -abs(x[1].get("diff", 0))):
                if corr.get("predictive"):
                    print(f"      {fname:<25} win={corr['win_avg']:+.3f}  loss={corr['loss_avg']:+.3f}  diff={corr['diff']:+.3f}")

    # Summary comparison
    if hc_features and auto_features:
        print(f"\n  COMPARISON:")
        hc_vals = evaluate_features(hc_features, all_states)
        auto_vals = evaluate_features(auto_features, all_states)
        hc_useful = sum(1 for f in hc_features if analyze_feature_quality(f.name, hc_vals[f.name])["useful"])
        auto_useful = sum(1 for f in auto_features if analyze_feature_quality(f.name, auto_vals[f.name])["useful"])

        random.seed(seed)
        hc_corr = check_win_correlation(hc_features, engine, 5)
        random.seed(seed)
        auto_corr = check_win_correlation(auto_features, engine, 5)
        hc_pred = sum(1 for c in hc_corr.values() if c.get("predictive"))
        auto_pred = sum(1 for c in auto_corr.values() if c.get("predictive"))

        print(f"    HC:   {hc_useful}/{len(hc_features)} useful, {hc_pred}/{len(hc_features)} predictive")
        print(f"    Auto: {auto_useful}/{len(auto_features)} useful, {auto_pred}/{len(auto_features)} predictive")
        if auto_pred >= hc_pred:
            print(f"    Verdict: AUTO READY")
        elif auto_pred >= hc_pred - 1:
            print(f"    Verdict: AUTO CLOSE")
        else:
            print(f"    Verdict: AUTO NEEDS WORK")


def main():
    parser = argparse.ArgumentParser(description="Validate features quickly")
    parser.add_argument("--game", help="Specific game to test")
    args = parser.parse_args()

    games = {args.game: GAMES[args.game]} if args.game else GAMES

    for game_key, game_name in games.items():
        validate_game(game_key, game_name)


if __name__ == "__main__":
    main()
