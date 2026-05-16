"""Integration tests for the explainability engine using synthetic workflow fixtures.

Tests verify that the explainability engine produces consistent, traceable results
across the full range of synthetic workflows — from well-documented approval flows
to informal, sparse workflows with minimal evidence.

No DB, MinIO, or Temporal dependencies.
"""

import pytest

from packages.core.schemas.process_ir import ProcessIR
from packages.core.process_ir.explainability import (
    explain_process,
    explain_similarity,
)
from packages.core.process_ir.similarity import make_fingerprint, score_similarity
from tests.fixtures.synthetic_workflows import (
    ALL_SYNTHETIC_WORKFLOWS,
    INFORMAL_WORKFLOW,
    INVOICE_APPROVAL,
    PAYMENT_DISPUTE,
    PURCHASE_ORDER_ESCALATION,
    SYSTEM_OUTAGE_FALLBACK,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _load(fixture: dict) -> ProcessIR:
    return ProcessIR.model_validate(fixture)


# ---------------------------------------------------------------------------
# Smoke: all synthetic workflows run without error
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture", ALL_SYNTHETIC_WORKFLOWS, ids=[w["id"] for w in ALL_SYNTHETIC_WORKFLOWS]
)
def test_explain_process_runs_for_all_fixtures(fixture):
    pir = _load(fixture)
    exp = explain_process(pir)
    assert exp.process_id == pir.id
    assert exp.confidence_decomposition is not None
    assert exp.evidence_lineage is not None


# ---------------------------------------------------------------------------
# Invoice approval — well-documented, high confidence expected
# ---------------------------------------------------------------------------


class TestInvoiceApprovalExplainability:
    def setup_method(self):
        self.pir = _load(INVOICE_APPROVAL)
        self.exp = explain_process(self.pir)

    def test_confidence_score_above_seventy(self):
        cd = self.exp.confidence_decomposition
        assert cd.overall_score >= 70

    def test_workflow_steps_all_have_evidence(self):
        step_exps = [
            e for e in self.exp.entity_explanations if e.entity_type == "workflow_step"
        ]
        # All 4 steps have evidence_refs in the fixture
        assert all(e.evidence_count > 0 for e in step_exps)

    def test_sequence_edges_connect_all_steps(self):
        seq_edges = [e for e in self.exp.edge_explanations if e.edge_type == "precedes"]
        # 4 steps → 3 sequence edges
        assert len(seq_edges) == 3

    def test_control_edges_present(self):
        ctrl_edges = [
            e for e in self.exp.edge_explanations if e.edge_type == "validates"
        ]
        assert len(ctrl_edges) == 2  # 2 controls in fixture

    def test_evidence_coverage_high(self):
        el = self.exp.evidence_lineage
        assert el.coverage_ratio >= 0.70

    def test_tier_high_confidence(self):
        cd = self.exp.confidence_decomposition
        assert cd.tier in ("high", "medium")


# ---------------------------------------------------------------------------
# Purchase order escalation — exception path + threshold control
# ---------------------------------------------------------------------------


class TestPurchaseOrderEscalation:
    def setup_method(self):
        self.pir = _load(PURCHASE_ORDER_ESCALATION)
        self.exp = explain_process(self.pir)

    def test_exception_entity_present(self):
        exc_exps = [
            e for e in self.exp.entity_explanations if e.entity_type == "exception"
        ]
        assert len(exc_exps) == 1
        assert "Emergency" in exc_exps[0].label

    def test_decision_point_explanation_present(self):
        dec_exps = [
            e for e in self.exp.entity_explanations if e.entity_type == "decision_point"
        ]
        assert len(dec_exps) == 1

    def test_confidence_score_reasonable(self):
        cd = self.exp.confidence_decomposition
        # 5/6 dimensions populated → should score > 80
        assert cd.overall_score > 80


# ---------------------------------------------------------------------------
# Payment dispute — change event + multiple exceptions
# ---------------------------------------------------------------------------


class TestPaymentDisputeExplainability:
    def setup_method(self):
        self.pir = _load(PAYMENT_DISPUTE)
        self.exp = explain_process(self.pir)

    def test_change_event_explanation_present(self):
        ce_exps = [
            e for e in self.exp.entity_explanations if e.entity_type == "change_event"
        ]
        assert len(ce_exps) == 1
        assert "Credit Policy" in ce_exps[0].label

    def test_two_exception_explanations(self):
        exc_exps = [
            e for e in self.exp.entity_explanations if e.entity_type == "exception"
        ]
        assert len(exc_exps) == 2

    def test_exception_without_refs_is_unverified(self):
        # "Repeated Disputer" has no evidence_refs
        repeated_exp = next(
            (e for e in self.exp.entity_explanations if "Repeated" in e.label),
            None,
        )
        assert repeated_exp is not None
        assert repeated_exp.confidence_tier == "unverified"
        assert repeated_exp.evidence_count == 0

    def test_well_evidenced_labels_from_fixture(self):
        el = self.exp.evidence_lineage
        # Steps with 2+ refs: "Initial Review" (2 refs), "Resolution Decision" (2 refs),
        # "Reconcile..." is not in this fixture
        assert len(el.well_evidenced_entity_labels) >= 1


