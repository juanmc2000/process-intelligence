"""Relation extraction — deterministic extraction of typed relations between entities.

Supports active and passive voice patterns for common operational relations:
approves, rejects, escalates_to, creates_in, validates, executed_in,
applies_to, changed_from_to, handoff_to, and temporal ordering relations.
"""

import re
from typing import Optional

from packages.core.process_ir.types import (
    ExtractionMethod,
    ExtractedEntity,
    ExtractedRelation,
    RelationType,
    TemporalCue,
)

# --- Temporal / ordering cue detection ---

_TEMPORAL_CUES: list[tuple[str, RelationType, float]] = [
    ("before", RelationType.PRECEDES, 0.75),
    ("prior to", RelationType.PRECEDES, 0.75),
    ("after", RelationType.FOLLOWS, 0.75),
    ("following", RelationType.FOLLOWS, 0.75),
    ("then", RelationType.FOLLOWS, 0.75),
    ("subsequently", RelationType.FOLLOWS, 0.75),
    ("next", RelationType.FOLLOWS, 0.75),
    ("finally", RelationType.FOLLOWS, 0.75),
    ("once", RelationType.TRIGGERED_BY, 0.70),
    ("triggered by", RelationType.TRIGGERED_BY, 0.80),
    ("conditioned on", RelationType.CONDITIONED_ON, 0.80),
    ("only if", RelationType.CONDITIONED_ON, 0.75),
    ("provided that", RelationType.CONDITIONED_ON, 0.75),
]

_TEMPORAL_PATTERNS = [
    (re.compile(r"\b" + re.escape(cue) + r"\b", re.IGNORECASE), rel, conf)
    for cue, rel, conf in _TEMPORAL_CUES
]


def extract_temporal_cues(text: str) -> list[TemporalCue]:
    """Detect temporal and ordering cues in text."""
    results: list[TemporalCue] = []
    for pattern, relation, confidence in _TEMPORAL_PATTERNS:
        for m in pattern.finditer(text):
            results.append(
                TemporalCue(
                    cue_word=m.group(),
                    relation=relation,
                    span=(m.start(), m.end()),
                    confidence=confidence,
                )
            )
    return results


# --- Relation extraction from pattern matches ---


def build_relations_from_patterns(
    pattern_matches: list,
    entities: list[ExtractedEntity],
) -> list[ExtractedRelation]:
    """Build typed relations from regex pattern matches and entity list.

    Attempts to link pattern-captured actors/targets/systems to extracted entities.
    Falls back to creating relations with the best-matching entity when exact
    linking is ambiguous.
    """
    relations: list[ExtractedRelation] = []
    entity_by_label: dict[str, ExtractedEntity] = {}
    for ent in entities:
        entity_by_label[ent.label.lower()] = ent
        entity_by_label[ent.canonical_label.lower()] = ent

    for pm in pattern_matches:
        from packages.core.process_ir.patterns import PatternMatch

        if not isinstance(pm, PatternMatch):
            continue

        rel = _pattern_match_to_relation(pm, entity_by_label, entities)
        if rel is not None:
            relations.append(rel)

    return relations


def _find_entity(
    label: Optional[str],
    entity_lookup: dict[str, ExtractedEntity],
    all_entities: list[ExtractedEntity],
    preferred_types: Optional[list] = None,
) -> Optional[ExtractedEntity]:
    """Find an entity by label, falling back to fuzzy substring match."""
    if label is None:
        return None

    label_lower = label.lower().strip()

    # Exact match
    if label_lower in entity_lookup:
        return entity_lookup[label_lower]

    # Substring match — find entity whose label contains the search term or vice versa
    for ent in all_entities:
        if preferred_types and ent.type not in preferred_types:
            continue
        if label_lower in ent.label.lower() or ent.label.lower() in label_lower:
            return ent

    # Fallback: any substring match ignoring type preference
    for ent in all_entities:
        if label_lower in ent.label.lower() or ent.label.lower() in label_lower:
            return ent

    return None


