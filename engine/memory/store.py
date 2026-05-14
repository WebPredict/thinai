"""Memory system for ThinAI.

Stores and retrieves learned evaluation weights per game.
Each game's knowledge is isolated in its own JSON file,
preventing catastrophic forgetting by design.
"""

from __future__ import annotations
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional

from engine.reasoner.evaluator import LearnableEval


@dataclass
class GameMemory:
    """Stored knowledge for a single game."""
    game_name: str
    feature_names: list[str]
    weights: list[float]
    generation: int
    learning_rate: float
    history: list[dict]
    metadata: dict

    @property
    def version(self) -> int:
        return 1


class MemoryStore:
    """Persistent storage for game memories."""

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir or os.path.join(os.path.dirname(__file__), "data")
        os.makedirs(self.data_dir, exist_ok=True)

    def save(self, evaluator: LearnableEval) -> str:
        """Save an evaluator's learned state. Returns the file path."""
        memory = GameMemory(
            game_name=evaluator.game_name,
            feature_names=[f.name for f in evaluator.features],
            weights=list(evaluator.weights),
            generation=evaluator.generation,
            learning_rate=evaluator.learning_rate,
            history=evaluator.history[-50:],  # Keep last 50 snapshots to limit size
            metadata={
                "saved_at": datetime.now().isoformat(),
                "total_generations": evaluator.generation,
            },
        )
        path = self._path_for(memory.game_name)
        with open(path, "w") as f:
            json.dump(asdict(memory), f, indent=2)
        return path

    def load(self, game_name: str) -> Optional[LearnableEval]:
        """Load a saved evaluator. Returns None if not found."""
        path = self._path_for(game_name)
        if not os.path.exists(path):
            return None

        with open(path) as f:
            data = json.load(f)

        return LearnableEval.from_dict({
            "game_name": data["game_name"],
            "weights": data["weights"],
            "learning_rate": data["learning_rate"],
            "generation": data["generation"],
            "history": data.get("history", []),
            "feature_names": data["feature_names"],
        })

    def exists(self, game_name: str) -> bool:
        """Check if a game has saved memory."""
        return os.path.exists(self._path_for(game_name))

    def list_games(self) -> list[dict]:
        """List all stored games with summary info."""
        games = []
        for filename in os.listdir(self.data_dir):
            if not filename.endswith(".json"):
                continue
            path = os.path.join(self.data_dir, filename)
            try:
                with open(path) as f:
                    data = json.load(f)
                games.append({
                    "game_name": data["game_name"],
                    "generation": data["generation"],
                    "saved_at": data.get("metadata", {}).get("saved_at"),
                    "num_features": len(data.get("feature_names", [])),
                })
            except (json.JSONDecodeError, KeyError):
                continue
        return sorted(games, key=lambda g: g["game_name"])

    def delete(self, game_name: str) -> bool:
        """Delete stored memory for a game. Returns True if deleted."""
        path = self._path_for(game_name)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def _path_for(self, game_name: str) -> str:
        """Get the file path for a game's memory."""
        safe = game_name.lower().replace(" ", "_").replace("(", "").replace(")", "")
        return os.path.join(self.data_dir, f"{safe}.json")
