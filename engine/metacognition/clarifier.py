"""Clarification questions for ThinAI.

When the system encounters ambiguity or uncertainty, it generates
questions rather than guessing. This applies during rule parsing
(ambiguous rules) and during play (confusing positions).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class ClarificationUrgency(Enum):
    LOW = "low"  # nice to know
    MEDIUM = "medium"  # would affect play quality
    HIGH = "high"  # can't proceed confidently without answer


@dataclass
class ClarificationQuestion:
    """A question the system wants to ask."""
    question_text: str
    context: str  # what triggered the question
    urgency: ClarificationUrgency = ClarificationUrgency.MEDIUM
    suggested_answers: list[str] = field(default_factory=list)
    category: str = "rules"  # "rules", "strategy", "ambiguity"
    resolved: bool = False
    answer: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "question": self.question_text,
            "context": self.context,
            "urgency": self.urgency.value,
            "suggested_answers": self.suggested_answers,
            "category": self.category,
            "resolved": self.resolved,
            "answer": self.answer,
        }


class Clarifier:
    """Detects ambiguities and generates clarification questions."""

    def __init__(self):
        self.questions: list[ClarificationQuestion] = []

    def check_rule_gaps(self, gdl: dict) -> list[ClarificationQuestion]:
        """Analyze a GDL spec for potential ambiguities or gaps.

        Looks for common issues: missing end conditions, unclear
        turn order, unhandled edge cases.
        """
        questions = []

        rules = gdl.get("rules", [])
        end_conditions = gdl.get("end_conditions", [])
        meta = gdl.get("meta", {})

        # Check: no draw condition
        has_draw = any(ec["type"] == "draw" for ec in end_conditions)
        has_win = any(ec["type"] == "win" for ec in end_conditions)

        if has_win and not has_draw:
            questions.append(ClarificationQuestion(
                question_text="What happens if no player can win? Is it a draw?",
                context="The rules specify a win condition but no draw condition.",
                urgency=ClarificationUrgency.MEDIUM,
                suggested_answers=["Yes, it's a draw", "The game continues until someone wins"],
                category="rules",
            ))

        # Check: no rules defined
        if not rules:
            questions.append(ClarificationQuestion(
                question_text="No move rules are defined. How do players take turns?",
                context="The GDL specification has no rules.",
                urgency=ClarificationUrgency.HIGH,
                category="rules",
            ))

        # Check: conditional turn order without turn rule
        if meta.get("turn_order") == "conditional" and "turn_rule" not in meta:
            questions.append(ClarificationQuestion(
                question_text="Turn order is marked as conditional, but no turn rule is specified. "
                              "How is the next player determined?",
                context="Conditional turn order requires a turn_rule.",
                urgency=ClarificationUrgency.HIGH,
                category="rules",
            ))

        # Check: rules with no conditions (anything goes?)
        for rule in rules:
            if not rule.get("conditions"):
                questions.append(ClarificationQuestion(
                    question_text=f"Rule '{rule['name']}' has no conditions. "
                                  f"Is this move always available?",
                    context=f"Rule '{rule['name']}' can be used at any time.",
                    urgency=ClarificationUrgency.LOW,
                    suggested_answers=["Yes, always available", "There should be restrictions"],
                    category="rules",
                ))

        # Check: board without regions on track games
        board = gdl.get("board", {})
        if board.get("type") == "track" and not board.get("regions"):
            if any("region" in str(r) for r in rules):
                questions.append(ClarificationQuestion(
                    question_text="Rules reference regions but no regions are defined on the board.",
                    context="Region references in rules require board regions.",
                    urgency=ClarificationUrgency.HIGH,
                    category="rules",
                ))

        self.questions.extend(questions)
        return questions

    def check_play_confusion(self, confidence_level: float,
                              game_name: str) -> Optional[ClarificationQuestion]:
        """During play, check if the system is confused enough to ask.

        Only generates a question when confidence is very low,
        suggesting the system doesn't understand what's happening.
        """
        if confidence_level >= 0.3:
            return None  # confident enough to continue

        q = ClarificationQuestion(
            question_text=f"I'm very unsure about my move in {game_name}. "
                          f"Am I applying the rules correctly?",
            context=f"Decision confidence is only {confidence_level:.0%}.",
            urgency=ClarificationUrgency.MEDIUM,
            suggested_answers=["Yes, keep playing", "Let me explain the rule"],
            category="strategy",
        )
        self.questions.append(q)
        return q

    def resolve(self, index: int, answer: str):
        """Mark a question as resolved with an answer."""
        if 0 <= index < len(self.questions):
            self.questions[index].resolved = True
            self.questions[index].answer = answer

    @property
    def unresolved(self) -> list[ClarificationQuestion]:
        return [q for q in self.questions if not q.resolved]

    @property
    def high_urgency_unresolved(self) -> list[ClarificationQuestion]:
        return [q for q in self.unresolved
                if q.urgency == ClarificationUrgency.HIGH]

    def summary(self) -> dict:
        return {
            "total_questions": len(self.questions),
            "unresolved": len(self.unresolved),
            "high_urgency": len(self.high_urgency_unresolved),
            "questions": [q.to_dict() for q in self.questions],
        }
