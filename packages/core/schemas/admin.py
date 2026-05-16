"""Admin and security governance schemas.

These schemas define the contract for admin API endpoints.
All responses are structured placeholders — no real governance
data is connected yet.  Values clearly indicate placeholder status.
"""

from typing import Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Integration status
# ---------------------------------------------------------------------------


class IntegrationStatus(BaseModel):
    """Status of a single external integration."""

    name: str
    connected: bool
    last_sync_at: Optional[str] = None
    error_message: Optional[str] = None
    placeholder: bool = True


class IntegrationsResponse(BaseModel):
    """Aggregated integration status response."""

    integrations: list[IntegrationStatus]
    note: str = "Integration status is not yet connected to live data."


# ---------------------------------------------------------------------------
# Ingestion status
# ---------------------------------------------------------------------------


class IngestionStatus(BaseModel):
    """Ingestion pipeline health summary."""

    active_runs: int
    completed_runs: int
    failed_runs: int
    last_ingestion_at: Optional[str] = None
    placeholder: bool = True


class IngestionResponse(BaseModel):
    """Ingestion status response."""

    status: IngestionStatus
    note: str = "Ingestion metrics are derived from the runs table."


# ---------------------------------------------------------------------------
# Retention policy
# ---------------------------------------------------------------------------


class RetentionRule(BaseModel):
    """A single retention rule entry."""

    artifact_class: str
    retention_days: Optional[int]
    deletion_eligible: bool
    description: str


class RetentionPolicyResponse(BaseModel):
    """Current retention policy settings."""

    rules: list[RetentionRule]
    note: str = (
        "Retention policy reflects schema-defined defaults. Runtime configuration not yet connected."
    )


# ---------------------------------------------------------------------------
# Anonymization settings
# ---------------------------------------------------------------------------


class AnonymizationResponse(BaseModel):
    """Anonymization / PII masking configuration."""

    pii_masking_enabled: bool
    masking_scope: list[str]
    placeholder: bool = True
    note: str = (
        "Anonymization settings are not yet connected to a live configuration store."
    )


# ---------------------------------------------------------------------------
# Audit summary
# ---------------------------------------------------------------------------


class AuditSummaryResponse(BaseModel):
    """High-level audit event summary."""

    events_last_24h: int
    events_last_7d: int
    top_event_types: list[str]
    placeholder: bool = True
    note: str = (
        "Audit pipeline is not yet connected. These values are placeholder defaults."
    )


# ---------------------------------------------------------------------------
# Security posture
# ---------------------------------------------------------------------------


class SecurityControl(BaseModel):
    """A single security control and its current status."""

    name: str
    status: str  # "planned" | "implemented" | "in_progress"
    description: str


class SecurityPostureResponse(BaseModel):
    """Security posture summary."""

    overall_status: str
    controls: list[SecurityControl]
    note: str = (
        "Security posture reflects planned controls. Production enforcement not yet active."
    )
