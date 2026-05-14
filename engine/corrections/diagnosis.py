"""Fault diagnosis for ThinAI corrections.

Given a CorrectionEvent, traces through the GDL rules to identify
which rule(s) are likely at fault. Uses the structured GDL format
to narrow candidates and rank them by likelihood.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from engine.corrections.detector import CorrectionEvent, CorrectionType
from engine.corrections.confidence import ConfidenceTracker


@dataclass
class DiagnosisCandidate:
    """A candidate rule that might be the source of a correction."""
    rule_name: str
    component: str  # "condition", "effect", "end_condition", "missing"
    confidence_score: float  # current confidence in this rule
    likelihood: float  # estimated likelihood this is the fault (0-1)
    reason: str  # explanation of why this is a candidate

    def to_dict(self) -> dict:
        return {
            "rule_name": self.rule_name,
            "component": self.component,
            "confidence_score": round(self.confidence_score, 4),
            "likelihood": round(self.likelihood, 4),
            "reason": self.reason,
        }


@dataclass
class Diagnosis:
    """Result of diagnosing a correction event."""
    event: CorrectionEvent
    candidates: list[DiagnosisCandidate] = field(default_factory=list)
    primary_candidate: Optional[DiagnosisCandidate] = None
    diagnosis_type: str = ""  # "rule_condition", "rule_effect", "end_condition", "missing_rule"

    def to_dict(self) -> dict:
        return {
            "event": self.event.to_dict(),
            "diagnosis_type": self.diagnosis_type,
            "primary_candidate": self.primary_candidate.to_dict() if self.primary_candidate else None,
            "all_candidates": [c.to_dict() for c in self.candidates],
        }


class FaultDiagnoser:
    """Diagnoses the source of correction events."""

    def __init__(self, gdl: dict, confidence_tracker: ConfidenceTracker):
        self.gdl = gdl
        self.confidence = confidence_tracker

    def diagnose(self, event: CorrectionEvent) -> Diagnosis:
        """Diagnose a correction event to identify the faulty rule(s)."""
        if event.correction_type == CorrectionType.ILLEGAL_MOVE:
            return self._diagnose_illegal_move(event)
        elif event.correction_type == CorrectionType.MISSING_RULE:
            return self._diagnose_missing_rule(event)
        elif event.correction_type == CorrectionType.OUTCOME_SURPRISE:
            return self._diagnose_outcome_surprise(event)
        elif event.correction_type == CorrectionType.EXPLICIT:
            return self._diagnose_explicit(event)
        else:
            return Diagnosis(event=event)

    def _diagnose_illegal_move(self, event: CorrectionEvent) -> Diagnosis:
        """Diagnose an illegal move correction.

        The system thought a move was legal, but it was rejected.
        Possible faults:
          1. The rule's conditions are too permissive (allow moves that shouldn't be)
          2. The rule's effects produce invalid state
          3. A missing condition that should restrict the move
        """
        candidates = []

        # The attempted move references a specific rule
        if event.candidate_rules:
            for rule_name in event.candidate_rules:
                rule = self._find_rule(rule_name)
                if rule is None:
                    continue

                rc = self.confidence.get(rule_name)
                score = rc.score if rc else 0.6

                # Primary suspect: the conditions are too permissive
                candidates.append(DiagnosisCandidate(
                    rule_name=rule_name,
                    component="condition",
                    confidence_score=score,
                    likelihood=0.7,
                    reason=f"Rule '{rule_name}' conditions may be too permissive, "
                           f"allowing a move that should be illegal",
                ))

                # Secondary suspect: a missing condition
                candidates.append(DiagnosisCandidate(
                    rule_name=rule_name,
                    component="missing",
                    confidence_score=score,
                    likelihood=0.3,
                    reason=f"Rule '{rule_name}' may be missing a condition "
                           f"that restricts when this move is legal",
                ))

        # Sort by likelihood (highest first), then by lowest confidence
        candidates.sort(key=lambda c: (-c.likelihood, c.confidence_score))

        return Diagnosis(
            event=event,
            candidates=candidates,
            primary_candidate=candidates[0] if candidates else None,
            diagnosis_type="rule_condition",
        )

    def _diagnose_missing_rule(self, event: CorrectionEvent) -> Diagnosis:
        """Diagnose a missing rule correction.

        The opponent made a move we don't have rules for.
        The GDL is missing a rule entirely.
        """
        candidates = []

        # Find rules with similar names or actions to the unexpected move
        if event.attempted_move:
            move_rule = event.attempted_move.rule_name
            for rule in self.gdl.get("rules", []):
                if rule["name"] == move_rule:
                    rc = self.confidence.get(rule["name"])
                    score = rc.score if rc else 0.6
                    candidates.append(DiagnosisCandidate(
                        rule_name=rule["name"],
                        component="missing",
                        confidence_score=score,
                        likelihood=0.5,
                        reason=f"Existing rule '{rule['name']}' may need expanding "
                               f"to cover this move variant",
                    ))

        # Always add a "new rule needed" candidate
        candidates.append(DiagnosisCandidate(
            rule_name="<new_rule>",
            component="missing",
            confidence_score=0.0,
            likelihood=0.6,
            reason="A new rule may need to be added to the GDL specification",
        ))

        candidates.sort(key=lambda c: (-c.likelihood, c.confidence_score))

        return Diagnosis(
            event=event,
            candidates=candidates,
            primary_candidate=candidates[0] if candidates else None,
            diagnosis_type="missing_rule",
        )

    def _diagnose_outcome_surprise(self, event: CorrectionEvent) -> Diagnosis:
        """Diagnose an outcome surprise.

        The game ended differently than expected. Either:
          1. An end condition is wrong (triggers when it shouldn't, or vice versa)
          2. The scoring/winner determination is wrong
          3. The evaluation function is misleading (not a rule fault)
        """
        candidates = []

        for i, ec in enumerate(self.gdl.get("end_conditions", [])):
            ec_name = f"end_{ec['type']}_{i}"
            rc = self.confidence.get(ec_name)
            score = rc.score if rc else 0.6

            # If the expected winner lost, the win condition may be wrong
            candidates.append(DiagnosisCandidate(
                rule_name=ec_name,
                component="end_condition",
                confidence_score=score,
                likelihood=0.5,
                reason=f"End condition '{ec['type']}' (condition: {ec.get('condition', '?')}) "
                       f"may have triggered incorrectly or uses wrong winner determination",
            ))

        # Also consider that the rules themselves cause wrong game flow
        for rule in self.gdl.get("rules", []):
            rc = self.confidence.get(rule["name"])
            score = rc.score if rc else 0.6
            # Lower-confidence rules are more likely at fault
            if score < 0.5:
                candidates.append(DiagnosisCandidate(
                    rule_name=rule["name"],
                    component="effect",
                    confidence_score=score,
                    likelihood=0.3,
                    reason=f"Low-confidence rule '{rule['name']}' effects may cause "
                           f"incorrect game state leading to wrong outcome",
                ))

        candidates.sort(key=lambda c: (-c.likelihood, c.confidence_score))

        return Diagnosis(
            event=event,
            candidates=candidates,
            primary_candidate=candidates[0] if candidates else None,
            diagnosis_type="end_condition",
        )

    def _diagnose_explicit(self, event: CorrectionEvent) -> Diagnosis:
        """Diagnose an explicit user correction.

        The user told us what's wrong. Try to match their feedback
        to specific rules.
        """
        candidates = []
        feedback = (event.feedback_text or "").lower()

        for rule in self.gdl.get("rules", []):
            rule_name = rule["name"]
            rc = self.confidence.get(rule_name)
            score = rc.score if rc else 0.6

            # Simple keyword matching: if the feedback mentions the rule name
            # or related terms, it's a candidate
            relevance = 0.0
            rule_words = rule_name.lower().replace("_", " ").split()
            for word in rule_words:
                if word in feedback:
                    relevance += 0.3

            # Check if the feedback mentions conditions or effects
            if any(word in feedback for word in ["can't", "cannot", "not allowed",
                                                   "illegal", "shouldn't"]):
                relevance += 0.2  # Likely about conditions
            if any(word in feedback for word in ["should", "actually", "instead",
                                                   "wrong", "different"]):
                relevance += 0.1  # Likely about effects

            if relevance > 0:
                candidates.append(DiagnosisCandidate(
                    rule_name=rule_name,
                    component="condition" if "not allowed" in feedback else "effect",
                    confidence_score=score,
                    likelihood=min(relevance, 0.9),
                    reason=f"User feedback may relate to rule '{rule_name}'",
                ))

        # Check end conditions too
        for i, ec in enumerate(self.gdl.get("end_conditions", [])):
            ec_name = f"end_{ec['type']}_{i}"
            if any(word in feedback for word in ["win", "lose", "draw", "end",
                                                   "over", "finish"]):
                rc = self.confidence.get(ec_name)
                score = rc.score if rc else 0.6
                candidates.append(DiagnosisCandidate(
                    rule_name=ec_name,
                    component="end_condition",
                    confidence_score=score,
                    likelihood=0.4,
                    reason=f"User feedback about game outcome may relate to "
                           f"end condition '{ec['type']}'",
                ))

        candidates.sort(key=lambda c: (-c.likelihood, c.confidence_score))

        return Diagnosis(
            event=event,
            candidates=candidates,
            primary_candidate=candidates[0] if candidates else None,
            diagnosis_type="explicit",
        )

    def _find_rule(self, rule_name: str) -> Optional[dict]:
        """Find a rule in the GDL by name."""
        for rule in self.gdl.get("rules", []):
            if rule["name"] == rule_name:
                return rule
        return None
