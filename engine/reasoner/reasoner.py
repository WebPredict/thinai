"""Strategic reasoner for ThinAI.

Minimax with alpha-beta pruning. Designed for basic competency
(like a smart kid learning) rather than expert-level play.
"""

from __future__ import annotations
import math
import random
from typing import Optional

from engine.engine import GameEngine
from engine.gdl.state import GameState, Move, GameResult


class Reasoner:
    """Minimax reasoner with alpha-beta pruning."""

    def __init__(self, engine: GameEngine, max_depth: int = 6, eval_fn=None):
        self.engine = engine
        self.max_depth = max_depth
        self.eval_fn = eval_fn or default_eval
        self.nodes_searched = 0

    def choose_move(self, state: GameState) -> Optional[Move]:
        """Choose the best move for the current player."""
        moves = self.engine.legal_moves(state)
        if not moves:
            return None

        self.nodes_searched = 0
        best_move = None
        best_score = -math.inf
        alpha = -math.inf
        beta = math.inf

        # Move ordering: shuffle first (breaks ties randomly),
        # then try center-ish moves first for grid games
        random.shuffle(moves)
        moves = self._order_moves(moves, state)

        for move in moves:
            new_state = self.engine.apply_move(state, move)
            score = -self._negamax(new_state, self.max_depth - 1, -beta, -alpha)
            if score > best_score:
                best_score = score
                best_move = move
            alpha = max(alpha, score)

        return best_move

    def _negamax(self, state: GameState, depth: int, alpha: float, beta: float) -> float:
        """Negamax with alpha-beta pruning."""
        self.nodes_searched += 1

        # Terminal check
        result = self.engine.check_terminal(state)
        if result is not None:
            return self._terminal_score(result, state.current_player)

        # Depth limit
        if depth <= 0:
            return self.eval_fn(state, state.current_player, self.engine)

        moves = self.engine.legal_moves(state)
        if not moves:
            return 0.0  # No moves, no result = draw-ish

        moves = self._order_moves(moves, state)
        best = -math.inf

        for move in moves:
            new_state = self.engine.apply_move(state, move)
            score = -self._negamax(new_state, depth - 1, -beta, -alpha)
            best = max(best, score)
            alpha = max(alpha, score)
            if alpha >= beta:
                break  # Beta cutoff

        return best

    def _terminal_score(self, result: GameResult, player: str) -> float:
        """Score a terminal state from player's perspective."""
        if result.result_type == "draw":
            return 0.0
        if result.winner == player:
            return 10000.0
        return -10000.0

    def _order_moves(self, moves: list[Move], state: GameState) -> list[Move]:
        """Order moves for better alpha-beta pruning."""
        from engine.gdl.board import GridBoard, GridSpace

        if not isinstance(state.board, GridBoard):
            return moves

        center_col = state.board.cols / 2
        center_row = state.board.rows / 2

        def center_score(m):
            # Prefer moves closer to center
            for key, val in m.params.items():
                if isinstance(val, GridSpace):
                    return abs(val.col - center_col) + abs(val.row - center_row)
                if isinstance(val, int):
                    # Column-based (connect four)
                    return abs(val - center_col)
            return 0

        return sorted(moves, key=center_score)


def default_eval(state: GameState, player: str, engine: GameEngine) -> float:
    """Simple evaluation function for grid-based line games.

    Counts partial lines (2-in-a-row, 3-in-a-row) weighted by length.
    Works for tic-tac-toe and connect four.
    """
    from engine.gdl.board import GridBoard, GridSpace
    from engine.gdl.expr_eval import _line_length

    if not isinstance(state.board, GridBoard):
        return 0.0

    board = state.board
    opponent = state.opponent(player)
    score = 0.0

    for space in board.spaces:
        piece = state.get_piece(space)
        if piece is None:
            continue

        for direction in board.directions():
            length = _line_length(state, space, direction, piece.owner)
            if length >= 2:
                value = length ** 2  # quadratic weighting
                if piece.owner == player:
                    score += value
                else:
                    score -= value

    return score
