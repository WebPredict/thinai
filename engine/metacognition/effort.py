"""Effort allocation for ThinAI.

Decides how deeply to search each position based on complexity,
uncertainty, and game phase — like a player deciding when to
think harder vs. move quickly.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from engine.gdl.state import GameState
from engine.gdl.board import GridBoard, TrackBoard, CardBoard


@dataclass
class PositionAnalysis:
    """Analysis of a position's complexity and characteristics."""
    branching_factor: int  # number of legal moves
    game_phase: float  # 0.0 = opening, 1.0 = endgame
    piece_count: int  # total pieces on board
    is_card_game: bool = False  # card zone board type
    eval_spread: float = 0.0  # gap between best and worst move evals
    weight_confidence: float = 0.5  # how confident we are in evaluation weights


@dataclass
class EffortDecision:
    """The allocator's recommendation for how hard to think."""
    depth: int
    max_nodes: int
    reason: str  # human-readable explanation of the allocation


@dataclass
class EffortRecord:
    """Record of effort spent and outcome, for learning."""
    depth_used: int
    nodes_searched: int
    branching_factor: int
    game_phase: float
    outcome: float  # +1 win, 0 draw, -1 loss


class EffortAllocator:
    """Decides how much search effort to spend on each position.

    Starts with heuristic rules, then learns from experience which
    effort levels correlate with better outcomes.
    """

    def __init__(self, min_depth: int = 1, max_depth: int = 5):
        self.min_depth = min_depth
        self.max_depth = max_depth
        # Learned adjustments: maps (phase_bucket, branch_bucket) -> depth_adjustment
        self._adjustments: dict[tuple[int, int], float] = {}
        self._history: list[EffortRecord] = []
        self.total_decisions = 0

    def analyze_position(self, state: GameState, engine) -> PositionAnalysis:
        """Analyze a position's complexity characteristics."""
        moves = engine.legal_moves(state)
        branching = len(moves)

        # Estimate game phase from piece count and turn number
        all_pieces = state.all_pieces()
        piece_count = len(all_pieces)

        # Phase heuristic: use turn number relative to expected game length
        # Early turns = opening, later = endgame
        if isinstance(state.board, GridBoard):
            total_spaces = state.board.rows * state.board.cols
            fill_ratio = piece_count / total_spaces
            phase = fill_ratio  # 0.0 = empty board, 1.0 = full
        elif isinstance(state.board, TrackBoard):
            phase = min(1.0, state.turn_number / 30.0)
        else:
            phase = min(1.0, state.turn_number / 40.0)

        is_card = isinstance(state.board, CardBoard) if state.card_zones else False

        return PositionAnalysis(
            branching_factor=branching,
            game_phase=phase,
            piece_count=piece_count,
            is_card_game=is_card,
        )

    def recommend(self, state: GameState, engine, evaluator=None) -> EffortDecision:
        """Recommend search depth for this position.

        Key principle: like a smart kid, balance thinking quality against
        time cost. Don't spend 30 seconds on one move in a casual game.
        """
        self.total_decisions += 1
        analysis = self.analyze_position(state, engine)

        # Base depth from heuristics
        depth = self._heuristic_depth(analysis)

        # Apply learned adjustments
        adj = self._get_adjustment(analysis)
        depth = int(round(depth + adj))

        # Clamp to range
        depth = max(self.min_depth, min(self.max_depth, depth))

        # Cost check: estimate nodes = branching_factor ^ depth
        # Card games stay cheap; board games need depth 4+ to see threats
        max_affordable_nodes = 1500 if analysis.is_card_game else 1000
        bf = max(analysis.branching_factor, 2)
        while depth > self.min_depth:
            estimated_nodes = bf ** depth
            if estimated_nodes <= max_affordable_nodes:
                break
            depth -= 1

        max_nodes = min(max_affordable_nodes, 500 * (3 ** depth))

        reason = self._explain(analysis, depth)
        return EffortDecision(depth=depth, max_nodes=max_nodes, reason=reason)

    def _heuristic_depth(self, analysis: PositionAnalysis) -> float:
        """Base depth from position characteristics."""
        bf = analysis.branching_factor
        phase = analysis.game_phase

        # Card games: let the node budget be the natural depth constraint
        # (bf=2 can search depth 8 for 256 nodes; bf=20 only gets depth 2)
        if analysis.is_card_game:
            if bf <= 3:
                return 5.0
            elif bf <= 10:
                return 4.0  # Go Fish, Poker: see a full round of play
            else:
                return 1.5

        if bf <= 3:
            base = 5.0  # few choices: think carefully
        elif bf <= 10:
            base = 4.0  # moderate: think ahead
        elif bf <= 20:
            base = 2.0  # many choices: stay efficient
        else:
            base = 1.5  # very broad: shallow is fine

        # Endgame bonus: search deeper when few moves remain
        if phase > 0.7:
            base += 1.0
        elif phase > 0.4:
            base += 0.5

        return base

    def _get_adjustment(self, analysis: PositionAnalysis) -> float:
        """Get learned depth adjustment for this type of position."""
        key = self._bucket_key(analysis)
        return self._adjustments.get(key, 0.0)

    def _bucket_key(self, analysis: PositionAnalysis) -> tuple[int, int]:
        """Bucket position characteristics for learning."""
        phase_bucket = int(analysis.game_phase * 3)  # 0=opening, 1=mid, 2=late
        branch_bucket = min(analysis.branching_factor // 5, 4)  # 0-4
        return (phase_bucket, branch_bucket)

    def record_outcome(self, record: EffortRecord):
        """Record an effort/outcome pair for learning."""
        self._history.append(record)

    def learn_from_history(self, learning_rate: float = 0.1):
        """Adjust depth recommendations based on accumulated outcomes.

        If deeper search correlated with better outcomes for a position type,
        increase recommended depth for that type. If shallow was fine, decrease.
        """
        if not self._history:
            return

        # Group by position bucket
        buckets: dict[tuple[int, int], list[EffortRecord]] = {}
        for rec in self._history:
            key = (
                int(rec.game_phase * 3),
                min(rec.branching_factor // 5, 4),
            )
            buckets.setdefault(key, []).append(rec)

        for key, records in buckets.items():
            if len(records) < 3:
                continue  # not enough data

            # Correlate depth with outcome
            avg_depth = sum(r.depth_used for r in records) / len(records)
            avg_outcome = sum(r.outcome for r in records) / len(records)

            # If winning more with deeper search, nudge depth up
            # If winning fine with shallow, nudge down (efficiency)
            if avg_outcome > 0.3 and avg_depth <= 2:
                # Winning at shallow depth — no need to go deeper
                adj = self._adjustments.get(key, 0.0)
                self._adjustments[key] = adj - learning_rate * 0.5
            elif avg_outcome < -0.1:
                # Losing — try searching deeper
                adj = self._adjustments.get(key, 0.0)
                self._adjustments[key] = adj + learning_rate

        # Clear history after learning
        self._history.clear()

    def _explain(self, analysis: PositionAnalysis, depth: int) -> str:
        """Generate human-readable explanation of the effort decision."""
        bf = analysis.branching_factor
        phase = analysis.game_phase

        parts = []
        if bf <= 3:
            parts.append(f"only {bf} options — thinking carefully")
        elif bf > 15:
            parts.append(f"{bf} options — staying efficient")

        if phase > 0.7:
            parts.append("endgame — searching deeper")
        elif phase < 0.2:
            parts.append("opening — balanced effort")

        parts.append(f"depth {depth}")
        return "; ".join(parts)

    def stats(self) -> dict:
        """Summary statistics."""
        return {
            "total_decisions": self.total_decisions,
            "learned_adjustments": len(self._adjustments),
            "history_size": len(self._history),
            "adjustments": {
                f"phase{k[0]}_branch{k[1]}": round(v, 3)
                for k, v in self._adjustments.items()
            },
        }

    def to_dict(self) -> dict:
        return {
            "min_depth": self.min_depth,
            "max_depth": self.max_depth,
            "adjustments": {
                f"{k[0]},{k[1]}": v for k, v in self._adjustments.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EffortAllocator":
        alloc = cls(min_depth=data.get("min_depth", 1),
                    max_depth=data.get("max_depth", 5))
        for key_str, val in data.get("adjustments", {}).items():
            parts = key_str.split(",")
            alloc._adjustments[(int(parts[0]), int(parts[1]))] = val
        return alloc
