#!/usr/bin/env python3
"""Compare hand-crafted vs auto-generated features.

Trains each game with both feature sets and compares win rates.
Used to validate that auto-features are competitive before switching.

Usage:
    python3 scripts/compare_features.py
    python3 scripts/compare_features.py --game reversi --games 30
"""

import argparse
import os
import sys
import random
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.engine import GameEngine
from engine.reasoner.evaluator import LearnableEval
from engine.reasoner.features import get_features
from engine.reasoner.auto_features import generate_features
from engine.training.learner import LearningRunner


EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "engine", "games", "examples")

# Games that have both hand-crafted and auto features
GAMES_TO_TEST = {
    "tictactoe": "Tic-Tac-Toe",
    "connect_four": "Connect Four",
    "mancala": "Mancala (Kalah)",
    "reversi": "Reversi",
    "nim": "Nim",
    "go_fish": "Go Fish",
}


def train_with_features(game_file, game_name, features, num_games, label):
    """Train with specific features and return results."""
    engine = GameEngine.from_file(os.path.join(EXAMPLES_DIR, game_file))
    evaluator = LearnableEval(game_name, features=features)
    runner = LearningRunner(engine, evaluator, max_depth=2)

    start = time.monotonic()
    results = runner.train(num_games)
    elapsed = time.monotonic() - start

    return {
        "label": label,
        "game": game_name,
        "num_features": len(features),
        "feature_names": [f.name for f in features],
        "win_rate": results.win_rate,
        "wins": results.wins,
        "losses": results.losses,
        "draws": results.draws,
        "time": round(elapsed, 1),
        "final_weights": {
            f.name: round(w, 3)
            for f, w in zip(features, results.final_weights)
        },
    }


def compare_game(game_key, game_name, num_games, seed=42):
    """Compare hand-crafted vs auto features for one game."""
    game_file = f"{game_key}.json"
    game_path = os.path.join(EXAMPLES_DIR, game_file)

    if not os.path.exists(game_path):
        print(f"  Skipping {game_name} — no GDL file")
        return None

    engine = GameEngine.from_file(game_path)

    # Get both feature sets
    hand_crafted = get_features(game_name)
    auto = generate_features(engine.gdl)

    if not hand_crafted:
        print(f"  {game_name}: no hand-crafted features (auto-only game)")
        # Still run auto to see if it works
        random.seed(seed)
        auto_result = train_with_features(game_file, game_name, auto, num_games, "auto")
        return {"game": game_name, "hand_crafted": None, "auto": auto_result}

    if not auto:
        print(f"  {game_name}: no auto features generated")
        return None

    # Train with hand-crafted
    random.seed(seed)
    hc_result = train_with_features(game_file, game_name, hand_crafted, num_games, "hand-crafted")

    # Train with auto
    random.seed(seed)
    auto_result = train_with_features(game_file, game_name, auto, num_games, "auto")

    return {"game": game_name, "hand_crafted": hc_result, "auto": auto_result}


def main():
    parser = argparse.ArgumentParser(description="Compare feature sets")
    parser.add_argument("--game", help="Specific game to test")
    parser.add_argument("--games", type=int, default=30, help="Training games per test")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    games = {args.game: GAMES_TO_TEST[args.game]} if args.game else GAMES_TO_TEST

    print(f"Feature Comparison: {args.games} training games each\n")
    print(f"{'Game':<20} {'HC Features':<12} {'HC Win%':<10} {'Auto Features':<14} {'Auto Win%':<10} {'Verdict'}")
    print("-" * 90)

    for game_key, game_name in games.items():
        result = compare_game(game_key, game_name, args.games, args.seed)
        if not result:
            continue

        hc = result["hand_crafted"]
        auto = result["auto"]

        if hc and auto:
            hc_wr = f"{hc['win_rate']:.0%}"
            auto_wr = f"{auto['win_rate']:.0%}"
            diff = auto["win_rate"] - hc["win_rate"]
            if diff >= -0.1:
                verdict = "AUTO OK" if diff >= -0.05 else "CLOSE"
            else:
                verdict = f"AUTO BEHIND ({diff:+.0%})"
            print(f"{game_name:<20} {hc['num_features']:<12} {hc_wr:<10} {auto['num_features']:<14} {auto_wr:<10} {verdict}")

            # Show feature details
            print(f"  HC features: {', '.join(hc['feature_names'])}")
            print(f"  Auto features: {', '.join(auto['feature_names'])}")
            print(f"  HC weights: {hc['final_weights']}")
            print(f"  Auto weights: {auto['final_weights']}")
            print()
        elif auto:
            auto_wr = f"{auto['win_rate']:.0%}"
            print(f"{game_name:<20} {'(none)':<12} {'N/A':<10} {auto['num_features']:<14} {auto_wr:<10} AUTO ONLY")
            print(f"  Auto features: {', '.join(auto['feature_names'])}")
            print()


if __name__ == "__main__":
    main()
