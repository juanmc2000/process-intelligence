"""ProcessIR — the intermediate representation of extracted process intelligence.

All sub-schemas carry evidence_refs to trace back to the source artifact.
No raw customer content is stored in these schemas — only structured facts.
"""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class EvidenceRef(BaseModel):
    """Reference to a source artifact from which a fact was extracted."""

    artifact_uri: str
    location_hint: Optional[str] = None  # e.g. page number, section heading


class WorkflowStep(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    sequence_order: Optional[int] = None
    role: Optional[str] = None
    system: Optional[str] = None
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class DecisionPoint(BaseModel):
    id: str
    name: str
    conditions: list[str] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class SystemTouchpoint(BaseModel):
    id: str
    name: str
    system_name: str
    interaction_type: Optional[str] = None  # e.g. 'read', 'write', 'trigger'
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class Role(BaseModel):
    id: str
    name: str
    description: Optional[str] = None


class Control(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    control_type: Optional[str] = None  # e.g. 'approval', 'validation', 'audit'
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class ProcessException(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    handling_steps: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class ChangeEvent(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    trigger: Optional[str] = None
    impact: Optional[str] = None
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class ProcessIR(BaseModel):
    """Top-level ProcessIR container.

    Produced by the LLM worker and written as a JSON artifact to MinIO.
    The URI of this artifact is stored in extraction_results.process_ir_uri.
    """

    id: str
    run_id: UUID
    source_artifact_uri: str
    schema_version: str
    workflow_steps: list[WorkflowStep] = Field(default_factory=list)
    decision_points: list[DecisionPoint] = Field(default_factory=list)
    system_touchpoints: list[SystemTouchpoint] = Field(default_factory=list)
    roles: list[Role] = Field(default_factory=list)
    controls: list[Control] = Field(default_factory=list)
    exceptions: list[ProcessException] = Field(default_factory=list)
    change_events: list[ChangeEvent] = Field(default_factory=list)
