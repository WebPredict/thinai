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


class ReasonerOpponent:
    """Uses the minimax reasoner."""

    def __init__(self, engine: GameEngine, max_depth: int = 4):
        self.reasoner = Reasoner(engine, max_depth=max_depth)

    def choose_move(self, state: GameState) -> Optional[Move]:
        return self.reasoner.choose_move(state)
