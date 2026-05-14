"""Decision confidence for ThinAI.

Scores each move with a calibrated confidence estimate — how sure
the system is that this is the right move. Distinct from Phase 3's
rule-level confidence; this is about individual decisions.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import math


@dataclass
class MoveConfidence:
    """Confidence assessment for a chosen move."""
    raw_score: float  # best move's evaluation score
    gap_to_second: float  # score difference to second-best move
    depth_used: int  # how deep we searched
    branching_factor: int  # how many moves were available
    calibrated: float = 0.5  # calibrated probability (0-1) that this move is correct

    @property
    def level(self) -> str:
        """Human-readable confidence level."""
        if self.calibrated >= 0.85:
            return "very confident"
        if self.calibrated >= 0.65:
            return "fairly confident"
        if self.calibrated >= 0.45:
            return "uncertain"
        if self.calibrated >= 0.25:
            return "guessing"
        return "very unsure"

    def to_dict(self) -> dict:
        return {
            "raw_score": round(self.raw_score, 3),
            "gap_to_second": round(self.gap_to_second, 3),
            "depth_used": self.depth_used,
            "branching_factor": self.branching_factor,
            "calibrated": round(self.calibrated, 3),
            "level": self.level,
        }


@dataclass
class ConfidencePrediction:
    """A prediction to be verified later for calibration."""
    move_number: int
    predicted_confidence: float
    was_correct: Optional[bool] = None  # filled in after game ends


class DecisionConfidenceTracker:
    """Tracks and calibrates decision confidence across games.

    The key insight: raw confidence features (score gap, depth stability)
    need to be calibrated against actual outcomes to be meaningful.
    "80% confident" should mean correct ~80% of the time.
    """

    def __init__(self):
        # Calibration bins: maps confidence_bucket -> (correct_count, total_count)
        self._calibration: dict[int, tuple[int, int]] = {}
        # Predictions from current game, verified at end
        self._current_predictions: list[ConfidencePrediction] = []
        self.total_moves_scored = 0

    def score_move(self, best_score: float, second_score: Optional[float],
                   depth: int, branching: int) -> MoveConfidence:
        """Score confidence for a move choice.

        Args:
            best_score: Evaluation of the chosen move
            second_score: Evaluation of the second-best move (None if only one move)
            depth: Search depth used
            branching: Number of legal moves available
        """
        self.total_moves_scored += 1

        # Gap to second-best move
        if second_score is not None:
            gap = best_score - second_score
        else:
            gap = abs(best_score)  # only one move — confidence from eval magnitude

        # Raw confidence features → uncalibrated confidence
        raw_conf = self._raw_confidence(gap, depth, branching)

        # Apply calibration
        calibrated = self._calibrate(raw_conf)

        mc = MoveConfidence(
            raw_score=best_score,
            gap_to_second=gap,
            depth_used=depth,
            branching_factor=branching,
            calibrated=calibrated,
        )

        # Record prediction for later calibration
        self._current_predictions.append(ConfidencePrediction(
            move_number=self.total_moves_scored,
            predicted_confidence=calibrated,
        ))

        return mc

    def _raw_confidence(self, gap: float, depth: int, branching: int) -> float:
        """Compute raw (uncalibrated) confidence from move features."""
        # Large gap between best and second → high confidence
        # Sigmoid-shaped: small gaps → ~0.5, large gaps → ~1.0
        gap_factor = 1.0 / (1.0 + math.exp(-gap * 0.5))

        # Deeper search → more confidence (diminishing returns)
        depth_factor = min(1.0, 0.4 + depth * 0.15)

        # Fewer branches → more confident we found the best
        branch_factor = 1.0 / (1.0 + math.log1p(branching) * 0.3)

        # Weighted combination
        raw = 0.5 * gap_factor + 0.3 * depth_factor + 0.2 * branch_factor
        return max(0.0, min(1.0, raw))

    def _calibrate(self, raw: float) -> float:
        """Apply calibration curve to raw confidence."""
        bucket = self._bucket(raw)
        cal_data = self._calibration.get(bucket)

        if cal_data is None or cal_data[1] < 5:
            # Not enough data — return raw with slight regression to mean
            return 0.3 + raw * 0.4  # compress toward 0.5

        correct, total = cal_data
        # Blend calibrated frequency with raw estimate
        empirical = correct / total
        # Weight empirical more as we get more data
        weight = min(0.8, cal_data[1] / 50.0)
        return raw * (1 - weight) + empirical * weight

    def on_game_end(self, winner: Optional[str], our_player: str):
        """Update calibration after a game ends.

        Marks all predictions from this game as correct/incorrect
        and updates the calibration curve.
        """
        won = winner == our_player

        for pred in self._current_predictions:
            pred.was_correct = won  # simplified: all moves in a winning game are "correct"
            bucket = self._bucket(pred.predicted_confidence)
            correct, total = self._calibration.get(bucket, (0, 0))
            if pred.was_correct:
                correct += 1
            self._calibration[bucket] = (correct, total + 1)

        self._current_predictions.clear()

    def _bucket(self, confidence: float) -> int:
        """Map confidence to a calibration bucket (0-9)."""
        return min(9, int(confidence * 10))

    def calibration_report(self) -> list[dict]:
        """Report calibration quality: predicted vs actual accuracy."""
        report = []
        for bucket in range(10):
            data = self._calibration.get(bucket)
            if data and data[1] > 0:
                correct, total = data
                predicted = (bucket + 0.5) / 10.0
                actual = correct / total
                report.append({
                    "predicted": round(predicted, 2),
                    "actual": round(actual, 3),
                    "count": total,
                    "gap": round(abs(predicted - actual), 3),
                })
        return report

    def stats(self) -> dict:
        return {
            "total_moves_scored": self.total_moves_scored,
            "calibration_buckets": len(self._calibration),
            "calibration": self.calibration_report(),
        }
