"""Sampling-based search for hidden-information games.

Instead of searching a single game tree (minimax), we sample N
possible worlds consistent with what we know, run shallow search
on each, and pick the move with the best average score.

This is how humans play card games: "what might they have?"
"""

from __future__ import annotations
from collections import defaultdict
import random
from typing import Optional

from engine.gdl.state import GameState
from engine.gdl.visibility import BeliefState
from engine.gdl.cards import CardGameState


class SamplingReasoner:
    """Search for hidden-information games via belief sampling.

    For each possible move:
      1. Sample N possible opponent hands
      2. For each sample, evaluate how good this move is
      3. Pick the move with the best average outcome
    """

    def __init__(self, engine, eval_fn=None, max_depth: int = 1,
                 num_samples: int = 20, opponent_model=None):
        self.engine = engine
        self.eval_fn = eval_fn
        self.max_depth = max_depth
        self.num_samples = num_samples
        self.opponent_model = opponent_model
        self.nodes_searched = 0
        self.last_depth_used = max_depth

    def choose_move(self, state: GameState):
        """Choose the best move by sampling possible hidden states."""
        moves = self.engine.legal_moves(state)
        if not moves:
            return None
        if len(moves) == 1:
            return moves[0]

        self.nodes_searched = 0
        player = state.current_player

        # Build belief state from what we can see
        if state.card_zones:
            card_state = self._to_card_game_state(state)
            belief = BeliefState(player, card_state)

            # Add constraints from opponent model if available
            if self.opponent_model:
                for constraint in self.opponent_model.get_constraints():
                    belief.add_constraint(constraint)

            num_samples = min(self.num_samples, belief.num_samples_needed())
        else:
            # No hidden info — just evaluate directly
            belief = None
            num_samples = 1

        # Score each move across samples
        move_scores = defaultdict(list)

        for _ in range(num_samples):
            # Generate a concrete state consistent with beliefs
            if belief:
                sampled_card_state = belief.sample()
                sampled_state = self._from_card_game_state(state, sampled_card_state)
            else:
                sampled_state = state

            for move in moves:
                new_state = self.engine.apply_move(sampled_state, move)
                self.nodes_searched += 1

                # Check if move leads to terminal
                result = self.engine.check_terminal(new_state)
                if result:
                    if result.result_type == "win":
                        score = 10000 if result.winner == player else -10000
                    elif result.result_type == "draw":
                        score = 0
                    else:
                        score = 0
                else:
                    # Evaluate with optional deeper search
                    score = self._evaluate(new_state, player)

                # Use move's rule_name + params as key
                move_key = (move.rule_name, tuple(sorted(move.params.items())))
                move_scores[move_key].append(score)

        # Pick move with best average score
        best_key = None
        best_avg = float('-inf')
        for key, scores in move_scores.items():
            avg = sum(scores) / len(scores)
            if avg > best_avg:
                best_avg = avg
                best_key = key

        # Find the actual move object
        for move in moves:
            key = (move.rule_name, tuple(sorted(move.params.items())))
            if key == best_key:
                return move

        return moves[0]  # fallback

    def _evaluate(self, state: GameState, player: str) -> float:
        """Evaluate a state, optionally with 1-ply lookahead."""
        if self.max_depth <= 1 or not self.eval_fn:
            # Simple evaluation
            if self.eval_fn:
                return self.eval_fn(state, player, self.engine)
            return 0.0

        # 1-ply lookahead: opponent's best response
        opp_moves = self.engine.legal_moves(state)
        if not opp_moves:
            if self.eval_fn:
                return self.eval_fn(state, player, self.engine)
            return 0.0

        worst = float('inf')
        for opp_move in opp_moves[:10]:  # cap for speed
            new_state = self.engine.apply_move(state, opp_move)
            self.nodes_searched += 1
            result = self.engine.check_terminal(new_state)
            if result:
                if result.result_type == "win":
                    score = 10000 if result.winner == player else -10000
                else:
                    score = 0
            elif self.eval_fn:
                score = self.eval_fn(new_state, player, self.engine)
            else:
                score = 0
            worst = min(worst, score)

        return worst

    def _to_card_game_state(self, state: GameState) -> CardGameState:
        """Wrap GameState's card zones into a CardGameState for BeliefState."""
        cgs = CardGameState()
        cgs.current_player = state.current_player
        cgs.turn_number = state.turn_number
        if state.card_zones:
            for name, zone in state.card_zones.items():
                cgs.zones[name] = zone
        return cgs

    def _from_card_game_state(self, original: GameState,
                               card_state: CardGameState) -> GameState:
        """Create a new GameState with sampled card zones."""
        new_state = original.copy()
        for name, zone in card_state.zones.items():
            if name in new_state.card_zones:
                new_state.card_zones[name] = zone
        return new_state
