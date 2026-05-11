"""Regex pattern extraction for high-confidence operational patterns.

Detects approval, rejection, escalation, handoff, system-entry, temporal,
SLA, monetary threshold, and change-history phrases using compiled regex.
"""

import re
from dataclasses import dataclass
from typing import Optional

from packages.core.process_ir.types import ActionClass, ExtractionMethod


@dataclass
class PatternMatch:
    """A match from a regex pattern."""

    pattern_name: str
    action_class: ActionClass
    matched_text: str
    span: tuple[int, int]
    confidence: float
    method: ExtractionMethod = ExtractionMethod.REGEX
    # Captured groups for structured data
    actor: Optional[str] = None
    target: Optional[str] = None
    system: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    threshold: Optional[str] = None


# Patterns are (name, action_class, compiled_regex, confidence, group_names)
# group_names maps regex group names to PatternMatch fields

_APPROVAL_PATTERNS = [
    (
        "approved_by",
        ActionClass.APPROVAL,
        re.compile(
            r"\b(?:approved|authorized|signed off)\s+by\s+(?P<actor>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*|\w+(?:\s+\w+){0,3})",
            re.IGNORECASE,
        ),
        0.92,
    ),
    (
        "approval_required",
        ActionClass.APPROVAL,
        re.compile(
            r"\brequires?\s+(?:approval|authorization|sign[- ]off)",
            re.IGNORECASE,
        ),
        0.88,
    ),
    (
        "approval_granted",
        ActionClass.APPROVAL,
        re.compile(
            r"\b(?:approval|authorization)\s+(?:granted|given|obtained)",
            re.IGNORECASE,
        ),
        0.90,
    ),
]

_REJECTION_PATTERNS = [
    (
        "rejected_by",
        ActionClass.REJECTION,
        re.compile(
            r"\b(?:rejected|denied|declined)\s+by\s+(?P<actor>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*|\w+(?:\s+\w+){0,3})",
            re.IGNORECASE,
        ),
        0.92,
    ),
    (
        "rejection_reason",
        ActionClass.REJECTION,
        re.compile(
            r"\b(?:rejected|denied|declined)\s+(?:due to|because|for)",
            re.IGNORECASE,
        ),
        0.88,
    ),
]

_ESCALATION_PATTERNS = [
    (
        "escalated_to",
        ActionClass.ESCALATION,
        re.compile(
            r"\bescalated\s+to\s+(?P<target>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*|\w+(?:\s+\w+){0,3})",
            re.IGNORECASE,
        ),
        0.92,
    ),
    (
        "escalation_required",
        ActionClass.ESCALATION,
        re.compile(
            r"\brequires?\s+escalation",
            re.IGNORECASE,
        ),
        0.85,
    ),
]

_HANDOFF_PATTERNS = [
    (
        "sent_to",
        ActionClass.HANDOFF,
        re.compile(
            r"\b(?:sent|assigned|reassigned|forwarded|handed over|transferred)\s+to\s+(?P<target>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*|\w+(?:\s+\w+){0,3})",
            re.IGNORECASE,
        ),
        0.90,
    ),
    (
        "routed_to",
        ActionClass.HANDOFF,
        re.compile(
            r"\brouted\s+to\s+(?P<target>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*|\w+(?:\s+\w+){0,3})",
            re.IGNORECASE,
        ),
        0.88,
    ),
]

_SYSTEM_ENTRY_PATTERNS = [
    (
        "entered_in",
        ActionClass.SYSTEM_ENTRY,
        re.compile(
            r"\b(?:entered|recorded|logged|created|posted)\s+(?:in|into)\s+(?P<system>[A-Z][\w]*(?:\s+[\w]+){0,2})",
            re.IGNORECASE,
        ),
        0.90,
    ),
    (
        "uploaded_to",
        ActionClass.SYSTEM_ENTRY,
        re.compile(
            r"\b(?:uploaded|submitted|imported)\s+(?:to|into)\s+(?P<system>[A-Z][\w]*(?:\s+[\w]+){0,2})",
            re.IGNORECASE,
        ),
        0.88,
    ),
]

_RECONCILIATION_PATTERNS = [
    (
        "reconciled_against",
        ActionClass.RECONCILIATION,
        re.compile(
            r"\b(?:reconciled|matched|compared)\s+(?:against|with|to)\s+(?P<system>[A-Z][\w]*(?:\s+[\w]+){0,2})",
            re.IGNORECASE,
        ),
        0.90,
    ),
]

