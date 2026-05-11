"""Extraction output types for the deterministic process extractor.

These types represent the intermediate extraction result — entities, relations,
and action classifications with confidence scores and provenance metadata.
They are converted into ProcessIR schemas before storage.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ExtractionMethod(str, Enum):
    GAZETTEER = "gazetteer"
    ALIAS = "alias"
    REGEX = "regex"
    RULE = "rule"
    TEMPORAL_CUE = "temporal_cue"


class EntityType(str, Enum):
    PERSON = "PERSON"
    ROLE = "ROLE"
    SYSTEM = "SYSTEM"
    DEPARTMENT = "DEPARTMENT"
    WORKFLOW_OBJECT = "WORKFLOW_OBJECT"
    ACTION = "ACTION"
    CONTROL = "CONTROL"
    POLICY = "POLICY"
    EXCEPTION = "EXCEPTION"
    CHANGE_EVENT = "CHANGE_EVENT"


class ActionClass(str, Enum):
    REQUEST_CREATED = "REQUEST_CREATED"
    APPROVAL = "APPROVAL"
    REJECTION = "REJECTION"
    HANDOFF = "HANDOFF"
    ESCALATION = "ESCALATION"
    SYSTEM_ENTRY = "SYSTEM_ENTRY"
    VALIDATION = "VALIDATION"
    RECONCILIATION = "RECONCILIATION"
    EXCEPTION_RAISED = "EXCEPTION_RAISED"
    EXCEPTION_RESOLVED = "EXCEPTION_RESOLVED"
    COMPLETION = "COMPLETION"
    CHANGE_MADE = "CHANGE_MADE"
    UNKNOWN = "UNKNOWN"


class ControlType(str, Enum):
    APPROVAL_CONTROL = "APPROVAL_CONTROL"
    RECONCILIATION_CONTROL = "RECONCILIATION_CONTROL"
    SEGREGATION_OF_DUTIES = "SEGREGATION_OF_DUTIES"
    THRESHOLD_CONTROL = "THRESHOLD_CONTROL"
    VALIDATION_CONTROL = "VALIDATION_CONTROL"
    ACCESS_CONTROL = "ACCESS_CONTROL"
    AUDIT_EVIDENCE = "AUDIT_EVIDENCE"
    EXCEPTION_REVIEW = "EXCEPTION_REVIEW"


class RelationType(str, Enum):
    APPROVES = "approves"
    REJECTS = "rejects"
    ESCALATES_TO = "escalates_to"
    CREATES_IN = "creates_in"
    VALIDATES = "validates"
    EXECUTED_IN = "executed_in"
    APPLIES_TO = "applies_to"
    CHANGED_FROM_TO = "changed_from_to"
    HANDOFF_TO = "handoff_to"
    PRECEDES = "precedes"
    FOLLOWS = "follows"
    TRIGGERED_BY = "triggered_by"
    CONDITIONED_ON = "conditioned_on"


class ExtractedEntity(BaseModel):
    """An entity found in the text by the deterministic extractor."""

    id: str
    type: EntityType
    label: str
    canonical_label: str
    confidence: float = Field(ge=0.0, le=1.0)
    span: Optional[tuple[int, int]] = None
    method: ExtractionMethod

    # Optional subtype for controls
    control_type: Optional[ControlType] = None
    # Optional threshold value for threshold controls
    threshold_value: Optional[str] = None


class ExtractedRelation(BaseModel):
    """A relation between two entities found by the deterministic extractor."""

    type: RelationType
    source_entity_id: str
    target_entity_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    method: ExtractionMethod
    # For change_from_to relations
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    # Optional metadata
    metadata: dict = Field(default_factory=dict)


class ActionClassification(BaseModel):
    """Classification of a text segment into an action class."""

    action_class: ActionClass
    confidence: float = Field(ge=0.0, le=1.0)
    method: ExtractionMethod
    matched_text: Optional[str] = None


class TemporalCue(BaseModel):
    """A detected ordering or temporal cue between text segments."""

    cue_word: str
    relation: RelationType
    span: tuple[int, int]
    confidence: float = Field(ge=0.0, le=1.0)


class ExtractionResult(BaseModel):
    """Full extraction output from a single evidence text."""

    evidence_id: str
    entities: list[ExtractedEntity] = Field(default_factory=list)
    relations: list[ExtractedRelation] = Field(default_factory=list)
    action_classifications: list[ActionClassification] = Field(default_factory=list)
    temporal_cues: list[TemporalCue] = Field(default_factory=list)
    # Flags for quality control
    has_speculative_content: bool = False
    has_negated_content: bool = False
