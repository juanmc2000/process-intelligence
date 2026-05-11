"""Convert ExtractionResult to ProcessIR schema for storage.

Bridges the internal extraction types to the ProcessIR schema that gets
serialized to MinIO. Handles mapping entity types to ProcessIR collections.
"""

from uuid import UUID

from packages.core.process_ir.types import (
    EntityType,
    ExtractionResult,
)
from packages.core.schemas.process_ir import (
    ChangeEvent,
    Control,
    EvidenceRef,
    ProcessException,
    ProcessIR,
    Role,
    SystemTouchpoint,
    WorkflowStep,
)


def extraction_result_to_process_ir(
    result: ExtractionResult,
    run_id: str,
    source_artifact_uri: str,
    schema_version: str = "process-ir-v1",
    process_ir_id: str = "",
) -> ProcessIR:
    """Convert an ExtractionResult into a ProcessIR schema instance.

    Maps extracted entities to ProcessIR collections by type:
    - ACTION, WORKFLOW_OBJECT → workflow_steps
    - SYSTEM → system_touchpoints
    - ROLE, PERSON → roles
    - CONTROL → controls
    - EXCEPTION → exceptions
    - CHANGE_EVENT → change_events
    """
    evidence_ref = EvidenceRef(artifact_uri=source_artifact_uri)

    workflow_steps: list[WorkflowStep] = []
    system_touchpoints: list[SystemTouchpoint] = []
    roles: list[Role] = []
    controls: list[Control] = []
    exceptions: list[ProcessException] = []
    change_events: list[ChangeEvent] = []

    for ent in result.entities:
        ref = [evidence_ref]

        if ent.type in (EntityType.ACTION, EntityType.WORKFLOW_OBJECT):
            workflow_steps.append(
                WorkflowStep(
                    id=ent.id,
                    name=ent.canonical_label,
                    evidence_refs=ref,
                )
            )

        elif ent.type == EntityType.SYSTEM:
            system_touchpoints.append(
                SystemTouchpoint(
                    id=ent.id,
                    name=ent.canonical_label,
                    system_name=ent.canonical_label,
                    evidence_refs=ref,
                )
            )

        elif ent.type in (EntityType.ROLE, EntityType.PERSON):
            roles.append(
                Role(
                    id=ent.id,
                    name=ent.canonical_label,
                )
            )

        elif ent.type == EntityType.CONTROL:
            controls.append(
                Control(
                    id=ent.id,
                    name=ent.canonical_label,
                    control_type=ent.control_type.value if ent.control_type else None,
                    evidence_refs=ref,
                )
            )

        elif ent.type == EntityType.EXCEPTION:
            exceptions.append(
                ProcessException(
                    id=ent.id,
                    name=ent.canonical_label,
                    evidence_refs=ref,
                )
            )

        elif ent.type == EntityType.CHANGE_EVENT:
            change_events.append(
                ChangeEvent(
                    id=ent.id,
                    name=ent.canonical_label,
                    evidence_refs=ref,
                )
            )

    return ProcessIR(
        id=process_ir_id,
        run_id=UUID(run_id),
        source_artifact_uri=source_artifact_uri,
        schema_version=schema_version,
        workflow_steps=workflow_steps,
        system_touchpoints=system_touchpoints,
        roles=roles,
        controls=controls,
        exceptions=exceptions,
        change_events=change_events,
    )
