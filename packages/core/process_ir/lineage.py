"""Process lineage and timeline engine.

Reconstructs workflow history from a collection of ProcessIR instances and their
associated ChangeEvent records.  Produces version chains, supersession detection,
timeline summaries, and chronological event sequences.

All logic is purely algorithmic — no database, API, storage, or LLM dependencies.
Lineage is inferred deterministically from ProcessIR content and evidence metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from packages.core.schemas.process_ir import ChangeEvent, EvidenceRef, ProcessIR


# ---------------------------------------------------------------------------
# Change categorisation helpers
# ---------------------------------------------------------------------------

# Keywords used to classify change events into structural categories.
_ROLE_CHANGE_KEYWORDS = {
    "role",
    "person",
    "owner",
    "manager",
    "responsible",
    "assigned",
}
_SYSTEM_CHANGE_KEYWORDS = {
    "system",
    "platform",
    "application",
    "software",
    "tool",
    "erp",
    "crm",
}
_CONTROL_CHANGE_KEYWORDS = {
    "control",
    "approval",
    "limit",
    "threshold",
    "policy",
    "sod",
}
_STEP_CHANGE_KEYWORDS = {"step", "workflow", "process", "activity", "task", "stage"}


class ChangeCategory(str, Enum):
    """High-level category of a process change event."""

    ROLE_CHANGE = "role_change"
    SYSTEM_MIGRATION = "system_migration"
    CONTROL_CHANGE = "control_change"
    WORKFLOW_STEP_CHANGE = "workflow_step_change"
    APPROVAL_CHANGE = "approval_change"
    GENERAL = "general"


def _classify_change(event: ChangeEvent) -> ChangeCategory:
    """Classify a ChangeEvent into a ChangeCategory based on keyword matching."""
    text = f"{event.name} {event.description or ''}".lower()
    if "approval" in text:
        return ChangeCategory.APPROVAL_CHANGE
    if any(k in text for k in _ROLE_CHANGE_KEYWORDS):
        return ChangeCategory.ROLE_CHANGE
    if any(k in text for k in _SYSTEM_CHANGE_KEYWORDS):
        return ChangeCategory.SYSTEM_MIGRATION
    if any(k in text for k in _CONTROL_CHANGE_KEYWORDS):
        return ChangeCategory.CONTROL_CHANGE
    if any(k in text for k in _STEP_CHANGE_KEYWORDS):
        return ChangeCategory.WORKFLOW_STEP_CHANGE
    return ChangeCategory.GENERAL


# ---------------------------------------------------------------------------
# Timeline event
# ---------------------------------------------------------------------------


@dataclass
class TimelineEvent:
    """A single chronological event in a process timeline."""

    event_id: str
    # Human-readable description of what changed
    description: str
    category: ChangeCategory
    # Source ProcessIR id that contains this change event
    process_id: str
    # Evidence references from the underlying ChangeEvent
    evidence_refs: list[EvidenceRef]
    # Extracted old/new values when available (from 'changed from X to Y' events)
    from_value: Optional[str] = None
    to_value: Optional[str] = None
    # Confidence: inherited from extraction if available; default 1.0 for explicit facts
    confidence: float = 1.0


# ---------------------------------------------------------------------------
# Process version
# ---------------------------------------------------------------------------


@dataclass
class ProcessVersion:
    """A snapshot of a process at a point in time (one ProcessIR instance)."""

    process_id: str
    # Ordered list of change events found in this version
    changes: list[TimelineEvent]
    # Version sequence number within a lineage chain (1 = oldest)
    version_number: int = 1
    # ID of the version this supersedes (None for the root version)
    supersedes: Optional[str] = None
    # Whether this version appears to have been superseded by a later version
    is_superseded: bool = False
    # Summary of structural dimensions (step count, role count, etc.)
    step_count: int = 0
    role_count: int = 0
    system_count: int = 0
    control_count: int = 0


def _build_version(
    process_ir: ProcessIR,
    version_number: int,
    supersedes: Optional[str] = None,
) -> ProcessVersion:
    """Build a ProcessVersion snapshot from a ProcessIR instance."""
    changes = [
        _change_event_to_timeline(ev, process_ir.id) for ev in process_ir.change_events
    ]
    return ProcessVersion(
        process_id=process_ir.id,
        changes=changes,
        version_number=version_number,
        supersedes=supersedes,
        step_count=len(process_ir.workflow_steps),
        role_count=len(process_ir.roles),
        system_count=len(process_ir.system_touchpoints),
        control_count=len(process_ir.controls),
    )


def _change_event_to_timeline(event: ChangeEvent, process_id: str) -> TimelineEvent:
    """Convert a ProcessIR ChangeEvent into a TimelineEvent."""
    category = _classify_change(event)
    # Attempt to parse 'from X to Y' from the name or description
    from_val, to_val = _extract_from_to(event)
    return TimelineEvent(
        event_id=event.id,
        description=event.name,
        category=category,
        process_id=process_id,
        evidence_refs=event.evidence_refs,
        from_value=from_val,
        to_value=to_val,
    )


def _extract_from_to(event: ChangeEvent) -> tuple[Optional[str], Optional[str]]:
    """Try to extract old/new values from 'Change: X → Y' style names."""
    text = event.name
    if "→" in text:
        # Matches pattern: "Change: <old> → <new>"
        parts = text.split("→", 1)
        old = parts[0].replace("Change:", "").strip()
        new = parts[1].strip()
        return old or None, new or None
    return None, None


# ---------------------------------------------------------------------------
# Lineage chain
# ---------------------------------------------------------------------------


@dataclass
class LineageChain:
    """An ordered chain of ProcessVersions representing workflow evolution.

    Versions are ordered oldest-first (version_number ascending).
    """

    chain_id: str
    versions: list[ProcessVersion]
    # Flat list of all timeline events across all versions, in order
    timeline: list[TimelineEvent]
    # Summary of the structural delta from first to last version
    summary: str
    # True when any version has ambiguous supersession (multiple successors)
    has_ambiguous_lineage: bool = False
    ambiguity_notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Supersession detection
# ---------------------------------------------------------------------------


def _detect_supersession(versions: list[ProcessVersion]) -> list[ProcessVersion]:
    """Mark versions as superseded when a later version references them.

    A version is considered superseded when another version's ``supersedes``
    field points to it.  This is a deterministic structural check.
    """
    superseded_ids = {v.supersedes for v in versions if v.supersedes}
    for v in versions:
        if v.process_id in superseded_ids:
            v.is_superseded = True
    return versions


def _check_ambiguous_supersession(
    versions: list[ProcessVersion],
) -> tuple[bool, list[str]]:
    """Flag ambiguous lineage when multiple versions supersede the same process."""
    from collections import Counter

    counts = Counter(v.supersedes for v in versions if v.supersedes)
    conflicts = [pid for pid, cnt in counts.items() if cnt > 1]
    notes = [
        f"Process '{pid}' is superseded by multiple versions — lineage is ambiguous."
        for pid in conflicts
    ]
    return bool(conflicts), notes


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_timeline(process_ir: ProcessIR) -> list[TimelineEvent]:
    """Extract and classify all change events from a single ProcessIR instance.

    Returns a list of TimelineEvent, one per ChangeEvent in the ProcessIR.
    Order follows the order of change_events in the input.
    """
    return [
        _change_event_to_timeline(ev, process_ir.id) for ev in process_ir.change_events
    ]


def build_lineage_chain(
    ordered_versions: list[ProcessIR],
) -> LineageChain:
    """Build a lineage chain from an ordered list of ProcessIR versions.

    The caller supplies the versions in chronological order (oldest first).
    Each version is assumed to supersede the preceding one.

    Args:
        ordered_versions: ProcessIR instances in chronological order.

    Returns:
        LineageChain with versioned snapshots and a merged timeline.
    """
    if not ordered_versions:
        return LineageChain(
            chain_id="chain_empty",
            versions=[],
            timeline=[],
            summary="No versions provided.",
        )

    built: list[ProcessVersion] = []
    for i, pir in enumerate(ordered_versions):
        supersedes_id = ordered_versions[i - 1].id if i > 0 else None
        pv = _build_version(pir, version_number=i + 1, supersedes=supersedes_id)
        built.append(pv)

    _detect_supersession(built)
    ambiguous, notes = _check_ambiguous_supersession(built)

    # Build flat timeline (all change events across all versions)
    timeline: list[TimelineEvent] = []
    for pv in built:
        timeline.extend(pv.changes)

    chain_id = f"chain_{ordered_versions[0].id}"
    summary = _build_chain_summary(built)

    return LineageChain(
        chain_id=chain_id,
        versions=built,
        timeline=timeline,
        summary=summary,
        has_ambiguous_lineage=ambiguous,
        ambiguity_notes=notes,
    )


def aggregate_changes(
    processes: list[ProcessIR],
) -> dict[ChangeCategory, list[TimelineEvent]]:
    """Aggregate change events from multiple ProcessIR instances by category.

    Useful for building cross-process change summaries.

    Returns:
        Dict mapping ChangeCategory → list of TimelineEvent.
    """
    result: dict[ChangeCategory, list[TimelineEvent]] = {
        cat: [] for cat in ChangeCategory
    }
    for pir in processes:
        for ev in pir.change_events:
            te = _change_event_to_timeline(ev, pir.id)
            result[te.category].append(te)
    return result


def detect_superseded(processes: list[ProcessIR]) -> list[str]:
    """Return process IDs that are superseded by another process in the list.

    A process is considered superseded when another process in the same list
    has a substantially overlapping set of workflow steps but also includes
    change events — indicating the newer version extends the older one.

    This is a lightweight heuristic using step overlap + change presence.
    It flags candidates for human review rather than making automatic decisions.

    Args:
        processes: List of ProcessIR instances to evaluate.

    Returns:
        List of process IDs that appear to be superseded.
    """
    if len(processes) < 2:
        return []

    superseded: list[str] = []

    # Build step-label sets per process
    step_sets = {
        pir.id: frozenset(s.name.lower().strip() for s in pir.workflow_steps)
        for pir in processes
    }

    for i, candidate in enumerate(processes):
        candidate_steps = step_sets[candidate.id]
        if not candidate_steps:
            continue
        for j, other in enumerate(processes):
            if i == j:
                continue
            other_steps = step_sets[other.id]
            # If 'other' contains all of candidate's steps + more + has change events
            if candidate_steps < other_steps and other.change_events:  # strict subset
                superseded.append(candidate.id)
                break

    return superseded


def build_timeline_summary(chain: LineageChain) -> dict:
    """Produce a compact summary dict for a lineage chain.

    Suitable for API responses — no raw customer content included.
    """
    categories: dict[str, int] = {}
    for te in chain.timeline:
        categories[te.category.value] = categories.get(te.category.value, 0) + 1

    return {
        "chain_id": chain.chain_id,
        "version_count": len(chain.versions),
        "total_change_events": len(chain.timeline),
        "change_categories": categories,
        "has_ambiguous_lineage": chain.has_ambiguous_lineage,
        "ambiguity_notes": chain.ambiguity_notes,
        "summary": chain.summary,
    }


def _build_chain_summary(versions: list[ProcessVersion]) -> str:
    """Build a human-readable summary of a lineage chain."""
    if not versions:
        return "Empty chain."
    first, last = versions[0], versions[-1]
    step_delta = last.step_count - first.step_count
    role_delta = last.role_count - first.role_count
    total_changes = sum(len(v.changes) for v in versions)
    parts = [
        f"{len(versions)} version(s) tracked.",
        f"{total_changes} change event(s) recorded.",
    ]
    if step_delta > 0:
        parts.append(f"Workflow grew by {step_delta} step(s).")
    elif step_delta < 0:
        parts.append(f"Workflow shrank by {abs(step_delta)} step(s).")
    if role_delta != 0:
        parts.append(f"Role count changed by {role_delta:+d}.")
    return " ".join(parts)
