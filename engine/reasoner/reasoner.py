"""Strategic reasoner for ThinAI.

Minimax with alpha-beta pruning. Designed for basic competency
(like a smart kid learning) rather than expert-level play.
"""

from __future__ import annotations
import math
import random
import time
from typing import Optional

from engine.engine import GameEngine
from engine.gdl.state import GameState, Move, GameResult


class Reasoner:
    """Minimax reasoner with alpha-beta pruning."""

    def __init__(self, engine: GameEngine, max_depth: int = 6, eval_fn=None,
                 effort_allocator=None, confidence_tracker=None,
                 time_limit: float = 4.0, use_sampling: bool = False,
                 opponent_model=None):
        self.engine = engine
        self.max_depth = max_depth
        self.eval_fn = eval_fn or default_eval
        self.effort_allocator = effort_allocator
        self.confidence_tracker = confidence_tracker
        self.time_limit = time_limit  # hard cap in seconds
        self.use_sampling = use_sampling  # only for play vs human, not training
        self.opponent_model = opponent_model
        self.nodes_searched = 0
        self.last_confidence = None  # MoveConfidence from most recent move
        self.last_depth_used = 0
        self.last_effort_reason = ""
        self.last_commentary = ""  # human-readable move explanation
        self._search_start = 0.0
        self._timed_out = False

    def choose_move(self, state: GameState) -> Optional[Move]:
        """Choose the best move for the current player."""
        moves = self.engine.legal_moves(state)
        if not moves:
            return None

        # For card games with hidden info during play, use sampling-based search
        if self.use_sampling and state.card_zones and any(
            z.visible_to == "owner" for z in state.card_zones.values()
        ):
            return self._choose_move_sampled(state, moves)

        # Determine search depth — adaptive or fixed
        if self.effort_allocator:
            decision = self.effort_allocator.recommend(state, self.engine, self.eval_fn)
            depth = decision.depth
            self.last_effort_reason = decision.reason
        else:
            depth = self.max_depth
            self.last_effort_reason = f"fixed depth {depth}"
        self.last_depth_used = depth

        self.nodes_searched = 0
        self._search_start = time.monotonic()
        self._timed_out = False
        best_move = None
        best_score = -math.inf
        second_score = -math.inf
        alpha = -math.inf
        beta = math.inf

        # Move ordering: shuffle first (breaks ties randomly),
        # then try center-ish moves first for grid games
        random.shuffle(moves)
        moves = self._order_moves(moves, state)

        for move in moves:
            # Time check — return best move found so far if over limit
            if time.monotonic() - self._search_start > self.time_limit:
                self._timed_out = True
                if best_move is None:
                    best_move = move  # at least pick something
                break

            new_state = self.engine.apply_move(state, move)
            score = -self._negamax(new_state, depth - 1, -beta, -alpha,
                                   root_depth=depth)
            if score > best_score:
                second_score = best_score
                best_score = score
                best_move = move
            elif score > second_score:
                second_score = score
            alpha = max(alpha, score)

        # Score confidence
        self.last_confidence = None
        if self.confidence_tracker and best_move:
            second = second_score if second_score > -math.inf else None
            self.last_confidence = self.confidence_tracker.score_move(
                best_score, second, depth, len(moves)
            )

        # Generate commentary
        self.last_commentary = ""
        if best_move:
            try:
                from engine.reasoner.commentary import generate_commentary
                new_state = self.engine.apply_move(state, best_move)
                self.last_commentary = generate_commentary(
                    state, new_state, best_move, self.engine,
                    eval_fn=self.eval_fn, best_score=best_score,
                    second_score=second_score, depth=depth,
                )
            except Exception:
                self.last_commentary = ""

        return best_move

    def _choose_move_sampled(self, state, moves):
        """Choose a move for hidden-info games via belief sampling."""
        from engine.reasoner.sampler import SamplingReasoner

        sampler = SamplingReasoner(
            self.engine,
            eval_fn=self.eval_fn,
            max_depth=1,
            num_samples=20,
            opponent_model=self.opponent_model,
        )
        move = sampler.choose_move(state)
        self.nodes_searched = sampler.nodes_searched
        self.last_depth_used = sampler.last_depth_used
        self.last_effort_reason = f"sampled {sampler.num_samples} worlds"

        # Generate commentary for card games
        self.last_commentary = ""
        if move:
            try:
                from engine.reasoner.commentary import generate_commentary
                new_state = self.engine.apply_move(state, move)
                self.last_commentary = generate_commentary(
                    state, new_state, move, self.engine, eval_fn=self.eval_fn,
                )
            except Exception:
                self.last_commentary = ""

        # Score confidence (simple: based on score spread)
        if self.confidence_tracker and move:
            self.last_confidence = self.confidence_tracker.score_move(
                0, None, 1, len(moves)
            )

        return move

    def _negamax(self, state: GameState, depth: int, alpha: float, beta: float,
                 root_depth: int = 0) -> float:
        """Negamax with alpha-beta pruning and selective deepening.

        At depth 1-2 from current position: consider all moves (full breadth).
        At depth 3+: only consider top K "promising" moves, scored by quick eval.
        This lets us see deeper into likely lines without exponential blowup.
        """
        self.nodes_searched += 1

        # Time check — abort if over limit
        if self._timed_out or (self.nodes_searched % 200 == 0 and
                                time.monotonic() - self._search_start > self.time_limit):
            self._timed_out = True
            return self.eval_fn(state, state.current_player, self.engine)

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

        # Selective deepening: at depth 3+ from root, prune to top K moves
        # Depth from root = root_depth - depth (how deep we've gone)
        plies_deep = root_depth - depth if root_depth > 0 else 0
        if plies_deep >= 2 and len(moves) > 8:
            # Score moves cheaply with eval, keep top K
            scored = []
            player = state.current_player
            for move in moves:
                new_state = self.engine.apply_move(state, move)
                quick_score = self.eval_fn(new_state, player, self.engine)
                scored.append((quick_score, move))
                self.nodes_searched += 1
            scored.sort(key=lambda x: x[0], reverse=True)
            # Keep more at depth 3, fewer at depth 4+
            k = 8 if plies_deep == 2 else 5
            moves = [m for _, m in scored[:k]]

        best = -math.inf

        for move in moves:
            new_state = self.engine.apply_move(state, move)
            score = -self._negamax(new_state, depth - 1, -beta, -alpha,
                                   root_depth=root_depth)
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
    Also handles track/race games by measuring position progress.
    """
    from engine.gdl.board import GridBoard, GridSpace, TrackBoard, TrackSpace
    from engine.gdl.expr_eval import _line_length

    # Track/race games: score by position progress toward finish
    if isinstance(state.board, TrackBoard):
        opponent = state.opponent(player)
        track_len = state.board.length
        my_pos = 0
        opp_pos = 0
        for space in state.board.spaces:
            for piece in state.get_pieces(space):
                if piece.owner == player:
                    my_pos = max(my_pos, space.index)
                elif piece.owner == opponent:
                    opp_pos = max(opp_pos, space.index)
        # Normalize to [-10, 10] range for consistency with grid eval
        return (my_pos - opp_pos) / max(track_len, 1) * 10.0

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
