"""Self-assessment for ThinAI.

The system's honest evaluation of its own competence at each game.
Tracks win rates, evaluation accuracy, learning trajectory, and
generates human-readable skill descriptions.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GameSkillProfile:
    """Self-assessment profile for a single game."""
    game_name: str
    games_played: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    recent_win_rate: float = 0.0  # over last N games
    eval_accuracy: float = 0.0  # how often predicted winner was correct
    confidence_calibration: float = 0.0  # how well-calibrated confidence is
    skill_level: str = "untrained"  # untrained, beginner, developing, competent, strong
    trend: str = "unknown"  # improving, stable, declining, unknown

    @property
    def win_rate(self) -> float:
        if self.games_played == 0:
            return 0.0
        return self.wins / self.games_played

    def to_dict(self) -> dict:
        return {
            "game_name": self.game_name,
            "games_played": self.games_played,
            "win_rate": round(self.win_rate, 3),
            "recent_win_rate": round(self.recent_win_rate, 3),
            "eval_accuracy": round(self.eval_accuracy, 3),
            "skill_level": self.skill_level,
            "trend": self.trend,
            "description": self.describe(),
        }

    def describe(self) -> str:
        """Generate honest, human-readable self-description."""
        if self.games_played == 0:
            return f"I haven't learned {self.game_name} yet."

        if self.games_played < 5:
            return (f"I've only played {self.games_played} games of {self.game_name}. "
                    f"Too early to assess my skill.")

        desc = f"{self.game_name}: "

        if self.skill_level == "strong":
            desc += f"I'm playing well — winning {self.recent_win_rate:.0%} of recent games."
        elif self.skill_level == "competent":
            desc += f"I'm reasonably competent, winning {self.recent_win_rate:.0%} recently."
        elif self.skill_level == "developing":
            desc += f"I'm still learning — winning {self.recent_win_rate:.0%} of recent games."
        elif self.skill_level == "beginner":
            desc += f"I'm struggling with this game ({self.recent_win_rate:.0%} recent win rate)."
        else:
            desc += "I haven't developed a feel for this game yet."

        if self.trend == "improving":
            desc += " I'm getting better."
        elif self.trend == "declining":
            desc += " My performance has been slipping."
        elif self.trend == "stable":
            desc += " My performance has plateaued."

        return desc


class SelfAssessor:
    """Tracks and reports the system's competence across games."""

    def __init__(self):
        self._profiles: dict[str, GameSkillProfile] = {}
        self._game_outcomes: dict[str, list[float]] = {}  # game -> list of outcomes
        self._eval_predictions: dict[str, list[tuple[float, bool]]] = {}  # game -> (predicted, correct)

    def record_game(self, game_name: str, outcome: float,
                    predicted_winner_correct: Optional[bool] = None):
        """Record a game outcome for self-assessment.

        Args:
            game_name: Name of the game
            outcome: +1 win, 0 draw, -1 loss
            predicted_winner_correct: Whether our eval predicted the right winner
        """
        self._game_outcomes.setdefault(game_name, []).append(outcome)

        if predicted_winner_correct is not None:
            self._eval_predictions.setdefault(game_name, []).append(
                (outcome, predicted_winner_correct)
            )

        self._update_profile(game_name)

    def _update_profile(self, game_name: str):
        """Recompute skill profile from accumulated data."""
        outcomes = self._game_outcomes.get(game_name, [])
        if not outcomes:
            return

        profile = self._profiles.get(game_name, GameSkillProfile(game_name=game_name))

        profile.games_played = len(outcomes)
        profile.wins = sum(1 for o in outcomes if o > 0)
        profile.losses = sum(1 for o in outcomes if o < 0)
        profile.draws = sum(1 for o in outcomes if o == 0)

        # Recent win rate (last 10 games)
        recent = outcomes[-10:]
        profile.recent_win_rate = sum(1 for o in recent if o > 0) / len(recent)

        # Trend: compare first half to second half
        if len(outcomes) >= 10:
            mid = len(outcomes) // 2
            first_half = sum(1 for o in outcomes[:mid] if o > 0) / mid
            second_half = sum(1 for o in outcomes[mid:] if o > 0) / (len(outcomes) - mid)

            if second_half > first_half + 0.1:
                profile.trend = "improving"
            elif second_half < first_half - 0.1:
                profile.trend = "declining"
            else:
                profile.trend = "stable"
        else:
            profile.trend = "unknown"

        # Eval accuracy
        preds = self._eval_predictions.get(game_name, [])
        if preds:
            correct = sum(1 for _, c in preds if c)
            profile.eval_accuracy = correct / len(preds)

        # Skill level from recent win rate
        rwr = profile.recent_win_rate
        if rwr >= 0.75:
            profile.skill_level = "strong"
        elif rwr >= 0.55:
            profile.skill_level = "competent"
        elif rwr >= 0.35:
            profile.skill_level = "developing"
        elif profile.games_played >= 5:
            profile.skill_level = "beginner"
        else:
            profile.skill_level = "untrained"

        self._profiles[game_name] = profile

    def assess(self, game_name: str) -> GameSkillProfile:
        """Get skill profile for a game."""
        return self._profiles.get(game_name, GameSkillProfile(game_name=game_name))

    def assess_all(self) -> list[GameSkillProfile]:
        """Get all skill profiles, sorted by competence."""
        return sorted(
            self._profiles.values(),
            key=lambda p: p.recent_win_rate,
            reverse=True,
        )

    def describe_all(self) -> str:
        """Generate a complete self-assessment across all games."""
        profiles = self.assess_all()
        if not profiles:
            return "I haven't learned any games yet."

        lines = ["Here's my honest assessment of my abilities:", ""]
        for p in profiles:
            lines.append(f"  {p.describe()}")

        learned = sum(1 for p in profiles if p.games_played >= 5)
        total = len(profiles)
        lines.append("")
        lines.append(f"Games with meaningful experience: {learned}/{total}")

        return "\n".join(lines)

    def summary(self) -> dict:
        return {
            "games_assessed": len(self._profiles),
            "profiles": [p.to_dict() for p in self.assess_all()],
            "overall": self.describe_all(),
        }