_CHANGE_PATTERNS = [
    (
        "changed_from_to",
        ActionClass.CHANGE_MADE,
        re.compile(
            r"\b(?:changed|updated|migrated|reassigned|moved)\s+from\s+(?P<old_value>[^.;]{1,60}?)\s+to\s+(?P<new_value>[^.;]{1,60})",
            re.IGNORECASE,
        ),
        0.90,
    ),
    (
        "replaced_with",
        ActionClass.CHANGE_MADE,
        re.compile(
            r"\b(?P<old_value>[A-Z][\w]*(?:\s+[\w]+){0,3})\s+(?:replaced|substituted)\s+(?:by|with)\s+(?P<new_value>[A-Z][\w]*(?:\s+[\w]+){0,3})",
            re.IGNORECASE,
        ),
        0.88,
    ),
    (
        "new_control_added",
        ActionClass.CHANGE_MADE,
        re.compile(
            r"\b(?:new|additional)\s+(?:control|check|validation)\s+(?:added|introduced|implemented)",
            re.IGNORECASE,
        ),
        0.85,
    ),
    (
        "control_removed",
        ActionClass.CHANGE_MADE,
        re.compile(
            r"\b(?:control|check|validation)\s+(?:removed|eliminated|deprecated)",
            re.IGNORECASE,
        ),
        0.85,
    ),
    (
        "process_changed",
        ActionClass.CHANGE_MADE,
        re.compile(
            r"\bprocess\s+(?:changed|updated|modified|revised|redesigned)",
            re.IGNORECASE,
        ),
        0.85,
    ),
]

_THRESHOLD_PATTERNS = [
    (
        "approval_above_amount",
        ActionClass.APPROVAL,
        re.compile(
            r"\brequires?\s+approval\s+(?:above|over|exceeding)\s+(?P<threshold>\$?[\d,]+(?:\.\d{2})?)",
            re.IGNORECASE,
        ),
        0.92,
    ),
    (
        "threshold_amount",
        ActionClass.VALIDATION,
        re.compile(
            r"\b(?:threshold|limit)\s+(?:of|is|at|set to)\s+(?P<threshold>\$?[\d,]+(?:\.\d{2})?)",
            re.IGNORECASE,
        ),
        0.88,
    ),
]

_EXCEPTION_PATTERNS = [
    (
        "exception_raised",
        ActionClass.EXCEPTION_RAISED,
        re.compile(
            r"\b(?:exception|error|discrepancy|variance|issue)\s+(?:was\s+|has\s+been\s+)?(?:raised|flagged|identified|detected|found|reported)",
            re.IGNORECASE,
        ),
        0.88,
    ),
    (
        "exception_resolved",
        ActionClass.EXCEPTION_RESOLVED,
        re.compile(
            r"\b(?:exception|error|discrepancy|variance|issue)\s+(?:was\s+|has\s+been\s+)?(?:resolved|cleared|corrected|fixed)",
            re.IGNORECASE,
        ),
        0.88,
    ),
]

_VALIDATION_PATTERNS = [
    (
        "validated_by",
        ActionClass.VALIDATION,
        re.compile(
            r"\b(?:validated|verified|checked|confirmed)\s+by\s+(?P<actor>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*|\w+(?:\s+\w+){0,3})",
            re.IGNORECASE,
        ),
        0.90,
    ),
]

_COMPLETION_PATTERNS = [
    (
        "process_completed",
        ActionClass.COMPLETION,
        re.compile(
            r"\b(?:process|workflow|task|request)\s+(?:completed|finished|closed|finalized)",
            re.IGNORECASE,
        ),
        0.88,
    ),
]

ALL_PATTERNS = (
    _APPROVAL_PATTERNS
    + _REJECTION_PATTERNS
    + _ESCALATION_PATTERNS
    + _HANDOFF_PATTERNS
    + _SYSTEM_ENTRY_PATTERNS
    + _RECONCILIATION_PATTERNS
    + _CHANGE_PATTERNS
    + _THRESHOLD_PATTERNS
    + _EXCEPTION_PATTERNS
    + _VALIDATION_PATTERNS
    + _COMPLETION_PATTERNS
)


def extract_patterns(text: str) -> list[PatternMatch]:
    """Run all regex patterns against text and return matches."""
    results: list[PatternMatch] = []

    for name, action_class, pattern, confidence in ALL_PATTERNS:
        for m in pattern.finditer(text):
            groups = m.groupdict()
            results.append(
                PatternMatch(
                    pattern_name=name,
                    action_class=action_class,
                    matched_text=m.group(),
                    span=(m.start(), m.end()),
                    confidence=confidence,
                    actor=_clean_capture(groups.get("actor")),
                    target=_clean_capture(groups.get("target")),
                    system=_clean_capture(groups.get("system")),
                    old_value=_clean_capture(groups.get("old_value")),
                    new_value=_clean_capture(groups.get("new_value")),
                    threshold=_clean_capture(groups.get("threshold")),
                )
            )

    return results


def _clean_capture(value: Optional[str]) -> Optional[str]:
    """Strip whitespace from a captured group value."""
    if value is None:
        return None
    return value.strip()
