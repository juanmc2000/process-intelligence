"""Admin and security governance API stubs.

Routes:
  GET /admin/integrations   — integration connection status
  GET /admin/ingestion      — ingestion pipeline health
  GET /admin/retention      — artifact retention policy
  GET /admin/anonymization  — PII anonymization settings
  GET /admin/audit          — audit event summary
  GET /admin/security       — security posture summary

All responses are structured placeholders.  Real governance data is not
connected yet.  Each response includes a `note` field that clearly states
placeholder status so consuming UIs can distinguish from production data.
"""

from fastapi import APIRouter

from packages.core.schemas.admin import (
    AnonymizationResponse,
    AuditSummaryResponse,
    IngestionResponse,
    IngestionStatus,
    IntegrationStatus,
    IntegrationsResponse,
    RetentionPolicyResponse,
    RetentionRule,
    SecurityControl,
    SecurityPostureResponse,
)

router = APIRouter(prefix="/admin", tags=["admin"])

# ---------------------------------------------------------------------------
# Known integrations (connection not yet wired)
# ---------------------------------------------------------------------------

_INTEGRATION_NAMES = [
    "SharePoint",
    "Slack",
    "Microsoft Teams",
    "Email (Exchange)",
    "S3 Storage",
    "Jira",
]

# ---------------------------------------------------------------------------
# Retention rules derived from ADR-001 artifact tiers
# ---------------------------------------------------------------------------

_RETENTION_RULES = [
    RetentionRule(
        artifact_class="raw_artifact",
        retention_days=30,
        deletion_eligible=True,
        description="Raw uploaded files — temporary, deletion-eligible after processing.",
    ),
    RetentionRule(
        artifact_class="normalized_evidence",
        retention_days=30,
        deletion_eligible=True,
        description="Parsed and normalized evidence — temporary, deletion-eligible.",
    ),
    RetentionRule(
        artifact_class="process_ir",
        retention_days=None,
        deletion_eligible=False,
        description="Structured ProcessIR — durable, retained indefinitely.",
    ),
]

# ---------------------------------------------------------------------------
# Planned security controls
# ---------------------------------------------------------------------------

_SECURITY_CONTROLS = [
    SecurityControl(
        name="RBAC",
        status="planned",
        description="Role-based access control for all API endpoints.",
    ),
    SecurityControl(
        name="Admin action auditing",
        status="planned",
        description="All admin actions logged to append-only audit table.",
    ),
    SecurityControl(
        name="MFA for admin users",
        status="planned",
        description="Multi-factor authentication required for admin accounts.",
    ),
    SecurityControl(
        name="Data at rest encryption",
        status="planned",
        description="All Postgres and MinIO data encrypted at rest.",
    ),
    SecurityControl(
        name="Data in transit encryption",
        status="planned",
        description="TLS enforced on all service-to-service and client communication.",
    ),
    SecurityControl(
        name="PII masking",
        status="planned",
        description="Automatic PII masking before ProcessIR storage.",
    ),
]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/integrations", response_model=IntegrationsResponse)
def get_integrations() -> IntegrationsResponse:
    """Return integration connection status.

    All integrations are currently disconnected — this endpoint returns
    structured placeholder data only.
    """
    integrations = [
        IntegrationStatus(name=name, connected=False) for name in _INTEGRATION_NAMES
    ]
    return IntegrationsResponse(integrations=integrations)


@router.get("/ingestion", response_model=IngestionResponse)
def get_ingestion_status() -> IngestionResponse:
    """Return ingestion pipeline health summary.

    Returns a structured placeholder — aggregated run metrics are not yet
    exposed via a dedicated admin query.  See GET /runs/{id} for per-run status.
    """
    return IngestionResponse(
        status=IngestionStatus(
            active_runs=0,
            completed_runs=0,
            failed_runs=0,
            last_ingestion_at=None,
            placeholder=True,
        ),
    )


@router.get("/retention", response_model=RetentionPolicyResponse)
def get_retention_policy() -> RetentionPolicyResponse:
    """Return the artifact retention policy.

    Returns the schema-defined retention rules from ADR-001.
    Runtime configuration overrides are not yet supported.
    """
    return RetentionPolicyResponse(rules=_RETENTION_RULES)


@router.get("/anonymization", response_model=AnonymizationResponse)
def get_anonymization_settings() -> AnonymizationResponse:
    """Return anonymization / PII masking configuration.

    Returns a structured placeholder — live configuration is not yet connected.
    """
    return AnonymizationResponse(
        pii_masking_enabled=False,
        masking_scope=["raw_artifact", "normalized_evidence"],
    )


@router.get("/audit", response_model=AuditSummaryResponse)
def get_audit_summary() -> AuditSummaryResponse:
    """Return a high-level audit event summary.

    Returns a structured placeholder — audit pipeline is not yet connected.
    """
    return AuditSummaryResponse(
        events_last_24h=0,
        events_last_7d=0,
        top_event_types=[],
    )


@router.get("/security", response_model=SecurityPostureResponse)
def get_security_posture() -> SecurityPostureResponse:
    """Return the current security posture summary.

    All controls are in 'planned' state — production enforcement is not yet active.
    """
    return SecurityPostureResponse(
        overall_status="planned",
        controls=_SECURITY_CONTROLS,
    )
