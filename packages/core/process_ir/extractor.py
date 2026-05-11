"""Main deterministic process extractor.

Orchestrates gazetteer matching, regex pattern extraction, action classification,
relation extraction, temporal cue detection, negation/speculative filtering,
and confidence scoring to produce a structured ExtractionResult.

This module is algorithm-only — no database, API, storage, or Temporal dependencies.
"""

import re
import uuid
from typing import Optional

from packages.core.process_ir.classifier import classify_sentences
from packages.core.process_ir.gazetteer import Gazetteer, GazetteerMatch
from packages.core.process_ir.negation import (
    filter_negated_sentences,
    is_negated,
    is_speculative,
)
from packages.core.process_ir.patterns import PatternMatch, extract_patterns
from packages.core.process_ir.relations import (
    build_control_relations,
    build_relations_from_patterns,
    extract_temporal_cues,
)
from packages.core.process_ir.types import (
    ActionClass,
    EntityType,
    ExtractionMethod,
    ExtractionResult,
    ExtractedEntity,
)


def extract(text: str, evidence_id: Optional[str] = None) -> ExtractionResult:
    """Run the full deterministic extraction pipeline on text.

    Steps:
    1. Split text into sentences
    2. Filter negated/speculative sentences
    3. Run gazetteer matching on factual sentences
    4. Run regex pattern extraction on factual sentences
    5. Classify sentences into action classes
    6. Extract relations from patterns and entities
    7. Extract temporal cues
    8. Build control relations
    9. Detect change events
    10. Compose final result

    Args:
        text: The input text to extract from.
        evidence_id: Optional ID for the source evidence.

    Returns:
        ExtractionResult with entities, relations, classifications, and temporal cues.
    """
    if evidence_id is None:
        evidence_id = f"ev_{uuid.uuid4().hex[:8]}"

    # Step 1: Split into sentences
    sentences = _split_sentences(text)

    # Step 2: Filter negated/speculative content
    factual_sentences, filtered_sentences = filter_negated_sentences(sentences)
    factual_text = " ".join(factual_sentences)

    has_negated = any(is_negated(s) for s in sentences)
    has_speculative = any(is_speculative(s) for s in sentences)

    # Step 3: Gazetteer matching on the full text (we match on full text for span accuracy)
    gazetteer = Gazetteer()
    gaz_matches = gazetteer.match(text)

    # Filter out gazetteer matches that fall within negated/speculative sentences
    gaz_matches = _filter_matches_in_negated_spans(gaz_matches, text, sentences)

    # Step 4: Convert gazetteer matches to entities
    entities: list[ExtractedEntity] = []
    entity_counter = 0
    for gm in gaz_matches:
        entity_counter += 1
        entities.append(_gazetteer_match_to_entity(gm, entity_counter))

    # Step 5: Regex pattern extraction on factual text
    # We use the full text for pattern matching but filter results in negated spans
    pattern_matches = extract_patterns(text)
    pattern_matches = _filter_pattern_matches_in_negated_spans(
        pattern_matches, text, sentences
    )

    # Step 6: Create entities from pattern captures (actors, targets, systems not already in gazetteer)
    for pm in pattern_matches:
        for label, preferred_type in _pattern_captured_entities(pm):
            if not _entity_exists(entities, label):
                entity_counter += 1
                entities.append(
                    ExtractedEntity(
                        id=f"ent_{entity_counter}",
                        type=preferred_type,
                        label=label,
                        canonical_label=label,
                        confidence=pm.confidence * 0.85,
                        method=ExtractionMethod.REGEX,
                    )
                )

    # Step 7: Classify sentences into action classes
    classifications = classify_sentences(factual_text)

    # Step 8: Extract relations from patterns + entities
    relations = build_relations_from_patterns(pattern_matches, entities)

    # Step 9: Extract temporal cues
    temporal_cues = extract_temporal_cues(text)

    # Step 10: Build control-applies-to relations
    control_rels = build_control_relations(entities)
    relations.extend(control_rels)

    # Step 11: Build change-event entities from change pattern matches
    for pm in pattern_matches:
        if pm.action_class == ActionClass.CHANGE_MADE:
            entity_counter += 1
            change_label = _build_change_label(pm)
            entities.append(
                ExtractedEntity(
                    id=f"ent_{entity_counter}",
                    type=EntityType.CHANGE_EVENT,
                    label=change_label,
                    canonical_label=change_label,
                    confidence=pm.confidence,
                    span=pm.span,
                    method=ExtractionMethod.REGEX,
                )
            )

    return ExtractionResult(
        evidence_id=evidence_id,
        entities=entities,
        relations=relations,
        action_classifications=classifications,
        temporal_cues=temporal_cues,
        has_speculative_content=has_speculative,
        has_negated_content=has_negated,
    )


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences on period/newline boundaries."""
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [s.strip() for s in parts if s.strip()]


def _find_sentence_spans(text: str, sentences: list[str]) -> list[tuple[int, int, str]]:
    """Find (start, end, sentence) for each sentence in the original text."""
    spans: list[tuple[int, int, str]] = []
    pos = 0
    for sentence in sentences:
        idx = text.find(sentence, pos)
        if idx == -1:
            # Fallback: approximate position
            idx = pos
        spans.append((idx, idx + len(sentence), sentence))
        pos = idx + len(sentence)
    return spans


def _filter_matches_in_negated_spans(
    matches: list[GazetteerMatch],
    text: str,
    sentences: list[str],
) -> list[GazetteerMatch]:
    """Remove gazetteer matches that fall within negated/speculative sentences."""
    negated_spans = _get_negated_spans(text, sentences)
    return [m for m in matches if not _span_overlaps_any(m.span, negated_spans)]


def _filter_pattern_matches_in_negated_spans(
    matches: list[PatternMatch],
    text: str,
    sentences: list[str],
) -> list[PatternMatch]:
    """Remove pattern matches that fall within negated/speculative sentences."""
    negated_spans = _get_negated_spans(text, sentences)
    return [m for m in matches if not _span_overlaps_any(m.span, negated_spans)]


def _get_negated_spans(text: str, sentences: list[str]) -> list[tuple[int, int]]:
    """Get character spans of negated/speculative sentences."""
    sentence_spans = _find_sentence_spans(text, sentences)
    return [
        (start, end)
        for start, end, sentence in sentence_spans
        if is_negated(sentence) or is_speculative(sentence)
    ]


def _span_overlaps_any(span: tuple[int, int], regions: list[tuple[int, int]]) -> bool:
    """Check if a span overlaps with any of the given regions."""
    start, end = span
    return any(not (end <= r_start or start >= r_end) for r_start, r_end in regions)


def _gazetteer_match_to_entity(gm: GazetteerMatch, counter: int) -> ExtractedEntity:
    """Convert a GazetteerMatch to an ExtractedEntity."""
    return ExtractedEntity(
        id=f"ent_{counter}",
        type=gm.entity_type,
        label=gm.matched_text,
        canonical_label=gm.canonical_label,
        confidence=gm.confidence,
        span=gm.span,
        method=gm.method,
        control_type=gm.control_type,
    )


def _pattern_captured_entities(pm: PatternMatch) -> list[tuple[str, EntityType]]:
    """Extract (label, type) pairs from pattern match captures that should become entities."""
    results: list[tuple[str, EntityType]] = []
    if pm.actor:
        results.append((pm.actor, EntityType.ROLE))
    if pm.target:
        results.append((pm.target, EntityType.ROLE))
    if pm.system:
        results.append((pm.system, EntityType.SYSTEM))
    return results


def _entity_exists(entities: list[ExtractedEntity], label: str) -> bool:
    """Check if an entity with this label already exists (case-insensitive)."""
    label_lower = label.lower()
    return any(
        e.label.lower() == label_lower or e.canonical_label.lower() == label_lower
        for e in entities
    )


def _build_change_label(pm: PatternMatch) -> str:
    """Build a human-readable label for a change event pattern match."""
    if pm.old_value and pm.new_value:
        return f"Change: {pm.old_value} → {pm.new_value}"
    return f"Change: {pm.matched_text[:80]}"
