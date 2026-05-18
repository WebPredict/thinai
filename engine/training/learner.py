"""Learning runner for ThinAI.

Plays training games while collecting feature traces, then updates
the learnable evaluator's weights based on outcomes. This produces
the visible learning curve.
"""

from __future__ import annotations
import random
import time
from dataclasses import dataclass, field
from typing import Optional, Callable

from engine.engine import GameEngine
from engine.gdl.state import GameState, Move, GameResult
from engine.reasoner.reasoner import Reasoner
from engine.reasoner.evaluator import LearnableEval
from engine.training.opponents import RandomOpponent, ReasonerOpponent


@dataclass
class LearningSnapshot:
    """Per-game learning metrics."""
    game_number: int
    outcome: float  # +1 win, 0 draw, -1 loss
    num_moves: int
    duration_ms: float
    rolling_win_rate: float  # over last N games
    weights: list[float]


@dataclass
class LearningResults:
    """Complete results from a learning run."""
    game_name: str
    total_games: int
    wins: int = 0
    losses: int = 0
    draws: int = 0
    snapshots: list[LearningSnapshot] = field(default_factory=list)
    final_weights: list[float] = field(default_factory=list)
    feature_names: list[str] = field(default_factory=list)
    stopped_early: bool = False
    stop_reason: str = ""
    final_depth: int = 0

    @property
    def win_rate(self) -> float:
        return self.wins / max(self.total_games, 1)

    def win_rate_curve(self, window: int = 10) -> list[float]:
        """Rolling win rate over a sliding window."""
        outcomes = [s.outcome for s in self.snapshots]
        curve = []
        for i in range(len(outcomes)):
            start = max(0, i - window + 1)
            window_outcomes = outcomes[start:i + 1]
            wins = sum(1 for o in window_outcomes if o > 0)
            curve.append(wins / len(window_outcomes))
        return curve

    def summary(self) -> str:
        curve = self.win_rate_curve()
        early = sum(curve[:5]) / min(5, len(curve)) if curve else 0
        late = sum(curve[-5:]) / min(5, len(curve)) if curve else 0
        return (
            f"{self.game_name}: Learning over {self.total_games} games\n"
            f"  Wins: {self.wins} ({self.win_rate:.0%})\n"
            f"  Losses: {self.losses}, Draws: {self.draws}\n"
            f"  Early win rate (first 5): {early:.0%}\n"
            f"  Late win rate (last 5): {late:.0%}\n"
            f"  Improvement: {late - early:+.0%}"
        )

    def to_dict(self) -> dict:
        return {
            "game_name": self.game_name,
            "total_games": self.total_games,
            "wins": self.wins,
            "losses": self.losses,
            "draws": self.draws,
            "win_rate": self.win_rate,
            "win_rate_curve": self.win_rate_curve(),
            "feature_names": self.feature_names,
            "final_weights": self.final_weights,
            "stopped_early": self.stopped_early,
            "stop_reason": self.stop_reason,
            "final_depth": self.final_depth,
            "snapshots": [
                {
                    "game": s.game_number,
                    "outcome": s.outcome,
                    "moves": s.num_moves,
                    "rolling_win_rate": s.rolling_win_rate,
                }
                for s in self.snapshots
            ],
        }


