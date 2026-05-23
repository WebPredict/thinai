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
    depth: int = 1  # current search depth


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
    strategy_assessment: str = ""  # "strategic", "mostly_luck", "pure_luck"
    opponent_description: str = ""  # human-readable description of training partner
    game_replays: list = field(default_factory=list)  # recorded game state sequences for visual replay

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
            "strategy_assessment": self.strategy_assessment,
            "opponent_description": self.opponent_description,
            "game_replays": _sample_replays(self.game_replays, 5),
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
        # Fast training mode for high-branching games (Scrabble)
        # Pick randomly from top moves instead of searching
        self._use_fast_training = gdl and any(
            r.get("name") == "place_word" for r in gdl.get("rules", [])
        )
        self._cancelled = False

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
        opponent_desc = ""

        from engine.reasoner.features import get_features as _get_features

        if opponent is None:
            # High branching factor games (Scrabble): use random opponent
            if self._gdl and any(r.get("name") == "place_word" for r in self._gdl.get("rules", [])):
                opponent = RandomOpponent(self.engine)
                opponent_desc = "Plays random valid words"

        if opponent is None:
            from engine.reasoner.features import get_features
            use_feature_opponent = False
            if self._gdl:
                end_conds = str(self._gdl.get("end_conditions", []))
                rules_str = str(self._gdl.get("rules", []))
                has_line_win = "line_length" in end_conds
                has_flank = "flank" in rules_str
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
                    has_dice = any(r.get("chance") for r in self._gdl.get("rules", []))
                    if has_dice:
                        opp_depth = 1
                        opponent = ReasonerOpponent(
                            self.engine, max_depth=opp_depth, eval_fn=opp_eval,
                        )
                        opponent_desc = "Uses game intuition, 1 move ahead (dice limit deeper planning)"
                    else:
                        # Use graduated difficulty: random → self-snapshot
                        opponent = RandomOpponent(self.engine)
                        opponent_desc = "Plays random, then graduates to self-snapshot"
                else:
                    opponent = RandomOpponent(self.engine)
                    opponent_desc = "Plays random, then graduates to self-snapshot"
            else:
                # If no hand-crafted features, default_eval is too strong — use graduated difficulty
                has_hc_features = bool(_get_features(self.evaluator.game_name))
                if not has_hc_features:
                    opponent = RandomOpponent(self.engine)
                    opponent_desc = "Plays random, then graduates to self-snapshot"
                else:
                    opponent = ReasonerOpponent(self.engine, max_depth=self.max_depth)
                    opponent_desc = f"Counts lines and patterns, looks {self.max_depth} move{'s' if self.max_depth != 1 else ''} ahead"

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

        # Pre-check: is this a luck-based game? (L0 check)
        is_luck_game = _is_pure_luck_l0(self.engine, self._gdl)

        # Dice games: stay at depth 1 (can't predict future rolls, depth doesn't help)
        has_dice = self._gdl and any(r.get("chance") for r in self._gdl.get("rules", []))

        # (depth cap moved before opponent creation)

        # Progressive depth: start shallow, deepen over time
        current_depth = 1
        depth_increase_interval = 5

        # Track if opponent started as random (eligible for graduation)
        from engine.training.opponents import SnapshotOpponent
        is_random_opponent = isinstance(opponent, RandomOpponent)
        is_snapshot_opponent = False

        # Collect state traces for L2 feature discovery (first 10 games)
        l2_traces = []  # list of {"states": [GameState], "outcome": float}
        l2_done = False

        for i in range(num_games):
            # Graduate opponent: after 10 games, switch random → snapshot of self
            if is_random_opponent and i == 10 and not self._use_fast_training:
                opponent = SnapshotOpponent(self.engine, self.evaluator, max_depth=min(2, current_depth))
                opponent_desc = f"Snapshot of self, looks {min(2, current_depth)} move{'s' if min(2, current_depth) != 1 else ''} ahead"
                is_random_opponent = False
                is_snapshot_opponent = True
            elif is_snapshot_opponent and i > 0 and i % 10 == 0:
                # Refresh snapshot every 10 games
                opponent.refresh(self.evaluator)

            # Update learner's depth (opponent stays fixed)
            if self.effort_allocator:
                self.effort_allocator.max_depth = current_depth

            # Check for cancellation
            if self._cancelled:
                results.stopped_early = True
                results.stop_reason = f"Training stopped by user after {i} games"
                results.total_games = i
                break

            start = time.monotonic()
            # Record all game replays (downsampled at the end)
            should_record = not self._use_fast_training
            outcome, num_moves, trace, replay_states = self._play_and_trace(opponent, record_replay=should_record)
            if should_record and replay_states:
                results.game_replays.append({
                    "game_number": i + 1,
                    "outcome": outcome,
                    "states": replay_states,
                })
            duration = (time.monotonic() - start) * 1000

            # Time guard: if games are too slow, cap depth lower
            if duration > 5000 and current_depth > 1:  # >5s per game
                self.max_depth = min(self.max_depth, current_depth)

            # L2 feature discovery: after game 10, run correlation analysis
            # L2 feature discovery: only for games without hand-crafted features
            has_hc = bool(_get_features(self.evaluator.game_name))
            if not l2_done and i == 10 and not self._use_fast_training and not has_hc:
                l2_done = True
                try:
                    l2_traces = self._collect_state_traces(opponent, n_games=5)
                    if l2_traces:
                        from engine.reasoner.feature_discovery import discover_features_from_play
                        new_features = discover_features_from_play(self.engine, l2_traces)
                        if new_features:
                            self.evaluator.add_features(new_features)
                except Exception:
                    pass  # L2 discovery is best-effort

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
                depth=current_depth,
            )
            results.snapshots.append(snapshot)

            if progress_callback:
                progress_callback(snapshot, results)

            # Progressive depth: increase every N games
            # Skip for dice games
            if (not has_dice
                    and current_depth < self.max_depth
                    and (i + 1) % depth_increase_interval == 0):
                current_depth += 1

            # Early stopping: consistent dominance at max depth
            # Don't early-stop luck games — winning streaks are just variance
            if (not is_luck_game
                    and current_depth >= self.max_depth
                    and len(recent_outcomes) >= 10
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

        # Assess whether the game involves strategy or is luck-based
        results.strategy_assessment = _assess_strategy(self.engine, self._gdl, results)
        results.opponent_description = opponent_desc

        # Let effort allocator learn from this training batch
        if self.effort_allocator:
            self.effort_allocator.learn_from_history()

        return results

    def _play_and_trace(self, opponent, record_replay: bool = False) -> tuple[float, int, list[dict], list]:
        """Play one game, collecting feature traces for the learner's positions.

        Returns: (outcome, num_moves, trace, replay_states)
        """
        state = self.engine.initial_state()
        trace = []
        replay_states = []
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
                for entry in trace:
                    entry["total_moves"] = num_moves
                if record_replay:
                    replay_states.append({"result": result.result_type, "winner": result.winner})
                return outcome, num_moves, trace, replay_states

            if record_replay:
                try:
                    replay_states.append(_snapshot_state(state))
                except Exception:
                    pass  # best effort

            if state.current_player == self.learner_player:
                # Learner's turn — record features and choose move
                features = self.evaluator.extract_features(state, self.learner_player)
                trace.append({
                    "features": features,
                    "move_index": num_moves,
                    "total_moves": 0,  # filled in at end
                })
                if self._use_fast_training:
                    # Fast mode: moves already sorted by score from placement engine
                    # Pick from top few with slight randomness for exploration
                    import random as _rng
                    state.state_vars["_search_mode"] = True
                    moves = self.engine.legal_moves(state)
                    if moves:
                        k = min(3, len(moves))
                        move = _rng.choice(moves[:k])
                    else:
                        move = None
                else:
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
        return 0.0, num_moves, trace, replay_states

    def _collect_state_traces(self, opponent, n_games: int = 5) -> list[dict]:
        """Play quick games collecting state snapshots for L2 feature discovery."""
        import random as _rng
        traces = []
        for _ in range(n_games):
            state = self.engine.initial_state()
            states = [state.copy()]
            for _ in range(100):
                result = self.engine.check_terminal(state)
                if result:
                    outcome = 1.0 if result.winner == self.learner_player else (
                        -1.0 if result.winner else 0.0)
                    # Sample a few states (not all — keep it fast)
                    sampled = states[::max(1, len(states) // 5)]
                    traces.append({"states": sampled, "outcome": outcome})
                    break
                moves = self.engine.legal_moves(state)
                if not moves:
                    break
                state = self.engine.apply_move(state, _rng.choice(moves))
                if len(states) < 20:  # cap state collection
                    states.append(state.copy())
        return traces

    def _result_to_outcome(self, result: GameResult) -> float:
        """Convert game result to outcome from learner's perspective."""
        if result.result_type == "draw":
            return 0.0
        if result.winner == self.learner_player:
            return 1.0
        return -1.0


def _sample_replays(replays: list, count: int) -> list:
    """Downsample replays to `count` evenly spaced entries."""
    if not replays or count <= 0:
        return []
    if len(replays) <= count:
        return replays
    indices = [round(k * (len(replays) - 1) / (count - 1)) for k in range(count)]
    return [replays[i] for i in indices]


def _snapshot_state(state: GameState) -> dict:
    """Lightweight state snapshot for replay recording."""
    from engine.gdl.board import GridBoard, TrackBoard
    snapshot = {"current_player": state.current_player}

    if isinstance(state.board, GridBoard):
        snapshot["board_type"] = "grid"
        snapshot["rows"] = state.board.rows
        snapshot["cols"] = state.board.cols
        spaces = {}
        for space in state.board.spaces:
            piece = state.get_piece(space)
            if piece:
                spaces[f"{space.row},{space.col}"] = {"name": piece.name, "owner": piece.owner}
        snapshot["spaces"] = spaces
    elif isinstance(state.board, TrackBoard):
        snapshot["board_type"] = "track"
        snapshot["track_length"] = state.board.length
        spaces = {}
        for space in state.board.spaces:
            pieces = state.get_pieces(space)
            if pieces:
                spaces[str(space.index)] = [{"name": p.name, "owner": p.owner} for p in pieces]
        snapshot["spaces"] = spaces

    # Card zones — include all cards for replay (both players are AI)
    if state.card_zones:
        snapshot["board_type"] = "card_zones"
        zones = {}
        for name, zone in state.card_zones.items():
            zones[name] = {
                "size": zone.size,
                "cards": [{"rank": c.rank, "suit": c.suit, "id": c.id} for c in zone.cards],
            }
        snapshot["card_zones"] = zones

    snapshot["state_vars"] = {k: v for k, v in state.state_vars.items()
                              if isinstance(v, (str, int, float, bool)) and not k.startswith("_")}
    return snapshot


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


def _is_pure_luck_l0(engine: GameEngine, gdl: dict) -> bool:
    """L0 check: does the game have any strategic decisions?"""
    if not gdl:
        return False
    rules = gdl.get("rules", [])
    non_chance_rules = [r for r in rules if not r.get("chance")]
    if not non_chance_rules:
        return True
    # Check if non-chance rules ever offer >1 choice
    try:
        import random as _rng
        state = engine.initial_state()
        chance_rule_names = {r["name"] for r in rules if r.get("chance")}
        for _ in range(50):
            moves = engine.legal_moves(state)
            if not moves:
                break
            player_moves = [m for m in moves if m.rule_name not in chance_rule_names]
            if len(player_moves) > 1:
                return False  # found a real choice
            state = engine.apply_move(state, _rng.choice(moves))
            if engine.check_terminal(state):
                break
        return True  # never found a real choice
    except Exception:
        return False


def _assess_strategy(engine: GameEngine, gdl: dict, results: LearningResults) -> str:
    """Assess whether a game involves strategy or is luck-based.

    L0: Check GDL rules — are all player-facing moves chance-based or forced?
    L1: Check post-training signals — did weights converge? Did win rate stay ~50%?

    Returns: "strategic", "mostly_luck", or "pure_luck"
    """
    # --- L0: GDL structure check ---
    if _is_pure_luck_l0(engine, gdl):
        return "pure_luck"

    # --- L1: Post-training signal check ---
    if results.total_games >= 10:
        # Check if weights stayed near zero (nothing was predictive)
        max_weight = max(abs(w) for w in results.final_weights) if results.final_weights else 0
        weights_flat = max_weight < 0.3

        # Check if win rate stayed near 50% (no learnable advantage)
        curve = results.win_rate_curve()
        if len(curve) >= 10:
            late_wr = sum(curve[-10:]) / 10
            wr_flat = 0.35 <= late_wr <= 0.65
        else:
            wr_flat = 0.35 <= results.win_rate <= 0.65

        if weights_flat and wr_flat:
            return "mostly_luck"

    return "strategic"


if __name__ == "__main__":
    import sys
    import os

    games_dir = os.path.join(os.path.dirname(__file__), "..", "games", "examples")
    game_name = sys.argv[1] if len(sys.argv) > 1 else "tictactoe"
    num_games = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    depth = int(sys.argv[3]) if len(sys.argv) > 3 else 4

    game_path = os.path.join(games_dir, f"{game_name}.json")
    run_learning(game_path, num_games, depth)
