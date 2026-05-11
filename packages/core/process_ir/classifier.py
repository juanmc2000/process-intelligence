"""Action and workflow-step classification interface.

Deterministic rule-based classifier that maps text to action classes.
Interface is future-compatible with TF-IDF + Logistic Regression replacement.
"""

import re

from packages.core.process_ir.types import (
    ActionClass,
    ActionClassification,
    ExtractionMethod,
)

# Keyword-to-action-class mapping, ordered from most to least specific.
# Each entry: (compiled_pattern, action_class, confidence)
_CLASSIFICATION_RULES: list[tuple[re.Pattern, ActionClass, float]] = [
    # Exception patterns (check before approval/validation to avoid misclassification)
    (
        re.compile(
            r"\b(?:exception|error|discrepancy|variance|issue)\s+(?:was\s+|has\s+been\s+)?(?:resolved|cleared|corrected|fixed)",
            re.IGNORECASE,
        ),
        ActionClass.EXCEPTION_RESOLVED,
        0.88,
    ),
    (
        re.compile(
            r"\b(?:exception|error|discrepancy|variance|issue)\s+(?:was\s+|has\s+been\s+)?(?:raised|flagged|identified|detected|found|reported)",
            re.IGNORECASE,
        ),
        ActionClass.EXCEPTION_RAISED,
        0.88,
    ),
    # Approval / rejection
    (
        re.compile(
            r"\b(?:approved|authorization granted|sign[- ]?off|authorized)\b",
            re.IGNORECASE,
        ),
        ActionClass.APPROVAL,
        0.85,
    ),
    (
        re.compile(r"\brequires?\s+approval\b", re.IGNORECASE),
        ActionClass.APPROVAL,
        0.80,
    ),
    (
        re.compile(r"\b(?:rejected|denied|declined|denial)\b", re.IGNORECASE),
        ActionClass.REJECTION,
        0.85,
    ),
    # Escalation
    (
        re.compile(r"\b(?:escalated|escalation|escalate)\b", re.IGNORECASE),
        ActionClass.ESCALATION,
        0.85,
    ),
    # Handoff
    (
        re.compile(
            r"\b(?:handed over|handoff|hand-off|assigned to|reassigned to|forwarded to|transferred to|sent to|routed to)\b",
            re.IGNORECASE,
        ),
        ActionClass.HANDOFF,
        0.82,
    ),
    # System entry
    (
        re.compile(
            r"\b(?:entered|recorded|logged|created|posted|uploaded|imported)\s+(?:in|into|to)\b",
            re.IGNORECASE,
        ),
        ActionClass.SYSTEM_ENTRY,
        0.82,
    ),
    # Reconciliation
    (
        re.compile(
            r"\b(?:reconciled|reconciliation|matched against|compared with)\b",
            re.IGNORECASE,
        ),
        ActionClass.RECONCILIATION,
        0.85,
    ),
    # Validation
    (
        re.compile(
            r"\b(?:validated|verification|verified|confirmed|checked)\b", re.IGNORECASE
        ),
        ActionClass.VALIDATION,
        0.82,
    ),
    # Change
    (
        re.compile(
            r"\b(?:changed|updated|migrated|reassigned|replaced)\s+from\b",
            re.IGNORECASE,
        ),
        ActionClass.CHANGE_MADE,
        0.85,
    ),
    (
        re.compile(
            r"\bnew\s+(?:control|process|system)\s+(?:added|introduced|implemented)\b",
            re.IGNORECASE,
        ),
        ActionClass.CHANGE_MADE,
        0.80,
    ),
    (
        re.compile(
            r"\b(?:process|system|control)\s+(?:changed|updated|modified|removed|replaced)\b",
            re.IGNORECASE,
        ),
        ActionClass.CHANGE_MADE,
        0.80,
    ),
    # Completion
    (
        re.compile(r"\b(?:completed|finished|closed|finalized)\b", re.IGNORECASE),
        ActionClass.COMPLETION,
        0.78,
    ),
    # Request creation
    (
        re.compile(
            r"\b(?:request\s+created|new\s+request|submitted\s+request|request\s+submitted)\b",
            re.IGNORECASE,
        ),
        ActionClass.REQUEST_CREATED,
        0.82,
    ),
]


def predict_action_class(text: str) -> ActionClassification:
    """Classify a text segment into an action class using deterministic rules.

    Returns the highest-confidence matching action class. Falls back to UNKNOWN
    if no rule matches.

    Future-compatible: this function signature supports replacement with
    TF-IDF + Logistic Regression by swapping the implementation.
    """
    best_match: ActionClassification | None = None

    for pattern, action_class, confidence in _CLASSIFICATION_RULES:
        if pattern.search(text):
            candidate = ActionClassification(
                action_class=action_class,
                confidence=confidence,
                method=ExtractionMethod.RULE,
                matched_text=text[:200],  # Truncate for storage
            )
            if best_match is None or candidate.confidence > best_match.confidence:
                best_match = candidate

    if best_match is not None:
        return best_match

    return ActionClassification(
        action_class=ActionClass.UNKNOWN,
        confidence=0.0,
        method=ExtractionMethod.RULE,
        matched_text=text[:200],
    )


def classify_sentences(text: str) -> list[ActionClassification]:
    """Classify each sentence in the text.

    Splits on sentence boundaries and classifies each non-empty segment.
    Returns only classifications with confidence > 0 (skips UNKNOWN).
    """
    # Simple sentence splitting on period, exclamation, question mark, or newline
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    results: list[ActionClassification] = []

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence or len(sentence) < 5:
            continue
        classification = predict_action_class(sentence)
        if classification.action_class != ActionClass.UNKNOWN:
            results.append(classification)

    return results
