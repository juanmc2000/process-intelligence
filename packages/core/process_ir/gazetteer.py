"""Gazetteer and alias matching for deterministic entity extraction.

Dictionary-based extraction for known systems, departments, roles, controls,
workflow nouns, approval terms, exception terms, and change terms.
Supports case-insensitive matching, alias resolution, canonical IDs,
longest-span match resolution, and confidence scoring.
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from packages.core.process_ir.types import (
    ControlType,
    EntityType,
    ExtractionMethod,
)


@dataclass
class GazetteerEntry:
    canonical_id: str
    canonical_label: str
    entity_type: EntityType
    aliases: list[str] = field(default_factory=list)
    control_type: Optional[ControlType] = None


@dataclass
class GazetteerMatch:
    canonical_id: str
    canonical_label: str
    entity_type: EntityType
    matched_text: str
    span: tuple[int, int]
    confidence: float
    method: ExtractionMethod
    control_type: Optional[ControlType] = None


# --- Gazetteer dictionaries ---
# Each entry: (canonical_id, canonical_label, entity_type, [aliases], optional control_type)

_SYSTEMS: list[GazetteerEntry] = [
    GazetteerEntry(
        "system:sap", "SAP", EntityType.SYSTEM, ["sap erp", "sap system", "erp"]
    ),
    GazetteerEntry(
        "system:oracle",
        "Oracle",
        EntityType.SYSTEM,
        ["oracle erp", "oracle financials"],
    ),
    GazetteerEntry(
        "system:salesforce", "Salesforce", EntityType.SYSTEM, ["sfdc", "salesforce crm"]
    ),
    GazetteerEntry(
        "system:jira", "Jira", EntityType.SYSTEM, ["jira system", "atlassian jira"]
    ),
    GazetteerEntry(
        "system:servicenow", "ServiceNow", EntityType.SYSTEM, ["snow", "service now"]
    ),
    GazetteerEntry("system:workday", "Workday", EntityType.SYSTEM, ["workday hcm"]),
    GazetteerEntry(
        "system:sharepoint", "SharePoint", EntityType.SYSTEM, ["sharepoint site"]
    ),
    GazetteerEntry(
        "system:excel", "Excel", EntityType.SYSTEM, ["spreadsheet", "excel file"]
    ),
    GazetteerEntry(
        "system:email", "Email", EntityType.SYSTEM, ["email system", "outlook", "gmail"]
    ),
]

_DEPARTMENTS: list[GazetteerEntry] = [
    GazetteerEntry(
        "dept:finance",
        "Finance",
        EntityType.DEPARTMENT,
        ["finance team", "finance department", "finance group"],
    ),
    GazetteerEntry(
        "dept:accounting",
        "Accounting",
        EntityType.DEPARTMENT,
        ["accounting team", "accounting department"],
    ),
    GazetteerEntry(
        "dept:hr",
        "Human Resources",
        EntityType.DEPARTMENT,
        ["hr", "hr department", "human resources department"],
    ),
    GazetteerEntry(
        "dept:it",
        "IT",
        EntityType.DEPARTMENT,
        ["it department", "information technology", "it team"],
    ),
    GazetteerEntry(
        "dept:legal", "Legal", EntityType.DEPARTMENT, ["legal team", "legal department"]
    ),
    GazetteerEntry(
        "dept:compliance",
        "Compliance",
        EntityType.DEPARTMENT,
        ["compliance team", "compliance department"],
    ),
    GazetteerEntry(
        "dept:operations",
        "Operations",
        EntityType.DEPARTMENT,
        ["ops", "operations team"],
    ),
    GazetteerEntry(
        "dept:procurement",
        "Procurement",
        EntityType.DEPARTMENT,
        ["procurement team", "purchasing"],
    ),
    GazetteerEntry(
        "dept:audit", "Audit", EntityType.DEPARTMENT, ["internal audit", "audit team"]
    ),
    GazetteerEntry(
        "dept:risk",
        "Risk Management",
        EntityType.DEPARTMENT,
        ["risk team", "risk management"],
    ),
]

_ROLES: list[GazetteerEntry] = [
    GazetteerEntry(
        "role:manager", "Manager", EntityType.ROLE, ["team lead", "team leader"]
    ),
    GazetteerEntry(
        "role:finance_manager",
        "Finance Manager",
        EntityType.ROLE,
        ["finance mgr", "financial manager"],
    ),
    GazetteerEntry(
        "role:controller", "Controller", EntityType.ROLE, ["financial controller"]
    ),
    GazetteerEntry("role:cfo", "CFO", EntityType.ROLE, ["chief financial officer"]),
    GazetteerEntry(
        "role:analyst",
        "Analyst",
        EntityType.ROLE,
        ["business analyst", "financial analyst"],
    ),
    GazetteerEntry(
        "role:clerk", "Clerk", EntityType.ROLE, ["accounts clerk", "processing clerk"]
    ),
    GazetteerEntry(
        "role:auditor",
        "Auditor",
        EntityType.ROLE,
        ["internal auditor", "external auditor"],
    ),
    GazetteerEntry(
        "role:approver",
        "Approver",
        EntityType.ROLE,
        ["authorized approver", "designated approver"],
    ),
    GazetteerEntry("role:reviewer", "Reviewer", EntityType.ROLE, ["peer reviewer"]),
    GazetteerEntry("role:supervisor", "Supervisor", EntityType.ROLE, []),
    GazetteerEntry("role:director", "Director", EntityType.ROLE, []),
    GazetteerEntry("role:vp", "Vice President", EntityType.ROLE, ["vp"]),
]

_CONTROLS: list[GazetteerEntry] = [
    GazetteerEntry(
        "control:approval",
        "Approval Control",
        EntityType.CONTROL,
        ["approval process", "sign off", "sign-off", "authorization"],
        ControlType.APPROVAL_CONTROL,
    ),
    GazetteerEntry(
        "control:reconciliation",
        "Reconciliation Control",
        EntityType.CONTROL,
        ["reconcile", "reconciliation", "matched", "matching"],
        ControlType.RECONCILIATION_CONTROL,
    ),
    GazetteerEntry(
        "control:sod",
        "Segregation of Duties",
        EntityType.CONTROL,
        ["segregation of duties", "separation of duties", "dual control"],
        ControlType.SEGREGATION_OF_DUTIES,
    ),
    GazetteerEntry(
        "control:threshold",
        "Threshold Control",
        EntityType.CONTROL,
        ["threshold", "limit", "spending limit", "approval limit"],
        ControlType.THRESHOLD_CONTROL,
    ),
    GazetteerEntry(
        "control:validation",
        "Validation Control",
        EntityType.CONTROL,
        ["validation", "verified", "verification", "validated"],
        ControlType.VALIDATION_CONTROL,
    ),
    GazetteerEntry(
        "control:access",
        "Access Control",
        EntityType.CONTROL,
        ["access control", "restricted access", "permission"],
        ControlType.ACCESS_CONTROL,
    ),
    GazetteerEntry(
        "control:audit_evidence",
        "Audit Evidence",
        EntityType.CONTROL,
        ["audit trail", "audit log", "audit evidence"],
        ControlType.AUDIT_EVIDENCE,
    ),
    GazetteerEntry(
        "control:exception_review",
        "Exception Review",
        EntityType.CONTROL,
        ["exception review", "exception handling"],
        ControlType.EXCEPTION_REVIEW,
    ),
]

_ACTIONS: list[GazetteerEntry] = [
    GazetteerEntry(
        "action:approve",
        "Approve",
        EntityType.ACTION,
        ["approved", "approval", "sign off", "signed off", "authorized"],
    ),
    GazetteerEntry(
        "action:reject",
        "Reject",
        EntityType.ACTION,
        ["rejected", "rejection", "denied", "denial"],
    ),
    GazetteerEntry(
        "action:escalate", "Escalate", EntityType.ACTION, ["escalated", "escalation"]
    ),
    GazetteerEntry(
        "action:submit", "Submit", EntityType.ACTION, ["submitted", "submission"]
    ),
    GazetteerEntry(
        "action:review", "Review", EntityType.ACTION, ["reviewed", "review"]
    ),
    GazetteerEntry(
        "action:create", "Create", EntityType.ACTION, ["created", "creation"]
    ),
    GazetteerEntry(
        "action:complete",
        "Complete",
        EntityType.ACTION,
        ["completed", "completion", "finalized"],
    ),
    GazetteerEntry(
        "action:validate", "Validate", EntityType.ACTION, ["validated", "verification"]
    ),
]

_EXCEPTIONS: list[GazetteerEntry] = [
    GazetteerEntry(
        "exception:error", "Error", EntityType.EXCEPTION, ["error", "failure", "failed"]
    ),
    GazetteerEntry(
        "exception:discrepancy",
        "Discrepancy",
        EntityType.EXCEPTION,
        ["discrepancy", "mismatch", "variance"],
    ),
    GazetteerEntry(
        "exception:overdue",
        "Overdue",
        EntityType.EXCEPTION,
        ["overdue", "past due", "late"],
    ),
    GazetteerEntry(
        "exception:breach",
        "Policy Breach",
        EntityType.EXCEPTION,
        ["breach", "violation", "non-compliance"],
    ),
]

_WORKFLOW_OBJECTS: list[GazetteerEntry] = [
    GazetteerEntry("wo:invoice", "Invoice", EntityType.WORKFLOW_OBJECT, ["invoices"]),
    GazetteerEntry(
        "wo:purchase_order",
        "Purchase Order",
        EntityType.WORKFLOW_OBJECT,
        ["purchase orders", "po", "pos"],
    ),
    GazetteerEntry(
        "wo:payment",
        "Payment",
        EntityType.WORKFLOW_OBJECT,
        ["payments", "disbursement"],
    ),
    GazetteerEntry(
        "wo:journal_entry",
        "Journal Entry",
        EntityType.WORKFLOW_OBJECT,
        ["journal entries", "je"],
    ),
    GazetteerEntry(
        "wo:request",
        "Request",
        EntityType.WORKFLOW_OBJECT,
        ["requests", "service request"],
    ),
    GazetteerEntry("wo:report", "Report", EntityType.WORKFLOW_OBJECT, ["reports"]),
    GazetteerEntry(
        "wo:ticket", "Ticket", EntityType.WORKFLOW_OBJECT, ["tickets", "case", "cases"]
    ),
]


def _build_all_entries() -> list[GazetteerEntry]:
    return (
        _SYSTEMS
        + _DEPARTMENTS
        + _ROLES
        + _CONTROLS
        + _ACTIONS
        + _EXCEPTIONS
        + _WORKFLOW_OBJECTS
    )


def _compile_pattern(text: str) -> re.Pattern:
    """Compile a word-boundary pattern for case-insensitive matching."""
    escaped = re.escape(text)
    return re.compile(r"\b" + escaped + r"\b", re.IGNORECASE)


class Gazetteer:
    """Gazetteer matcher with alias support and longest-span resolution."""

    def __init__(self, entries: Optional[list[GazetteerEntry]] = None):
        if entries is None:
            entries = _build_all_entries()

        # Build (pattern, entry, is_alias) tuples sorted by pattern length desc
        # so longest match is found first
        self._patterns: list[tuple[re.Pattern, GazetteerEntry, bool]] = []
        for entry in entries:
            # Primary label
            self._patterns.append(
                (_compile_pattern(entry.canonical_label), entry, False)
            )
            # Aliases
            for alias in entry.aliases:
                self._patterns.append((_compile_pattern(alias), entry, True))

        # Sort by pattern length descending for longest-match-first
        self._patterns.sort(key=lambda t: len(t[0].pattern), reverse=True)

    def match(self, text: str) -> list[GazetteerMatch]:
        """Find all gazetteer matches in text with longest-span resolution.

        Returns non-overlapping matches, preferring longer spans when overlapping.
        """
        raw_matches: list[GazetteerMatch] = []

        for pattern, entry, is_alias in self._patterns:
            for m in pattern.finditer(text):
                confidence = 0.90 if is_alias else 0.95
                raw_matches.append(
                    GazetteerMatch(
                        canonical_id=entry.canonical_id,
                        canonical_label=entry.canonical_label,
                        entity_type=entry.entity_type,
                        matched_text=m.group(),
                        span=(m.start(), m.end()),
                        confidence=confidence,
                        method=(
                            ExtractionMethod.ALIAS
                            if is_alias
                            else ExtractionMethod.GAZETTEER
                        ),
                        control_type=entry.control_type,
                    )
                )

        return _resolve_overlaps(raw_matches)


def _resolve_overlaps(matches: list[GazetteerMatch]) -> list[GazetteerMatch]:
    """Keep only non-overlapping matches, preferring longer spans then higher confidence."""
    # Sort by span length descending, then confidence descending
    sorted_matches = sorted(
        matches,
        key=lambda m: (m.span[1] - m.span[0], m.confidence),
        reverse=True,
    )

    kept: list[GazetteerMatch] = []
    occupied: list[tuple[int, int]] = []

    for match in sorted_matches:
        start, end = match.span
        if any(
            not (end <= occ_start or start >= occ_end)
            for occ_start, occ_end in occupied
        ):
            continue
        kept.append(match)
        occupied.append((start, end))

    # Return in text order
    kept.sort(key=lambda m: m.span[0])
    return kept
