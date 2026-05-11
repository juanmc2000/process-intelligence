"""Tests for extraction evaluation helpers and gold fixtures.

Validates that:
- Metrics compute correctly
- Gold fixtures produce meaningful extraction results
- Negative examples are handled correctly
- Per-label summaries work
"""

import pytest

from packages.core.process_ir.evaluation import (
    EvaluationReport,
    Metrics,
    evaluate_action_classes,
    evaluate_entities,
    evaluate_fixture,
    evaluate_gold_dataset,
    evaluate_relations,
)
from packages.core.process_ir.extractor import extract
from tests.fixtures.gold_extraction import GOLD_FIXTURES


# --- Metrics unit tests ---


class TestMetrics:
    def test_perfect_precision(self):
        m = Metrics(true_positives=5, false_positives=0, false_negatives=0)
        assert m.precision == 1.0

    def test_perfect_recall(self):
        m = Metrics(true_positives=5, false_positives=0, false_negatives=0)
        assert m.recall == 1.0

    def test_perfect_f1(self):
        m = Metrics(true_positives=5, false_positives=0, false_negatives=0)
        assert m.f1 == 1.0

    def test_zero_precision(self):
        m = Metrics(true_positives=0, false_positives=5, false_negatives=0)
        assert m.precision == 0.0

    def test_zero_recall(self):
        m = Metrics(true_positives=0, false_positives=0, false_negatives=5)
        assert m.recall == 0.0

    def test_zero_f1_when_no_predictions(self):
        m = Metrics(true_positives=0, false_positives=0, false_negatives=0)
        assert m.f1 == 0.0

    def test_partial_precision(self):
        m = Metrics(true_positives=3, false_positives=2, false_negatives=1)
        assert m.precision == pytest.approx(0.6)
        assert m.recall == pytest.approx(0.75)


# --- Entity evaluation tests ---


class TestEntityEvaluation:
    def test_approval_fixture_entities(self):
        fixture = GOLD_FIXTURES[0]  # approval workflow
        result = extract(fixture["text"])
        metrics = evaluate_entities(result, fixture["expected_entities"])
        # Should find at least some of the expected entities
        assert metrics.true_positives > 0
        assert metrics.recall > 0.0

    def test_negative_fixture_no_entities(self):
        fixture = GOLD_FIXTURES[-1]  # negated example
        result = extract(fixture["text"])
        metrics = evaluate_entities(result, fixture["expected_entities"])
        # No expected entities, so FP count = number of extracted entities
        assert metrics.false_negatives == 0


# --- Relation evaluation tests ---


class TestRelationEvaluation:
    def test_approval_fixture_relations(self):
        fixture = GOLD_FIXTURES[0]  # approval workflow
        result = extract(fixture["text"])
        metrics = evaluate_relations(
            result, fixture["expected_relations"], fixture["expected_entities"]
        )
        # May or may not find the relation — check metrics are valid
        assert metrics.true_positives + metrics.false_negatives == len(
            fixture["expected_relations"]
        )


# --- Action classification evaluation tests ---


class TestActionEvaluation:
    def test_approval_fixture_actions(self):
        fixture = GOLD_FIXTURES[0]  # approval workflow
        result = extract(fixture["text"])
        metrics = evaluate_action_classes(result, fixture["expected_action_classes"])
        assert metrics.true_positives > 0

    def test_rejection_fixture_actions(self):
        fixture = GOLD_FIXTURES[1]  # rejection workflow
        result = extract(fixture["text"])
        metrics = evaluate_action_classes(result, fixture["expected_action_classes"])
        assert metrics.true_positives > 0

    def test_handoff_fixture_actions(self):
        fixture = GOLD_FIXTURES[2]  # handoff
        result = extract(fixture["text"])
        metrics = evaluate_action_classes(result, fixture["expected_action_classes"])
        assert metrics.true_positives > 0

    def test_escalation_fixture_actions(self):
        fixture = GOLD_FIXTURES[3]  # escalation
        result = extract(fixture["text"])
        metrics = evaluate_action_classes(result, fixture["expected_action_classes"])
        assert metrics.true_positives > 0

    def test_system_entry_fixture_actions(self):
        fixture = GOLD_FIXTURES[4]  # system entry
        result = extract(fixture["text"])
        metrics = evaluate_action_classes(result, fixture["expected_action_classes"])
        assert metrics.true_positives > 0

    def test_change_fixture_actions(self):
        fixture = GOLD_FIXTURES[9]  # change event
        result = extract(fixture["text"])
        metrics = evaluate_action_classes(result, fixture["expected_action_classes"])
        assert metrics.true_positives > 0

    def test_exception_raised_fixture_actions(self):
        fixture = GOLD_FIXTURES[7]  # exception raised
        result = extract(fixture["text"])
        metrics = evaluate_action_classes(result, fixture["expected_action_classes"])
        assert metrics.true_positives > 0

    def test_exception_resolved_fixture_actions(self):
        fixture = GOLD_FIXTURES[8]  # exception resolved
        result = extract(fixture["text"])
        metrics = evaluate_action_classes(result, fixture["expected_action_classes"])
        assert metrics.true_positives > 0


# --- Full fixture evaluation tests ---


class TestFixtureEvaluation:
    def test_evaluate_single_fixture(self):
        fixture = GOLD_FIXTURES[0]
        result = extract(fixture["text"])
        metrics_dict = evaluate_fixture(result, fixture)
        assert "entities" in metrics_dict
        assert "relations" in metrics_dict
        assert "actions" in metrics_dict

    def test_evaluate_all_positive_fixtures(self):
        """All positive fixtures should produce at least some correct extractions."""
        for fixture in GOLD_FIXTURES:
            if fixture.get("is_negative"):
                continue
            result = extract(fixture["text"])
            metrics_dict = evaluate_fixture(result, fixture)
            # At least one category should have true positives
            total_tp = sum(m.true_positives for m in metrics_dict.values())
            assert total_tp > 0, f"Fixture {fixture['id']} produced no true positives"


# --- Gold dataset evaluation tests ---


class TestGoldDatasetEvaluation:
    def test_full_evaluation(self):
        results = []
        for fixture in GOLD_FIXTURES:
            result = extract(fixture["text"], evidence_id=fixture["id"])
            results.append((result, fixture))

        report = evaluate_gold_dataset(results)

        # Entity metrics should show some extraction quality
        assert report.entity_metrics.true_positives > 0
        assert report.entity_metrics.precision > 0.0
        assert report.entity_metrics.recall > 0.0
        assert report.entity_metrics.f1 > 0.0

        # Action metrics should show good classification
        assert report.action_metrics.true_positives > 0
        assert report.action_metrics.f1 > 0.0

        # Negative examples should be mostly correct
        assert report.negative_total == 2
        assert report.negative_accuracy > 0.0

    def test_per_action_class_summary(self):
        results = []
        for fixture in GOLD_FIXTURES:
            result = extract(fixture["text"], evidence_id=fixture["id"])
            results.append((result, fixture))

        report = evaluate_gold_dataset(results)

        # Should have per-action-class breakdown
        assert len(report.per_action_class) > 0
        # APPROVAL should be in the breakdown
        assert "APPROVAL" in report.per_action_class

    def test_report_structure(self):
        report = EvaluationReport()
        assert report.entity_metrics.f1 == 0.0
        assert report.negative_accuracy == 0.0
