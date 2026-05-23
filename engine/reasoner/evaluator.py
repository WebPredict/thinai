"""Learnable evaluation function for ThinAI.

A linear model over hand-crafted features. Weights start at zero
(random play) and shift based on game outcomes. Interpretable,
serializable, and per-game.
"""

from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import Optional

from engine.gdl.state import GameState
from engine.reasoner.features import FeatureSpec, get_features


class LearnableEval:
    """Weighted feature evaluation that learns from game outcomes."""

    def __init__(
        self,
        game_name: str,
        features: Optional[list[FeatureSpec]] = None,
        weights: Optional[list[float]] = None,
        learning_rate: float = 0.15,
        gdl: Optional[dict] = None,
    ):
        self.game_name = game_name
        self.features = features or get_features(game_name)
        if not self.features and gdl:
            # No hand-crafted features — auto-generate from GDL
            from engine.reasoner.auto_features import generate_features
            self.features = generate_features(gdl)
        if not self.features:
            raise ValueError(f"No features for game: {game_name}. Provide GDL for auto-generation.")

        if weights is not None:
            self.weights = list(weights)
        else:
            # Use auto-priors if GDL available, otherwise small random
            if gdl:
                from engine.reasoner.auto_priors import generate_priors
                self.weights = generate_priors(self.features, gdl)
            else:
                self.weights = [random.uniform(-0.05, 0.05) for _ in self.features]

        self.learning_rate = learning_rate
        self.generation = 0
        self.history: list[dict] = []

    def __call__(self, state: GameState, player: str, engine=None) -> float:
        """Evaluate a position from player's perspective."""
        score = 0.0
        for spec, weight in zip(self.features, self.weights):
            score += weight * spec.extract(state, player)
        return score

    def extract_features(self, state: GameState, player: str) -> list[float]:
        """Extract feature values for a state (used for trace collection)."""
        return [spec.extract(state, player) for spec in self.features]

    def add_features(self, new_features: list):
        """Add newly-discovered features with zero weights."""
        for f in new_features:
            if f.name not in {existing.name for existing in self.features}:
                self.features.append(f)
                self.weights.append(0.0)

    def update_weights(self, game_trace: list[dict], outcome: float):
        """Update weights based on a completed game.

        Args:
            game_trace: list of {"features": list[float], "move_index": int, "total_moves": int}
            outcome: +1.0 (win), 0.0 (draw), -1.0 (loss) from learner's perspective
        """
        self.generation += 1

        for snapshot in game_trace:
            features = snapshot["features"]
            # Weight late-game positions more heavily
            total = snapshot.get("total_moves", 1)
            idx = snapshot.get("move_index", 0)
            move_weight = 0.3 + 0.7 * (idx / max(total, 1))

            for i, f_val in enumerate(features):
                adjustment = self.learning_rate * outcome * f_val * move_weight
                # Clamp individual weight adjustments to prevent runaway
                adjustment = max(-0.5, min(0.5, adjustment))
                self.weights[i] += adjustment

        # Adaptive learning rate decay
        if outcome > 0:
            self.learning_rate = max(0.01, self.learning_rate * 0.95)
        elif outcome < 0:
            self.learning_rate = max(0.01, self.learning_rate * 0.92)
        else:
            self.learning_rate = max(0.01, self.learning_rate * 0.99)

        # Record snapshot
        self.history.append({
            "generation": self.generation,
            "weights": list(self.weights),
            "outcome": outcome,
            "learning_rate": self.learning_rate,
        })

    def weight_summary(self) -> list[dict]:
        """Human-readable summary of current weights."""
        items = []
        for spec, w in zip(self.features, self.weights):
            items.append({
                "feature": spec.name,
                "description": spec.description,
                "weight": round(w, 4),
            })
        return sorted(items, key=lambda x: abs(x["weight"]), reverse=True)

    def to_dict(self) -> dict:
        """Serialize for storage."""
        return {
            "game_name": self.game_name,
            "feature_names": [f.name for f in self.features],
            "weights": list(self.weights),
            "learning_rate": self.learning_rate,
            "generation": self.generation,
            "history": self.history,
        }

    @classmethod
    def from_dict(cls, data: dict, gdl: Optional[dict] = None) -> "LearnableEval":
        """Deserialize from storage."""
        features = get_features(data["game_name"])
        saved_weights = data["weights"]

        if not features:
            # No hand-crafted features — try auto-generation from GDL
            if not gdl:
                try:
                    import os
                    from engine.engine import GameEngine
                    examples_dir = os.path.join(os.path.dirname(__file__), "..", "games", "examples")
                    slug = data["game_name"].lower().replace(" ", "_").replace("-", "_").replace("(", "").replace(")", "")
                    no_sep = slug.replace("_", "")
                    for candidate in [slug, slug.replace("__", "_"), no_sep]:
                        path = os.path.join(examples_dir, f"{candidate}.json")
                        if os.path.exists(path):
                            gdl = GameEngine.from_file(path).gdl
                            break
                except Exception:
                    pass
            if gdl:
                from engine.reasoner.auto_features import generate_features
                features = generate_features(gdl)

        # If feature count changed (e.g. switched from L0 to auto), reset weights
        if features and len(features) != len(saved_weights):
            saved_weights = None

        evaluator = cls(
            game_name=data["game_name"],
            features=features if features else None,
            weights=saved_weights,
            learning_rate=data["learning_rate"],
            gdl=gdl,
        )
        evaluator.generation = data["generation"] if saved_weights else 0
        evaluator.history = data.get("history", []) if saved_weights else []
        return evaluator