class LearningRunner:
    """Run training games with a learnable evaluator."""

    def __init__(
        self,
        engine: GameEngine,
        evaluator: LearnableEval,
        max_depth: int = 4,
        learner_player: str = "player1",
        effort_allocator=None,
        confidence_tracker=None,
        self_assessor=None,
        gdl: dict = None,
    ):
        self.engine = engine
        self.evaluator = evaluator
        self.max_depth = max_depth
        self.learner_player = learner_player
        self.effort_allocator = effort_allocator
        self.confidence_tracker = confidence_tracker
        self._gdl = gdl
        self.self_assessor = self_assessor

    def train(
        self,
        num_games: int,
        opponent=None,
        progress_callback: Optional[Callable] = None,
    ) -> LearningResults:
        """Run training games, updating weights after each.

        Mirrors how a kid learns:
        - First games: fast, near-random exploration (build intuitions)
        - Later games: use effort allocator to decide depth per position
        - Opponent is fixed at a consistent level throughout
        """
        if opponent is None:
            # For games where default_eval is meaningless (non-line games
            # like checkers, card games), use features+priors opponent.
            # For grid games with line-based wins, default_eval works well.
            from engine.reasoner.features import get_features
            use_feature_opponent = False
            if self._gdl:
                end_conds = str(self._gdl.get("end_conditions", []))
                rules_str = str(self._gdl.get("rules", []))
                has_line_win = "line_length" in end_conds
                has_flank = "flank" in rules_str  # Reversi-style
                # default_eval counts grid lines — good for line-win and flank games
                # Everything else needs feature-based opponent
                if not has_line_win and not has_flank:
                    use_feature_opponent = True

            if use_feature_opponent:
                opp_features = get_features(self.evaluator.game_name)
                if opp_features and self._gdl:
                    opp_eval = LearnableEval(
                        self.evaluator.game_name,
                        features=opp_features,
                        gdl=self._gdl,
                    )
                    opponent = ReasonerOpponent(
                        self.engine, max_depth=self.max_depth, eval_fn=opp_eval,
                    )
                else:
                    opponent = ReasonerOpponent(self.engine, max_depth=self.max_depth)
            else:
                opponent = ReasonerOpponent(self.engine, max_depth=self.max_depth)

        # Effort allocator for training — cost-aware, adapts depth per position
        if not self.effort_allocator:
            from engine.metacognition.effort import EffortAllocator
            self.effort_allocator = EffortAllocator(min_depth=1, max_depth=self.max_depth)

        results = LearningResults(
            game_name=self.evaluator.game_name,
            total_games=num_games,
            feature_names=[f.name for f in self.evaluator.features],
        )

        recent_outcomes = []

        for i in range(num_games):
            start = time.monotonic()
            outcome, num_moves, trace = self._play_and_trace(opponent)
            duration = (time.monotonic() - start) * 1000

            # Update weights
            self.evaluator.update_weights(trace, outcome)

            # Update metacognition
            if self.confidence_tracker:
                winner = self.learner_player if outcome > 0 else (
                    "opponent" if outcome < 0 else None
                )
                self.confidence_tracker.on_game_end(winner, self.learner_player)
            if self.self_assessor:
                self.self_assessor.record_game(self.evaluator.game_name, outcome)

            # Track results
            if outcome > 0:
                results.wins += 1
            elif outcome < 0:
                results.losses += 1
            else:
                results.draws += 1

            recent_outcomes.append(outcome)
            window = recent_outcomes[-10:]
            # Count wins as 1, draws as 0.5 (holding your own is good)
            rolling_wr = sum(1 if o > 0 else 0.5 if o == 0 else 0 for o in window) / len(window)

            snapshot = LearningSnapshot(
                game_number=i + 1,
                outcome=outcome,
                num_moves=num_moves,
                duration_ms=duration,
                rolling_win_rate=rolling_wr,
                weights=list(self.evaluator.weights),
            )
            results.snapshots.append(snapshot)

            if progress_callback:
                progress_callback(snapshot, results)

            # Early stopping: consistent dominance (not just a lucky streak)
            # Need 90%+ rolling win rate AND 5 wins in a row
            if (len(recent_outcomes) >= 10
                    and rolling_wr >= 0.9
                    and all(o > 0 for o in recent_outcomes[-5:])):
                results.stopped_early = True
                results.stop_reason = f"Mastery achieved — {rolling_wr:.0%} win rate, won last 5"
                results.total_games = i + 1
                break

        results.final_weights = list(self.evaluator.weights)
        results.final_depth = getattr(self.effort_allocator, 'total_decisions', 0) and \
            self.effort_allocator.recommend(self.engine.initial_state(), self.engine).depth \
            if self.effort_allocator else self.max_depth

        # Let effort allocator learn from this training batch
        if self.effort_allocator:
            self.effort_allocator.learn_from_history()

        return results

    def _play_and_trace(self, opponent) -> tuple[float, int, list[dict]]:
        """Play one game, collecting feature traces for the learner's positions.

        Returns: (outcome, num_moves, trace)
        """
        state = self.engine.initial_state()
        trace = []
        num_moves = 0
        # Backgammon needs ~300+ moves (each die is separate), most games need < 200
        max_moves = 500 if any(r.get("chance") for r in self.engine.gdl.get("rules", [])) else 200

        reasoner = Reasoner(
            self.engine, max_depth=self.max_depth, eval_fn=self.evaluator,
            effort_allocator=self.effort_allocator,
            confidence_tracker=self.confidence_tracker,
        )

        for _ in range(max_moves):
            result = self.engine.check_terminal(state)
            if result:
                outcome = self._result_to_outcome(result)
                # Set total_moves on all trace entries
                for entry in trace:
                    entry["total_moves"] = num_moves
                return outcome, num_moves, trace

            if state.current_player == self.learner_player:
                # Learner's turn — record features and choose move
                features = self.evaluator.extract_features(state, self.learner_player)
                trace.append({
                    "features": features,
                    "move_index": num_moves,
                    "total_moves": 0,  # filled in at end
                })
                move = reasoner.choose_move(state)
            else:
                move = opponent.choose_move(state)

            if move is None:
                break

            state = self.engine.apply_move(state, move)
            num_moves += 1

        # Game didn't terminate normally
        for entry in trace:
            entry["total_moves"] = num_moves
        return 0.0, num_moves, trace

    def _result_to_outcome(self, result: GameResult) -> float:
        """Convert game result to outcome from learner's perspective."""
        if result.result_type == "draw":
            return 0.0
        if result.winner == self.learner_player:
            return 1.0
        return -1.0


def run_learning(
    game_path: str,
    num_games: int = 50,
    depth: int = 4,
    verbose: bool = True,
) -> LearningResults:
    """Convenience function: train a learnable evaluator on a game."""
    engine = GameEngine.from_file(game_path)
    evaluator = LearnableEval(engine.meta["name"])
    runner = LearningRunner(engine, evaluator, max_depth=depth)

    def progress(snapshot, results):
        if verbose and snapshot.game_number % 10 == 0:
            print(f"  Game {snapshot.game_number}: "
                  f"rolling WR={snapshot.rolling_win_rate:.0%}, "
                  f"{snapshot.duration_ms:.0f}ms")

    if verbose:
        print(f"Training {engine.meta['name']} over {num_games} games (depth={depth})...")

    results = runner.train(num_games, progress_callback=progress if verbose else None)

    if verbose:
        print(results.summary())
        print("\nLearned weights:")
        for item in evaluator.weight_summary():
            print(f"  {item['feature']:25s} {item['weight']:+.4f}  ({item['description']})")

    return results


if __name__ == "__main__":
    import sys
    import os

    games_dir = os.path.join(os.path.dirname(__file__), "..", "games", "examples")
    game_name = sys.argv[1] if len(sys.argv) > 1 else "tictactoe"
    num_games = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    depth = int(sys.argv[3]) if len(sys.argv) > 3 else 4

    game_path = os.path.join(games_dir, f"{game_name}.json")
    run_learning(game_path, num_games, depth)
