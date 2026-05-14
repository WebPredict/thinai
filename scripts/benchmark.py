#!/usr/bin/env python3
"""Benchmark script for ThinAI.

Trains and evaluates all games, producing a results summary.
Results are saved as JSON in scripts/results/.

Usage:
    python3 scripts/benchmark.py                    # all games, defaults
    python3 scripts/benchmark.py --games tictactoe nim  # specific games
    python3 scripts/benchmark.py --num-games 30 --depth 3
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.engine import GameEngine
from engine.reasoner.evaluator import LearnableEval
from engine.training.learner import LearningRunner
from engine.training.opponents import RandomOpponent
from engine.memory.store import MemoryStore


EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "engine", "games", "examples")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")

# Game configs: (filename, default training games, default search depth)
GAME_CONFIGS = {
    "tictactoe": ("tictactoe.json", 30, 4),
    "connect_four": ("connect_four.json", 25, 3),
    "mancala": ("mancala.json", 25, 3),
    "reversi": ("reversi.json", 20, 3),
    "nim": ("nim.json", 30, 4),
    "chutes_and_ladders": ("chutes_and_ladders.json", 20, 2),
}


def evaluate_against_random(engine, evaluator, num_games=20, depth=3):
    """Evaluate a trained model against a random opponent."""
    from engine.reasoner.reasoner import Reasoner
    reasoner = Reasoner(engine, max_depth=depth, eval_fn=evaluator)
    opponent = RandomOpponent(engine)

    wins, losses, draws = 0, 0, 0
    for _ in range(num_games):
        state = engine.initial_state()
        for _ in range(300):
            result = engine.check_terminal(state)
            if result:
                if result.result_type == "draw":
                    draws += 1
                elif result.winner == "player1":
                    wins += 1
                else:
                    losses += 1
                break
            if state.current_player == "player1":
                move = reasoner.choose_move(state)
            else:
                move = opponent.choose_move(state)
            if move is None:
                draws += 1
                break
            state = engine.apply_move(state, move)
        else:
            draws += 1

    return {"wins": wins, "losses": losses, "draws": draws, "win_rate": wins / num_games}


def benchmark_game(game_key, num_games=None, depth=None, verbose=True):
    """Train and evaluate a single game. Returns results dict."""
    filename, default_games, default_depth = GAME_CONFIGS[game_key]
    num_games = num_games or default_games
    depth = depth or default_depth

    game_path = os.path.join(EXAMPLES_DIR, filename)
    engine = GameEngine.from_file(game_path)
    game_name = engine.meta["name"]

    if verbose:
        print(f"\n{'='*50}")
        print(f"  {game_name}")
        print(f"  Training: {num_games} games, depth={depth}")
        print(f"{'='*50}")

    evaluator = LearnableEval(game_name)
    runner = LearningRunner(engine, evaluator, max_depth=depth)

    start = time.monotonic()
    train_results = runner.train(num_games)
    train_time = time.monotonic() - start

    if verbose:
        print(f"  Training: {train_results.win_rate:.0%} win rate "
              f"({train_results.wins}W/{train_results.losses}L/{train_results.draws}D) "
              f"in {train_time:.1f}s")

    # Evaluate
    eval_results = evaluate_against_random(engine, evaluator, num_games=20, depth=depth)

    if verbose:
        print(f"  Eval:     {eval_results['win_rate']:.0%} win rate "
              f"({eval_results['wins']}W/{eval_results['losses']}L/{eval_results['draws']}D)")

    # Learning curve
    curve = train_results.win_rate_curve(window=5)
    early_wr = sum(curve[:5]) / min(5, len(curve)) if curve else 0
    late_wr = sum(curve[-5:]) / min(5, len(curve)) if curve else 0

    return {
        "game": game_name,
        "game_key": game_key,
        "training": {
            "num_games": num_games,
            "depth": depth,
            "wins": train_results.wins,
            "losses": train_results.losses,
            "draws": train_results.draws,
            "win_rate": train_results.win_rate,
            "early_win_rate": early_wr,
            "late_win_rate": late_wr,
            "improvement": late_wr - early_wr,
            "time_seconds": round(train_time, 2),
        },
        "evaluation": eval_results,
        "weights": {
            name: weight
            for name, weight in zip(
                [f.name for f in evaluator.features],
                evaluator.weights,
            )
        },
    }


def main():
    parser = argparse.ArgumentParser(description="ThinAI Benchmark")
    parser.add_argument("--games", nargs="*", choices=list(GAME_CONFIGS.keys()),
                        help="Games to benchmark (default: all)")
    parser.add_argument("--num-games", type=int, help="Training games per game")
    parser.add_argument("--depth", type=int, help="Search depth override")
    parser.add_argument("--output", help="Output JSON file path")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose output")
    args = parser.parse_args()

    games = args.games or list(GAME_CONFIGS.keys())
    verbose = not args.quiet

    if verbose:
        print("ThinAI Benchmark")
        print(f"Games: {', '.join(games)}")

    results = []
    total_start = time.monotonic()

    for game_key in games:
        result = benchmark_game(game_key, args.num_games, args.depth, verbose)
        results.append(result)

    total_time = time.monotonic() - total_start

    # Summary
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_time_seconds": round(total_time, 2),
        "games": results,
    }

    if verbose:
        print(f"\n{'='*50}")
        print("  SUMMARY")
        print(f"{'='*50}")
        for r in results:
            print(f"  {r['game']:25s} train={r['training']['win_rate']:5.0%}  "
                  f"eval={r['evaluation']['win_rate']:5.0%}  "
                  f"improve={r['training']['improvement']:+.0%}")
        print(f"\n  Total time: {total_time:.1f}s")

    # Save results
    os.makedirs(RESULTS_DIR, exist_ok=True)
    output_path = args.output or os.path.join(
        RESULTS_DIR,
        f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
    )
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2)

    if verbose:
        print(f"\n  Results saved to: {output_path}")


if __name__ == "__main__":
    main()