def _pattern_match_to_relation(
    pm,
    entity_lookup: dict[str, ExtractedEntity],
    all_entities: list[ExtractedEntity],
) -> Optional[ExtractedRelation]:
    """Convert a single PatternMatch into a typed relation if entities can be linked."""
    from packages.core.process_ir.types import EntityType
    from packages.core.process_ir.patterns import PatternMatch

    if not isinstance(pm, PatternMatch):
        return None

    action = pm.action_class
    base_confidence = (
        pm.confidence * 0.85
    )  # Relation confidence = pattern * entity factor

    from packages.core.process_ir.types import ActionClass

    if action == ActionClass.APPROVAL:
        source = _find_entity(
            pm.actor, entity_lookup, all_entities, [EntityType.ROLE, EntityType.PERSON]
        )
        # Find a workflow object as target
        target = _find_nearest_entity(
            all_entities, [EntityType.WORKFLOW_OBJECT, EntityType.ACTION], pm.span
        )
        if source and target:
            return ExtractedRelation(
                type=RelationType.APPROVES,
                source_entity_id=source.id,
                target_entity_id=target.id,
                confidence=base_confidence,
                method=ExtractionMethod.REGEX,
            )

    elif action == ActionClass.REJECTION:
        source = _find_entity(
            pm.actor, entity_lookup, all_entities, [EntityType.ROLE, EntityType.PERSON]
        )
        target = _find_nearest_entity(
            all_entities, [EntityType.WORKFLOW_OBJECT, EntityType.ACTION], pm.span
        )
        if source and target:
            return ExtractedRelation(
                type=RelationType.REJECTS,
                source_entity_id=source.id,
                target_entity_id=target.id,
                confidence=base_confidence,
                method=ExtractionMethod.REGEX,
            )

    elif action == ActionClass.ESCALATION:
        target = _find_entity(
            pm.target,
            entity_lookup,
            all_entities,
            [EntityType.ROLE, EntityType.DEPARTMENT],
        )
        source = _find_nearest_entity(
            all_entities, [EntityType.WORKFLOW_OBJECT, EntityType.ACTION], pm.span
        )
        if source and target:
            return ExtractedRelation(
                type=RelationType.ESCALATES_TO,
                source_entity_id=source.id,
                target_entity_id=target.id,
                confidence=base_confidence,
                method=ExtractionMethod.REGEX,
            )

    elif action == ActionClass.HANDOFF:
        target = _find_entity(
            pm.target,
            entity_lookup,
            all_entities,
            [EntityType.ROLE, EntityType.DEPARTMENT],
        )
        source = _find_nearest_entity(
            all_entities,
            [EntityType.WORKFLOW_OBJECT, EntityType.ACTION, EntityType.ROLE],
            pm.span,
        )
        if source and target:
            return ExtractedRelation(
                type=RelationType.HANDOFF_TO,
                source_entity_id=source.id,
                target_entity_id=target.id,
                confidence=base_confidence,
                method=ExtractionMethod.REGEX,
            )

    elif action == ActionClass.SYSTEM_ENTRY:
        system = _find_entity(
            pm.system, entity_lookup, all_entities, [EntityType.SYSTEM]
        )
        source = _find_nearest_entity(
            all_entities, [EntityType.WORKFLOW_OBJECT, EntityType.ACTION], pm.span
        )
        if source and system:
            return ExtractedRelation(
                type=RelationType.CREATES_IN,
                source_entity_id=source.id,
                target_entity_id=system.id,
                confidence=base_confidence,
                method=ExtractionMethod.REGEX,
            )

    elif action == ActionClass.VALIDATION:
        source = _find_entity(
            pm.actor, entity_lookup, all_entities, [EntityType.ROLE, EntityType.PERSON]
        )
        target = _find_nearest_entity(
            all_entities, [EntityType.WORKFLOW_OBJECT, EntityType.CONTROL], pm.span
        )
        if source and target:
            return ExtractedRelation(
                type=RelationType.VALIDATES,
                source_entity_id=source.id,
                target_entity_id=target.id,
                confidence=base_confidence,
                method=ExtractionMethod.REGEX,
            )

    elif action == ActionClass.RECONCILIATION:
        system = _find_entity(
            pm.system, entity_lookup, all_entities, [EntityType.SYSTEM]
        )
        source = _find_nearest_entity(
            all_entities, [EntityType.WORKFLOW_OBJECT, EntityType.CONTROL], pm.span
        )
        if source and system:
            return ExtractedRelation(
                type=RelationType.VALIDATES,
                source_entity_id=source.id,
                target_entity_id=system.id,
                confidence=base_confidence,
                method=ExtractionMethod.REGEX,
            )

    elif action == ActionClass.CHANGE_MADE:
        if pm.old_value and pm.new_value:
            # Find the nearest entity to attribute the change to
            subject = _find_nearest_entity(all_entities, None, pm.span)
            if subject:
                return ExtractedRelation(
                    type=RelationType.CHANGED_FROM_TO,
                    source_entity_id=subject.id,
                    target_entity_id=subject.id,
                    confidence=base_confidence,
                    method=ExtractionMethod.REGEX,
                    old_value=pm.old_value,
                    new_value=pm.new_value,
                )

    return None


def _find_nearest_entity(
    entities: list[ExtractedEntity],
    preferred_types: Optional[list] = None,
    reference_span: Optional[tuple[int, int]] = None,
) -> Optional[ExtractedEntity]:
    """Find the nearest entity by span position, optionally filtered by type."""
    candidates = entities
    if preferred_types:
        typed = [e for e in entities if e.type in preferred_types]
        if typed:
            candidates = typed

    if not candidates:
        return None

    if reference_span is None:
        return candidates[0]

    ref_mid = (reference_span[0] + reference_span[1]) / 2

    def distance(ent: ExtractedEntity) -> float:
        if ent.span is None:
            return float("inf")
        ent_mid = (ent.span[0] + ent.span[1]) / 2
        return abs(ref_mid - ent_mid)

    return min(candidates, key=distance)


def build_control_relations(entities: list[ExtractedEntity]) -> list[ExtractedRelation]:
    """Build applies_to relations from control entities to nearby workflow objects."""
    controls = [e for e in entities if e.type.value == "CONTROL"]
    workflow_objects = [
        e for e in entities if e.type.value in ("WORKFLOW_OBJECT", "ACTION")
    ]

    relations: list[ExtractedRelation] = []
    for control in controls:
        nearest = _find_nearest_entity(workflow_objects, reference_span=control.span)
        if nearest:
            relations.append(
                ExtractedRelation(
                    type=RelationType.APPLIES_TO,
                    source_entity_id=control.id,
                    target_entity_id=nearest.id,
                    confidence=control.confidence * 0.80,
                    method=ExtractionMethod.RULE,
                )
            )

    return relations
