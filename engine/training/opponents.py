"""Opponent implementations for training."""

from __future__ import annotations
import random
from typing import Optional

from engine.engine import GameEngine
from engine.gdl.state import GameState, Move
from engine.reasoner.reasoner import Reasoner


class RandomOpponent:
    """Selects uniformly from legal moves."""

    def __init__(self, engine: GameEngine):
        self.engine = engine

    def choose_move(self, state: GameState) -> Optional[Move]:
        moves = self.engine.legal_moves(state)
        if not moves:
            return None
        return random.choice(moves)


class SnapshotOpponent:
    """Plays using a frozen snapshot of learned weights at low depth.

    Used for graduated difficulty — the learner plays against an older
    version of itself, creating an arms race that develops real strategy.
    """

    def __init__(self, engine: GameEngine, evaluator, max_depth: int = 2):
        from engine.reasoner.evaluator import LearnableEval
        # Create a frozen copy of the evaluator's current weights
        self._eval = LearnableEval(
            evaluator.game_name,
            features=evaluator.features,
            weights=list(evaluator.weights),
        )
        self.reasoner = Reasoner(engine, max_depth=max_depth, eval_fn=self._eval)
        self.max_depth = max_depth

    def choose_move(self, state: GameState) -> Optional[Move]:
        return self.reasoner.choose_move(state)

    def refresh(self, evaluator):
        """Update snapshot to current learner weights."""
        self._eval.weights = list(evaluator.weights)


class ReasonerOpponent:
    """Uses the minimax reasoner with optional evaluation function."""

    def __init__(self, engine: GameEngine, max_depth: int = 4, eval_fn=None):
        self.reasoner = Reasoner(engine, max_depth=max_depth, eval_fn=eval_fn)

    def choose_move(self, state: GameState) -> Optional[Move]:
        return self.reasoner.choose_move(state)
