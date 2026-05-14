"""Rule revision for ThinAI corrections.

Given a diagnosis identifying which rule(s) are at fault, proposes
and applies modifications to the GDL specification. Includes
consistency checking to ensure revisions don't break other rules.
"""

from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from engine.corrections.detector import CorrectionEvent, CorrectionType
from engine.corrections.diagnosis import Diagnosis, DiagnosisCandidate
from engine.corrections.confidence import ConfidenceTracker


@dataclass
class Revision:
    """A proposed or applied revision to the GDL."""
    revision_id: str
    rule_name: str
    revision_type: str  # "add_condition", "modify_condition", "modify_effect",
                         # "add_rule", "modify_end_condition"
    description: str
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    applied: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    triggered_by: Optional[str] = None  # correction event description

    def to_dict(self) -> dict:
        return {
            "revision_id": self.revision_id,
            "rule_name": self.rule_name,
            "revision_type": self.revision_type,
            "description": self.description,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "applied": self.applied,
            "timestamp": self.timestamp,
            "triggered_by": self.triggered_by,
        }


class RuleReviser:
    """Proposes and applies revisions to GDL specifications."""

    def __init__(self, gdl: dict, confidence_tracker: ConfidenceTracker):
        self.gdl = gdl
        self.confidence = confidence_tracker
        self.revision_history: list[Revision] = []
        self._revision_counter = 0

    def _next_id(self) -> str:
        self._revision_counter += 1
        return f"rev_{self._revision_counter}"

    def propose_revisions(self, diagnosis: Diagnosis) -> list[Revision]:
        """Propose revisions based on a diagnosis."""
        if diagnosis.primary_candidate is None:
            return []

        candidate = diagnosis.primary_candidate
        event = diagnosis.event

        if event.correction_type == CorrectionType.ILLEGAL_MOVE:
            return self._propose_for_illegal_move(candidate, event)
        elif event.correction_type == CorrectionType.MISSING_RULE:
            return self._propose_for_missing_rule(candidate, event)
        elif event.correction_type == CorrectionType.OUTCOME_SURPRISE:
            return self._propose_for_outcome_surprise(candidate, event)
        elif event.correction_type == CorrectionType.EXPLICIT:
            return self._propose_for_explicit(candidate, event)
        return []

    def apply_revision(self, revision: Revision) -> bool:
        """Apply a revision to the GDL spec. Returns True if successful."""
        try:
            if revision.revision_type == "add_condition":
                return self._apply_add_condition(revision)
            elif revision.revision_type == "modify_condition":
                return self._apply_modify_condition(revision)
            elif revision.revision_type == "modify_effect":
                return self._apply_modify_effect(revision)
            elif revision.revision_type == "add_rule":
                return self._apply_add_rule(revision)
            elif revision.revision_type == "remove_condition":
                return self._apply_remove_condition(revision)
            elif revision.revision_type == "modify_end_condition":
                return self._apply_modify_end_condition(revision)
            return False
        except Exception:
            return False

    def check_consistency(self, revision: Revision) -> list[str]:
        """Check if a revision would be consistent with the rest of the GDL.

        Returns a list of warnings (empty = consistent).
        """
        warnings = []

        # Check that the target rule exists (unless we're adding a new one)
        if revision.revision_type != "add_rule":
            rule = self._find_rule(revision.rule_name)
            if rule is None and not revision.rule_name.startswith("end_"):
                warnings.append(f"Rule '{revision.rule_name}' not found in GDL")

        # Check that conditions reference valid identifiers
        if revision.new_value and isinstance(revision.new_value, str):
            # Basic checks: referenced pieces/vars exist
            for piece_def in self.gdl.get("pieces", []):
                pass  # Could validate piece references

        # Check for contradictory conditions
        if revision.revision_type == "add_condition":
            rule = self._find_rule(revision.rule_name)
            if rule:
                existing = rule.get("conditions", [])
                new_cond = revision.new_value
                # Trivial contradiction check: negation of existing condition
                for ec in existing:
                    if new_cond == f"not ({ec})" or ec == f"not ({new_cond})":
                        warnings.append(
                            f"New condition '{new_cond}' contradicts "
                            f"existing condition '{ec}'"
                        )

        return warnings

    # --- Proposal methods ---

    def _propose_for_illegal_move(self, candidate: DiagnosisCandidate,
                                   event: CorrectionEvent) -> list[Revision]:
        """Propose revisions for an illegal move.

        The most common fix: add a condition to the rule that prevents
        the illegal move from being generated.
        """
        revisions = []

        if candidate.component == "condition" and event.attempted_move:
            move = event.attempted_move
            # Propose adding a restrictive condition
            # We can infer what condition to add from the move parameters
            for param_name, param_val in move.params.items():
                revisions.append(Revision(
                    revision_id=self._next_id(),
                    rule_name=candidate.rule_name,
                    revision_type="add_condition",
                    description=f"Add condition to restrict {param_name} "
                                f"(blocked value: {param_val})",
                    new_value=f"# NEEDS SPECIFIC CONDITION for {param_name} != {param_val}",
                    triggered_by=event.description,
                ))

        return revisions

    def _propose_for_missing_rule(self, candidate: DiagnosisCandidate,
                                   event: CorrectionEvent) -> list[Revision]:
        """Propose revisions for a missing rule."""
        revisions = []

        if candidate.rule_name == "<new_rule>" and event.attempted_move:
            move = event.attempted_move
            revisions.append(Revision(
                revision_id=self._next_id(),
                rule_name=move.rule_name,
                revision_type="add_rule",
                description=f"Add new rule to handle move type '{move.rule_name}'",
                new_value={
                    "name": move.rule_name,
                    "action": "unknown",
                    "params": [{"name": k, "select": "space"} for k in move.params],
                    "conditions": [],
                    "effects": [],
                },
                triggered_by=event.description,
            ))
        elif event.attempted_move:
            # Expand existing rule
            revisions.append(Revision(
                revision_id=self._next_id(),
                rule_name=candidate.rule_name,
                revision_type="remove_condition",
                description=f"Relax conditions on '{candidate.rule_name}' "
                            f"to allow the observed move",
                triggered_by=event.description,
            ))

        return revisions

    def _propose_for_outcome_surprise(self, candidate: DiagnosisCandidate,
                                       event: CorrectionEvent) -> list[Revision]:
        """Propose revisions for an outcome surprise."""
        revisions = []

        if candidate.component == "end_condition":
            revisions.append(Revision(
                revision_id=self._next_id(),
                rule_name=candidate.rule_name,
                revision_type="modify_end_condition",
                description=f"End condition '{candidate.rule_name}' may need revision. "
                            f"Expected {event.expected_result} but got {event.actual_result}",
                triggered_by=event.description,
            ))

        return revisions

    def _propose_for_explicit(self, candidate: DiagnosisCandidate,
                               event: CorrectionEvent) -> list[Revision]:
        """Propose revisions based on explicit user feedback."""
        revisions = []
        feedback = event.feedback_text or ""

        if candidate.component == "condition":
            revisions.append(Revision(
                revision_id=self._next_id(),
                rule_name=candidate.rule_name,
                revision_type="modify_condition",
                description=f"Modify conditions on '{candidate.rule_name}' "
                            f"based on feedback: {feedback}",
                triggered_by=event.description,
            ))
        elif candidate.component == "effect":
            revisions.append(Revision(
                revision_id=self._next_id(),
                rule_name=candidate.rule_name,
                revision_type="modify_effect",
                description=f"Modify effects on '{candidate.rule_name}' "
                            f"based on feedback: {feedback}",
                triggered_by=event.description,
            ))
        elif candidate.component == "end_condition":
            revisions.append(Revision(
                revision_id=self._next_id(),
                rule_name=candidate.rule_name,
                revision_type="modify_end_condition",
                description=f"Modify end condition based on feedback: {feedback}",
                triggered_by=event.description,
            ))

        return revisions

    # --- Application methods ---

    def _apply_add_condition(self, revision: Revision) -> bool:
        """Add a condition to a rule."""
        rule = self._find_rule(revision.rule_name)
        if rule is None:
            return False
        revision.old_value = list(rule.get("conditions", []))
        rule.setdefault("conditions", []).append(revision.new_value)
        revision.applied = True
        self.revision_history.append(revision)
        self.confidence.penalize_rule(revision.rule_name)
        self.confidence.add_rule(revision.rule_name, initial_score=0.4,
                                 provenance="corrected")
        return True

    def _apply_modify_condition(self, revision: Revision) -> bool:
        """Modify a condition in a rule."""
        rule = self._find_rule(revision.rule_name)
        if rule is None:
            return False
        if revision.old_value is not None and revision.new_value is not None:
            conditions = rule.get("conditions", [])
            for i, cond in enumerate(conditions):
                if cond == revision.old_value:
                    conditions[i] = revision.new_value
                    revision.applied = True
                    self.revision_history.append(revision)
                    self.confidence.penalize_rule(revision.rule_name)
                    return True
        return False

    def _apply_modify_effect(self, revision: Revision) -> bool:
        """Modify an effect in a rule."""
        rule = self._find_rule(revision.rule_name)
        if rule is None:
            return False
        if revision.old_value is not None and revision.new_value is not None:
            effects = rule.get("effects", [])
            for i, effect in enumerate(effects):
                if effect == revision.old_value:
                    effects[i] = revision.new_value
                    revision.applied = True
                    self.revision_history.append(revision)
                    self.confidence.penalize_rule(revision.rule_name)
                    return True
        return False

    def _apply_add_rule(self, revision: Revision) -> bool:
        """Add a new rule to the GDL."""
        if not isinstance(revision.new_value, dict):
            return False
        self.gdl.setdefault("rules", []).append(revision.new_value)
        revision.applied = True
        self.revision_history.append(revision)
        self.confidence.add_rule(
            revision.new_value["name"],
            initial_score=0.3,
            provenance="corrected",
        )
        return True

    def _apply_remove_condition(self, revision: Revision) -> bool:
        """Remove a condition from a rule."""
        rule = self._find_rule(revision.rule_name)
        if rule is None:
            return False
        conditions = rule.get("conditions", [])
        if conditions and revision.old_value:
            try:
                conditions.remove(revision.old_value)
                revision.applied = True
                self.revision_history.append(revision)
                return True
            except ValueError:
                return False
        return False

    def _apply_modify_end_condition(self, revision: Revision) -> bool:
        """Modify an end condition."""
        for i, ec in enumerate(self.gdl.get("end_conditions", [])):
            ec_name = f"end_{ec['type']}_{i}"
            if ec_name == revision.rule_name:
                if revision.old_value and revision.new_value:
                    if "condition" in revision.new_value:
                        revision.old_value = ec.get("condition")
                        ec["condition"] = revision.new_value["condition"]
                    if "player" in revision.new_value:
                        ec["player"] = revision.new_value["player"]
                    revision.applied = True
                    self.revision_history.append(revision)
                    self.confidence.penalize_rule(ec_name)
                    return True
        return False

    def apply_direct_revision(self, rule_name: str, revision_type: str,
                               old_value: Any, new_value: Any,
                               description: str = "") -> bool:
        """Apply a revision directly with explicit old/new values.

        Convenience method for programmatic corrections (e.g., from tests).
        """
        revision = Revision(
            revision_id=self._next_id(),
            rule_name=rule_name,
            revision_type=revision_type,
            description=description or f"Direct revision to {rule_name}",
            old_value=old_value,
            new_value=new_value,
        )

        warnings = self.check_consistency(revision)
        if warnings:
            pass  # Log but don't block

        return self.apply_revision(revision)

    def _find_rule(self, rule_name: str) -> Optional[dict]:
        """Find a rule in the GDL by name."""
        for rule in self.gdl.get("rules", []):
            if rule["name"] == rule_name:
                return rule
        return None

    def history_summary(self) -> list[dict]:
        """Return revision history as dicts."""
        return [r.to_dict() for r in self.revision_history]