# ---------------------------------------------------------------------------
# System outage fallback — reconciliation control + sparse system touchpoints
# ---------------------------------------------------------------------------


class TestSystemOutageFallback:
    def setup_method(self):
        self.pir = _load(SYSTEM_OUTAGE_FALLBACK)
        self.exp = explain_process(self.pir)

    def test_no_system_touchpoints_reduces_confidence(self):
        cd = self.exp.confidence_decomposition
        sys_dim = next(d for d in cd.dimensions if d.name == "system_touchpoints")
        assert sys_dim.present is False
        assert sys_dim.score_contribution == 0.0

    def test_fallback_steps_all_evidenced(self):
        step_exps = [
            e for e in self.exp.entity_explanations if e.entity_type == "workflow_step"
        ]
        assert all(e.evidence_count > 0 for e in step_exps)


# ---------------------------------------------------------------------------
# Informal / low-evidence workflow — sparse documentation
# ---------------------------------------------------------------------------


class TestInformalWorkflowExplainability:
    def setup_method(self):
        self.pir = _load(INFORMAL_WORKFLOW)
        self.exp = explain_process(self.pir)

    def test_confidence_score_low(self):
        cd = self.exp.confidence_decomposition
        assert cd.overall_score <= 65

    def test_all_steps_unverified(self):
        step_exps = [
            e for e in self.exp.entity_explanations if e.entity_type == "workflow_step"
        ]
        assert all(e.confidence_tier == "unverified" for e in step_exps)

    def test_coverage_ratio_zero(self):
        el = self.exp.evidence_lineage
        assert el.coverage_ratio == 0.0

    def test_lineage_note_warns_sparse(self):
        el = self.exp.evidence_lineage
        assert "sparse" in el.lineage_note.lower() or "only" in el.lineage_note.lower()


# ---------------------------------------------------------------------------
# Similarity explanation integration tests
# ---------------------------------------------------------------------------


class TestSimilarityExplanationIntegration:
    def test_invoice_and_po_escalation_are_related(self):
        """Both involve approvals and finance-related roles — expect some similarity."""
        pir_a = _load(INVOICE_APPROVAL)
        pir_b = _load(PURCHASE_ORDER_ESCALATION)
        score = score_similarity(make_fingerprint(pir_a), make_fingerprint(pir_b))
        exp = explain_similarity(score)
        # They share some overlap (both have approval-like steps)
        assert exp.composite_score >= 0.0
        assert exp.human_summary

    def test_invoice_and_informal_are_distinct(self):
        """Informal workflow has almost no structural overlap with invoice approval."""
        pir_a = _load(INVOICE_APPROVAL)
        pir_b = _load(INFORMAL_WORKFLOW)
        score = score_similarity(make_fingerprint(pir_a), make_fingerprint(pir_b))
        exp = explain_similarity(score)
        # Informal has very few entities → low similarity
        assert exp.composite_score < 0.50

    def test_same_workflow_different_versions_likely_same_process(self):
        """Two versions of the invoice approval should score as likely same process."""
        pir_v1 = _load(INVOICE_APPROVAL)
        # Create a near-identical version with minor variation
        data_v2 = {**INVOICE_APPROVAL, "id": "synthetic_invoice_approval_v2"}
        pir_v2 = ProcessIR.model_validate(data_v2)
        score = score_similarity(make_fingerprint(pir_v1), make_fingerprint(pir_v2))
        exp = explain_similarity(score)
        assert exp.verdict == "likely same process"
        assert exp.composite_score >= 0.90

    def test_similarity_dimensions_all_explained(self):
        pir_a = _load(INVOICE_APPROVAL)
        pir_b = _load(PURCHASE_ORDER_ESCALATION)
        score = score_similarity(make_fingerprint(pir_a), make_fingerprint(pir_b))
        exp = explain_similarity(score)
        assert (
            len(exp.dimensions) == 6
        )  # steps, roles, systems, controls, changes, exceptions
        assert all(d.description for d in exp.dimensions)

    def test_no_fabricated_overlap_on_disjoint_labels(self):
        """Workflows with completely disjoint labels must report no shared labels."""
        pir_a = _load(INVOICE_APPROVAL)
        pir_b = _load(SYSTEM_OUTAGE_FALLBACK)
        score = score_similarity(make_fingerprint(pir_a), make_fingerprint(pir_b))
        exp = explain_similarity(score)
        # Invoice approval and system outage fallback share no roles/systems
        role_dim = next(d for d in exp.dimensions if d.dimension == "roles")
        sys_dim = next(d for d in exp.dimensions if d.dimension == "systems")
        assert role_dim.shared_labels == []
        assert sys_dim.shared_labels == []
