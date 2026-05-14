#!/usr/bin/env python3
"""Retention benchmark for ThinAI.

Trains multiple games sequentially, then evaluates each to verify
that learning one game doesn't degrade performance on previously
learned games. This directly tests the "no catastrophic forgetting" claim.

Usage:
    python3 scripts/retention_bench.py
    python3 scripts/retention_bench.py --games tictactoe nim connect_four
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.engine import GameEngine
from engine.reasoner.evaluator import LearnableEval
from engine.reasoner.reasoner import Reasoner
from engine.training.learner import LearningRunner
from engine.training.opponents import RandomOpponent
from engine.memory.store import MemoryStore


EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "engine", "games", "examples")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")

GAME_CONFIGS = {
    "tictactoe": ("tictactoe.json", 25, 4),
    "connect_four": ("connect_four.json", 20, 3),
    "mancala": ("mancala.json", 20, 3),
    "reversi": ("reversi.json", 15, 3),
    "nim": ("nim.json", 25, 4),
}


def train_and_save(game_key, store, num_games=None, depth=None):
    """Train a game and save to memory store."""
    filename, default_games, default_depth = GAME_CONFIGS[game_key]
    num_games = num_games or default_games
    depth = depth or default_depth

    engine = GameEngine.from_file(os.path.join(EXAMPLES_DIR, filename))
    evaluator = LearnableEval(engine.meta["name"])
    runner = LearningRunner(engine, evaluator, max_depth=depth)
    results = runner.train(num_games)
    store.save(evaluator)
    return results.win_rate


def evaluate_from_memory(game_key, store, num_eval=15, depth=None):
    """Load a trained game from memory and evaluate against random."""
    filename, _, default_depth = GAME_CONFIGS[game_key]
    depth = depth or default_depth

    engine = GameEngine.from_file(os.path.join(EXAMPLES_DIR, filename))
    evaluator = store.load(engine.meta["name"])
    if evaluator is None:
        return None

    reasoner = Reasoner(engine, max_depth=depth, eval_fn=evaluator)
    opponent = RandomOpponent(engine)

    wins = 0
    for _ in range(num_eval):
        state = engine.initial_state()
        for _ in range(300):
            result = engine.check_terminal(state)
            if result:
                if result.winner == "player1":
                    wins += 1
                break
            if state.current_player == "player1":
                move = reasoner.choose_move(state)
            else:
                move = opponent.choose_move(state)
            if move is None:
                break
            state = engine.apply_move(state, move)

    return wins / num_eval


def main():
    parser = argparse.ArgumentParser(description="ThinAI Retention Benchmark")
    parser.add_argument("--games", nargs="*", choices=list(GAME_CONFIGS.keys()),
                        help="Games to train sequentially (default: all)")
    args = parser.parse_args()

    games = args.games or list(GAME_CONFIGS.keys())

    # Use a temp directory for this benchmark's memory
    import tempfile
    import shutil
    tmpdir = tempfile.mkdtemp(prefix="thinai_retention_")
    store = MemoryStore(data_dir=tmpdir)

    print("ThinAI Retention Benchmark")
    print(f"Training order: {', '.join(games)}")
    print()

    # Track: after training each game, evaluate ALL previously trained games
    training_results = {}
    retention_matrix = {}  # {game: {after_training_N: win_rate}}

    for i, game_key in enumerate(games):
        filename = GAME_CONFIGS[game_key][0]
        engine = GameEngine.from_file(os.path.join(EXAMPLES_DIR, filename))
        game_name = engine.meta["name"]

        print(f"[{i+1}/{len(games)}] Training {game_name}...")
        start = time.monotonic()
        train_wr = train_and_save(game_key, store)
        elapsed = time.monotonic() - start
        training_results[game_key] = train_wr
        print(f"  Train WR: {train_wr:.0%} ({elapsed:.1f}s)")

        # Evaluate all previously trained games
        print(f"  Evaluating retention after training {game_name}:")
        for prev_key in games[:i + 1]:
            wr = evaluate_from_memory(prev_key, store)
            retention_matrix.setdefault(prev_key, {})[i] = wr
            status = "OK" if wr and wr >= 0.3 else "LOW"
            prev_name = GAME_CONFIGS[prev_key][0].replace(".json", "")
            print(f"    {prev_name:20s} → {wr:.0%} [{status}]")
        print()

    # Summary
    print("=" * 60)
    print("RETENTION SUMMARY")
    print("=" * 60)
    print(f"{'Game':20s} {'Train WR':>10s} {'Final WR':>10s} {'Retained?':>10s}")
    print("-" * 50)
    for game_key in games:
        train_wr = training_results[game_key]
        final_wr = retention_matrix[game_key][len(games) - 1]
        retained = "YES" if final_wr and final_wr >= 0.3 else "NO"
        print(f"{game_key:20s} {train_wr:10.0%} {final_wr:10.0%} {retained:>10s}")

    # Save results
    os.makedirs(RESULTS_DIR, exist_ok=True)
    output_path = os.path.join(
        RESULTS_DIR,
        f"retention_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
    )
    summary = {
        "timestamp": datetime.now().isoformat(),
        "training_order": games,
        "training_win_rates": training_results,
        "retention_matrix": {
            k: {str(step): wr for step, wr in v.items()}
            for k, v in retention_matrix.items()
        },
    }
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nResults saved to: {output_path}")

    # Cleanup
    shutil.rmtree(tmpdir)


if __name__ == "__main__":
    main()
