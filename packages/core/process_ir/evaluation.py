"""Evaluation helpers for measuring deterministic extraction quality.

Computes precision, recall, and F1 for entities, relations, and action
classifications against a gold dataset. Metrics are simple and transparent
— no threshold tuning or optimization against the fixture set.

How to interpret results:
- Precision: fraction of extracted items that are correct.
- Recall: fraction of expected items that were found.
- F1: harmonic mean of precision and recall.
- Per-label summary: breakdown by entity type or action class.
"""

from dataclasses import dataclass, field

from packages.core.process_ir.types import ExtractionResult


@dataclass
class Metrics:
    """Precision / recall / F1 for a single evaluation category."""

    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0

    @property
    def precision(self) -> float:
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom > 0 else 0.0

    @property
    def recall(self) -> float:
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom > 0 else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0


@dataclass
class EvaluationReport:
    """Full evaluation report across a gold dataset."""

    entity_metrics: Metrics = field(default_factory=Metrics)
    relation_metrics: Metrics = field(default_factory=Metrics)
    action_metrics: Metrics = field(default_factory=Metrics)
    per_entity_type: dict[str, Metrics] = field(default_factory=dict)
    per_action_class: dict[str, Metrics] = field(default_factory=dict)
    negative_correct: int = 0
    negative_total: int = 0

    @property
    def negative_accuracy(self) -> float:
        return (
            self.negative_correct / self.negative_total
            if self.negative_total > 0
            else 0.0
        )


def evaluate_entities(
    result: ExtractionResult,
    expected_entities: list[dict],
) -> Metrics:
    """Evaluate entity extraction against expected entities.

    Matching: an extracted entity counts as a true positive if its type matches
    and its label or canonical_label contains (case-insensitive) the expected label.
    """
    metrics = Metrics()
    matched_expected: set[int] = set()

    for ent in result.entities:
        found = False
        for i, exp in enumerate(expected_entities):
            if i in matched_expected:
                continue
            if ent.type.value == exp["type"] and _label_match(
                ent.label, ent.canonical_label, exp["label"]
            ):
                metrics.true_positives += 1
                matched_expected.add(i)
                found = True
                break
        if not found:
            metrics.false_positives += 1

    metrics.false_negatives = len(expected_entities) - len(matched_expected)
    return metrics


def evaluate_relations(
    result: ExtractionResult,
    expected_relations: list[dict],
    expected_entities: list[dict],
) -> Metrics:
    """Evaluate relation extraction against expected relations.

    Matching: a relation counts as a true positive if its type matches and
    its source/target entities roughly match the expected labels.
    """
    metrics = Metrics()
    matched_expected: set[int] = set()

    # Build entity ID → label lookup from the extraction result
    ent_lookup = {ent.id: (ent.label, ent.canonical_label) for ent in result.entities}

    for rel in result.relations:
        source_labels = ent_lookup.get(rel.source_entity_id, ("", ""))
        target_labels = ent_lookup.get(rel.target_entity_id, ("", ""))

        found = False
        for i, exp in enumerate(expected_relations):
            if i in matched_expected:
                continue
            if (
                rel.type.value == exp["type"]
                and _label_match(
                    source_labels[0], source_labels[1], exp["source_label"]
                )
                and _label_match(
                    target_labels[0], target_labels[1], exp["target_label"]
                )
            ):
                metrics.true_positives += 1
                matched_expected.add(i)
                found = True
                break
        if not found:
            metrics.false_positives += 1

    metrics.false_negatives = len(expected_relations) - len(matched_expected)
    return metrics


def evaluate_action_classes(
    result: ExtractionResult,
    expected_classes: list[str],
) -> Metrics:
    """Evaluate action classification against expected classes.

    Matching: extracted classification counts as TP if the action class
    appears in the expected list.
    """
    metrics = Metrics()
    extracted_classes = {c.action_class.value for c in result.action_classifications}
    expected_set = set(expected_classes)

    metrics.true_positives = len(extracted_classes & expected_set)
    metrics.false_positives = len(extracted_classes - expected_set)
    metrics.false_negatives = len(expected_set - extracted_classes)
    return metrics


def evaluate_fixture(
    result: ExtractionResult,
    fixture: dict,
) -> dict[str, Metrics]:
    """Evaluate extraction result against a single gold fixture.

    Returns a dict with 'entities', 'relations', 'actions' keys.
    """
    return {
        "entities": evaluate_entities(result, fixture["expected_entities"]),
        "relations": evaluate_relations(
            result, fixture["expected_relations"], fixture["expected_entities"]
        ),
        "actions": evaluate_action_classes(result, fixture["expected_action_classes"]),
    }


def evaluate_gold_dataset(
    results: list[tuple[ExtractionResult, dict]],
) -> EvaluationReport:
    """Evaluate extraction results against the full gold dataset.

    Args:
        results: list of (ExtractionResult, fixture_dict) pairs.

    Returns:
        EvaluationReport with aggregate and per-label metrics.
    """
    report = EvaluationReport()

    for result, fixture in results:
        is_negative = fixture.get("is_negative", False)

        if is_negative:
            report.negative_total += 1
            # For negative examples, success = no entities and no action classes extracted
            if len(result.entities) == 0 and len(result.action_classifications) == 0:
                report.negative_correct += 1
            continue

        fixture_metrics = evaluate_fixture(result, fixture)

        # Aggregate entity metrics
        ent_m = fixture_metrics["entities"]
        report.entity_metrics.true_positives += ent_m.true_positives
        report.entity_metrics.false_positives += ent_m.false_positives
        report.entity_metrics.false_negatives += ent_m.false_negatives

        # Per-entity-type breakdown
        for exp_ent in fixture["expected_entities"]:
            etype = exp_ent["type"]
            if etype not in report.per_entity_type:
                report.per_entity_type[etype] = Metrics()

        # Aggregate relation metrics
        rel_m = fixture_metrics["relations"]
        report.relation_metrics.true_positives += rel_m.true_positives
        report.relation_metrics.false_positives += rel_m.false_positives
        report.relation_metrics.false_negatives += rel_m.false_negatives

        # Aggregate action metrics
        act_m = fixture_metrics["actions"]
        report.action_metrics.true_positives += act_m.true_positives
        report.action_metrics.false_positives += act_m.false_positives
        report.action_metrics.false_negatives += act_m.false_negatives

        # Per-action-class breakdown
        for ac in fixture["expected_action_classes"]:
            if ac not in report.per_action_class:
                report.per_action_class[ac] = Metrics()
            extracted_classes = {
                c.action_class.value for c in result.action_classifications
            }
            if ac in extracted_classes:
                report.per_action_class[ac].true_positives += 1
            else:
                report.per_action_class[ac].false_negatives += 1

    return report


def _label_match(label: str, canonical_label: str, expected: str) -> bool:
    """Case-insensitive substring match for entity labels."""
    expected_lower = expected.lower()
    return expected_lower in label.lower() or expected_lower in canonical_label.lower()
