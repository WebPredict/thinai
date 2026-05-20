"""Tests for the memory system."""

import os
import shutil
import tempfile
import random
import pytest
from engine.reasoner.evaluator import LearnableEval
from engine.memory.store import MemoryStore


@pytest.fixture
def temp_store():
    """Create a temporary memory store for testing."""
    tmpdir = tempfile.mkdtemp()
    store = MemoryStore(data_dir=tmpdir)
    yield store
    shutil.rmtree(tmpdir)


class TestMemoryStore:
    def test_save_and_load(self, temp_store):
        ev = LearnableEval("Reversi", weights=[0.1, 0.2, 0.3, 0.4, 0.5])
        ev.generation = 25
        ev.learning_rate = 0.08

        temp_store.save(ev)
        loaded = temp_store.load("Reversi")

        assert loaded is not None
        assert loaded.game_name == "Reversi"
        assert loaded.weights == [0.1, 0.2, 0.3, 0.4, 0.5]
        assert loaded.generation == 25
        assert loaded.learning_rate == 0.08

    def test_load_nonexistent(self, temp_store):
        assert temp_store.load("Nonexistent Game") is None

    def test_exists(self, temp_store):
        assert not temp_store.exists("Reversi")
        ev = LearnableEval("Reversi")
        temp_store.save(ev)
        assert temp_store.exists("Reversi")

    def test_list_games_empty(self, temp_store):
        assert temp_store.list_games() == []

    def test_list_games(self, temp_store):
        temp_store.save(LearnableEval("Reversi"))
        temp_store.save(LearnableEval("Mancala (Kalah)"))
        games = temp_store.list_games()
        assert len(games) == 2
        names = [g["game_name"] for g in games]
        assert "Reversi" in names
        assert "Mancala (Kalah)" in names

    def test_delete(self, temp_store):
        temp_store.save(LearnableEval("Reversi"))
        assert temp_store.exists("Reversi")
        assert temp_store.delete("Reversi")
        assert not temp_store.exists("Reversi")

    def test_delete_nonexistent(self, temp_store):
        assert not temp_store.delete("Nonexistent")

    def test_overwrite(self, temp_store):
        ev1 = LearnableEval("Reversi", weights=[0.1, 0.2, 0.3, 0.4, 0.5])
        ev1.generation = 10
        temp_store.save(ev1)

        ev2 = LearnableEval("Reversi", weights=[0.5, 0.6, 0.7, 0.8, 0.9])
        ev2.generation = 20
        temp_store.save(ev2)

        loaded = temp_store.load("Reversi")
        assert loaded.weights == [0.5, 0.6, 0.7, 0.8, 0.9]
        assert loaded.generation == 20

    def test_preserves_features(self, temp_store):
        ev = LearnableEval("Reversi")
        temp_store.save(ev)
        loaded = temp_store.load("Reversi")
        assert len(loaded.features) == len(ev.features)
        assert [f.name for f in loaded.features] == [f.name for f in ev.features]

    def test_isolation_between_games(self, temp_store):
        """Saving one game doesn't affect another — no catastrophic forgetting."""
        ev_ttt = LearnableEval("Reversi", weights=[1.0, 2.0, 3.0, 4.0, 5.0])
        ev_ttt.generation = 50
        temp_store.save(ev_ttt)

        ev_c4 = LearnableEval("Mancala (Kalah)", weights=[5.0, 6.0, 7.0, 8.0, 9.0])
        ev_c4.generation = 30
        temp_store.save(ev_c4)

        # Loading TTT should still have original weights
        loaded_ttt = temp_store.load("Reversi")
        assert loaded_ttt.weights == [1.0, 2.0, 3.0, 4.0, 5.0]
        assert loaded_ttt.generation == 50

        # C4 should have its own weights
        loaded_c4 = temp_store.load("Mancala (Kalah)")
        assert loaded_c4.weights == [5.0, 6.0, 7.0, 8.0, 9.0]
        assert loaded_c4.generation == 30
