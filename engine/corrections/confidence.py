"""Confidence tracking for GDL rules.

Each rule in a GDL spec gets a confidence score that reflects how
reliable it appears to be. Confidence is updated based on:
  - Successful play (rules work as expected) → confidence increases
  - Corrections triggered → confidence on the faulty rule decreases
  - Revisions applied → new rules start at lower confidence

Scores range from 0.0 (completely untrusted) to 1.0 (fully confirmed).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class RuleConfidence:
    """Confidence metadata for a single GDL rule."""
    rule_name: str
    score: float = 0.6  # Initial confidence: moderate
    confirmations: int = 0  # Successful uses
    corrections: int = 0  # Times this rule was corrected
    last_updated: Optional[str] = None
    provenance: str = "parsed"  # "parsed", "corrected", "inferred"

    def confirm(self, amount: float = 0.02):
        """Increase confidence after successful use."""
        self.confirmations += 1
        self.score = min(1.0, self.score + amount)
        self.last_updated = datetime.now().isoformat()

    def penalize(self, amount: float = 0.15):
        """Decrease confidence after a correction event."""
        self.corrections += 1
        self.score = max(0.0, self.score - amount)
        self.last_updated = datetime.now().isoformat()

    def reset(self, new_score: float = 0.4, provenance: str = "corrected"):
        """Reset confidence after a rule revision."""
        self.score = new_score
        self.provenance = provenance
        self.last_updated = datetime.now().isoformat()

    @property
    def is_trusted(self) -> bool:
        """Whether this rule is considered reliable."""
        return self.score >= 0.5

    @property
    def is_suspect(self) -> bool:
        """Whether this rule has low enough confidence to warrant scrutiny."""
        return self.score < 0.3

    def to_dict(self) -> dict:
        return {
            "rule_name": self.rule_name,
            "score": round(self.score, 4),
            "confirmations": self.confirmations,
            "corrections": self.corrections,
            "last_updated": self.last_updated,
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RuleConfidence":
        return cls(
            rule_name=data["rule_name"],
            score=data["score"],
            confirmations=data.get("confirmations", 0),
            corrections=data.get("corrections", 0),
            last_updated=data.get("last_updated"),
            provenance=data.get("provenance", "parsed"),
        )


class ConfidenceTracker:
    """Tracks confidence scores for all rules in a GDL spec."""

    def __init__(self, gdl: dict):
        self._scores: dict[str, RuleConfidence] = {}
        # Initialize from GDL rules
        for rule in gdl.get("rules", []):
            name = rule["name"]
            self._scores[name] = RuleConfidence(rule_name=name)
        # Also track end conditions
        for i, ec in enumerate(gdl.get("end_conditions", [])):
            name = f"end_{ec['type']}_{i}"
            self._scores[name] = RuleConfidence(rule_name=name)

    def get(self, rule_name: str) -> Optional[RuleConfidence]:
        """Get confidence for a rule by name."""
        return self._scores.get(rule_name)

    def confirm_rule(self, rule_name: str):
        """Mark a rule as successfully used."""
        if rule_name in self._scores:
            self._scores[rule_name].confirm()

    def penalize_rule(self, rule_name: str):
        """Decrease confidence for a rule that triggered a correction."""
        if rule_name in self._scores:
            self._scores[rule_name].penalize()

    def confirm_all_rules(self):
        """Confirm all rules after a successful game completion."""
        for rc in self._scores.values():
            rc.confirm(amount=0.01)

    def add_rule(self, rule_name: str, initial_score: float = 0.4,
                 provenance: str = "corrected"):
        """Add tracking for a new or revised rule."""
        self._scores[rule_name] = RuleConfidence(
            rule_name=rule_name,
            score=initial_score,
            provenance=provenance,
        )

    def remove_rule(self, rule_name: str):
        """Stop tracking a removed rule."""
        self._scores.pop(rule_name, None)

    @property
    def suspect_rules(self) -> list[RuleConfidence]:
        """Rules with low confidence that may need correction."""
        return [rc for rc in self._scores.values() if rc.is_suspect]

    @property
    def all_scores(self) -> dict[str, RuleConfidence]:
        return dict(self._scores)

    def summary(self) -> list[dict]:
        """Summary of all rule confidences, sorted by score ascending."""
        return sorted(
            [rc.to_dict() for rc in self._scores.values()],
            key=lambda x: x["score"],
        )

    def to_dict(self) -> dict:
        return {name: rc.to_dict() for name, rc in self._scores.items()}

    @classmethod
    def from_dict(cls, data: dict, gdl: dict) -> "ConfidenceTracker":
        tracker = cls(gdl)
        for name, rc_data in data.items():
            tracker._scores[name] = RuleConfidence.from_dict(rc_data)
        return tracker
