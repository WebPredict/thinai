"""Retention tests — learn multiple games, verify each is retained.

The memory system stores weights per-game in isolated files, so
retention is guaranteed by architecture. These tests verify the
full pipeline: train → save → train another → load first → still works.
"""

import os
import random
import shutil
import tempfile
import pytest

from engine.engine import GameEngine
from engine.reasoner.evaluator import LearnableEval
from engine.reasoner.reasoner import Reasoner
from engine.training.learner import LearningRunner
from engine.training.opponents import RandomOpponent
from engine.memory.store import MemoryStore


EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "games", "examples")


@pytest.fixture
def temp_store():
    tmpdir = tempfile.mkdtemp()
    store = MemoryStore(data_dir=tmpdir)
    yield store
    shutil.rmtree(tmpdir)


def _train_game(game_file: str, num_games: int, depth: int, store: MemoryStore):
    """Train a game and save to memory. Returns final win rate."""
    engine = GameEngine.from_file(os.path.join(EXAMPLES_DIR, game_file))
    evaluator = LearnableEval(engine.meta["name"])
    runner = LearningRunner(engine, evaluator, max_depth=depth)
    results = runner.train(num_games)
    store.save(evaluator)
    return results.win_rate, evaluator.generation


def _evaluate_game(game_file: str, store: MemoryStore, num_games: int = 15, depth: int = 3):
    """Load a trained game from memory and evaluate against random."""
    engine = GameEngine.from_file(os.path.join(EXAMPLES_DIR, game_file))
    evaluator = store.load(engine.meta["name"])
    assert evaluator is not None, f"No saved weights for {engine.meta['name']}"

    reasoner = Reasoner(engine, max_depth=depth, eval_fn=evaluator)
    opponent = RandomOpponent(engine)

    wins = 0
    for _ in range(num_games):
        state = engine.initial_state()
        for _ in range(200):
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
    return wins / num_games


class TestRetention:
    def test_ttt_then_c4_retains_ttt(self, temp_store):
        """Train TTT, then C4. Loading TTT should still work."""
        random.seed(42)

        # Train TTT
        ttt_wr, ttt_gen = _train_game("tictactoe.json", 25, 4, temp_store)
        assert ttt_wr >= 0.5, f"TTT training failed: {ttt_wr:.0%}"

        # Train C4
        c4_wr, c4_gen = _train_game("connect_four.json", 20, 3, temp_store)

        # Evaluate TTT from memory — should still be competent
        ttt_eval_wr = _evaluate_game("tictactoe.json", temp_store, num_games=15, depth=4)
        assert ttt_eval_wr >= 0.4, \
            f"TTT retained win rate too low: {ttt_eval_wr:.0%} (trained at {ttt_wr:.0%})"

    def test_sequential_training_all_retained(self, temp_store):
        """Train TTT and C4 sequentially, verify both retained."""
        random.seed(123)

        # Train both
        _train_game("tictactoe.json", 20, 4, temp_store)
        _train_game("connect_four.json", 15, 3, temp_store)

        # Both should be in memory
        games = temp_store.list_games()
        names = [g["game_name"] for g in games]
        assert "Tic-Tac-Toe" in names
        assert "Connect Four" in names

        # Both should still play competently
        ttt_wr = _evaluate_game("tictactoe.json", temp_store, num_games=10, depth=4)
        c4_wr = _evaluate_game("connect_four.json", temp_store, num_games=10, depth=3)

        assert ttt_wr >= 0.3, f"TTT retained WR: {ttt_wr:.0%}"
        assert c4_wr >= 0.3, f"C4 retained WR: {c4_wr:.0%}"

    def test_weights_unchanged_after_other_training(self, temp_store):
        """Saving one game's weights doesn't modify another's."""
        random.seed(42)

        # Train TTT and save
        engine_ttt = GameEngine.from_file(os.path.join(EXAMPLES_DIR, "tictactoe.json"))
        ev_ttt = LearnableEval("Tic-Tac-Toe")
        runner = LearningRunner(engine_ttt, ev_ttt, max_depth=4)
        runner.train(15)
        temp_store.save(ev_ttt)
        saved_ttt_weights = list(ev_ttt.weights)

        # Train C4 and save
        _train_game("connect_four.json", 15, 3, temp_store)

        # Load TTT — weights should be exactly the same
        loaded_ttt = temp_store.load("Tic-Tac-Toe")
        assert loaded_ttt.weights == saved_ttt_weights, \
            "TTT weights changed after training C4!"
