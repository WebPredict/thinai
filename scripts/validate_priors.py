#!/usr/bin/env python3
"""Validate auto-generated priors vs zero initialization.

For each game, shows what priors the system derives from the rules
and plays a few quick games to check they help.

Usage:
    python3 scripts/validate_priors.py
    python3 scripts/validate_priors.py --game checkers
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
from engine.reasoner.auto_priors import generate_priors, describe_priors
from engine.training.learner import LearningRunner

EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "engine", "games", "examples")

GAMES = {
    "tictactoe": "Tic-Tac-Toe",
    "connect_four": "Connect Four",
    "mancala": "Mancala (Kalah)",
    "reversi": "Reversi",
    "nim": "Nim",
    "checkers": "Checkers",
    "go_fish": "Go Fish",
}


def test_game(game_key, game_name, num_games=10, seed=42):
    game_path = os.path.join(EXAMPLES_DIR, f"{game_key}.json")
    if not os.path.exists(game_path):
        return

    engine = GameEngine.from_file(game_path)
    features = get_features(game_name)
    if not features:
        print(f"  {game_name}: no features, skipping")
        return

    # Generate and show priors
    priors = generate_priors(features, engine.gdl)
    descriptions = describe_priors(features, priors, engine.gdl)

    print(f"\n{'='*60}")
    print(f"  {game_name}")
    print(f"{'='*60}")
    print(f"\n  Derived priors (what a kid guesses from the rules):")
    for f, p in zip(features, priors):
        marker = "***" if abs(p) > 0.1 else "   "
        print(f"    {marker} {f.name:<25} prior={p:+.3f}  ({f.description})")

    if descriptions:
        print(f"\n  Reasoning:")
        for d in descriptions:
            print(f"    {d['feature']}: {d['reason']}")

    # Train with priors
    random.seed(seed)
    eval_priors = LearnableEval(game_name, features=features, gdl=engine.gdl)
    runner_p = LearningRunner(engine, eval_priors, max_depth=2)
    start = time.monotonic()
    results_p = runner_p.train(num_games)
    time_p = time.monotonic() - start

    # Train with zero init (no priors)
    random.seed(seed)
    eval_zero = LearnableEval(game_name, features=features)
    eval_zero.weights = [0.0] * len(features)  # force zero
    runner_z = LearningRunner(engine, eval_zero, max_depth=2)
    start = time.monotonic()
    results_z = runner_z.train(num_games)
    time_z = time.monotonic() - start

    # Compare
    draws_p = results_p.draws
    draws_z = results_z.draws
    wr_p = results_p.win_rate
    wr_z = results_z.win_rate

    print(f"\n  Results ({num_games} games):")
    print(f"    With priors:    {results_p.wins}W {results_p.losses}L {draws_p}D  win_rate={wr_p:.0%}  ({time_p:.1f}s)")
    print(f"    Zero init:      {results_z.wins}W {results_z.losses}L {draws_z}D  win_rate={wr_z:.0%}  ({time_z:.1f}s)")

    diff = wr_p - wr_z
    if diff > 0.05:
        print(f"    Verdict: PRIORS HELP (+{diff:.0%})")
    elif diff > -0.05:
        print(f"    Verdict: SIMILAR")
    else:
        print(f"    Verdict: PRIORS HURT ({diff:+.0%}) — needs investigation")

    if draws_z > draws_p + 2:
        print(f"    Note: Priors reduced draws from {draws_z} to {draws_p}")


def main():
    parser = argparse.ArgumentParser(description="Validate auto-priors")
    parser.add_argument("--game", help="Specific game to test")
    parser.add_argument("--games", type=int, default=10, help="Training games")
    args = parser.parse_args()

    games = {args.game: GAMES[args.game]} if args.game else GAMES

    for game_key, game_name in games.items():
        test_game(game_key, game_name, args.games)


if __name__ == "__main__":
    main()
