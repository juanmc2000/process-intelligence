"""Unit tests for the deterministic process extractor.

Tests cover entity extraction, relation extraction, action classification,
temporal cues, negation/speculative filtering, and confidence scoring.
All examples are synthetic — no real customer data.
"""

from packages.core.process_ir.classifier import classify_sentences, predict_action_class
from packages.core.process_ir.extractor import extract
from packages.core.process_ir.gazetteer import Gazetteer
from packages.core.process_ir.negation import (
    filter_negated_sentences,
    is_negated,
    is_speculative,
)
from packages.core.process_ir.patterns import extract_patterns
from packages.core.process_ir.relations import extract_temporal_cues
from packages.core.process_ir.types import (
    ActionClass,
    EntityType,
    ExtractionMethod,
    RelationType,
)


# --- Gazetteer tests ---


class TestGazetteer:
    def test_exact_system_match(self):
        gaz = Gazetteer()
        matches = gaz.match("The invoice was entered in SAP by the clerk.")
        systems = [m for m in matches if m.entity_type == EntityType.SYSTEM]
        assert any(m.canonical_id == "system:sap" for m in systems)

    def test_alias_match(self):
        gaz = Gazetteer()
        matches = gaz.match("Data was loaded into the ERP system.")
        systems = [m for m in matches if m.entity_type == EntityType.SYSTEM]
        assert any(m.canonical_id == "system:sap" for m in systems)
        alias_matches = [m for m in systems if m.method == ExtractionMethod.ALIAS]
        assert len(alias_matches) > 0

    def test_case_insensitive(self):
        gaz = Gazetteer()
        matches = gaz.match("the finance department reviews all invoices.")
        depts = [m for m in matches if m.entity_type == EntityType.DEPARTMENT]
        assert any(m.canonical_id == "dept:finance" for m in depts)

    def test_longest_span_wins(self):
        gaz = Gazetteer()
        matches = gaz.match("The Finance Manager approved the request.")
        # "Finance Manager" should be matched as a role, not "Finance" as dept + "Manager" as role
        role_matches = [m for m in matches if m.entity_type == EntityType.ROLE]
        assert any(m.canonical_label == "Finance Manager" for m in role_matches)

    def test_confidence_exact_vs_alias(self):
        gaz = Gazetteer()
        exact = gaz.match("SAP is used.")
        alias = gaz.match("ERP is used.")
        exact_sys = [m for m in exact if m.canonical_id == "system:sap"]
        alias_sys = [m for m in alias if m.canonical_id == "system:sap"]
        assert exact_sys[0].confidence == 0.95
        assert alias_sys[0].confidence == 0.90

    def test_control_detection(self):
        gaz = Gazetteer()
        matches = gaz.match("Segregation of duties is enforced.")
        controls = [m for m in matches if m.entity_type == EntityType.CONTROL]
        assert any(m.canonical_id == "control:sod" for m in controls)

    def test_multiple_entities(self):
        gaz = Gazetteer()
        text = "The Auditor reconciled the Invoice in SAP."
        matches = gaz.match(text)
        types_found = {m.entity_type for m in matches}
        assert EntityType.ROLE in types_found
        assert EntityType.SYSTEM in types_found

    def test_workflow_object_detection(self):
        gaz = Gazetteer()
        matches = gaz.match("The purchase order was submitted.")
        wos = [m for m in matches if m.entity_type == EntityType.WORKFLOW_OBJECT]
        assert any(m.canonical_label == "Purchase Order" for m in wos)


# --- Regex pattern tests ---


class TestPatterns:
    def test_approved_by(self):
        matches = extract_patterns("The request was approved by Finance Manager.")
        assert any(m.action_class == ActionClass.APPROVAL and m.actor for m in matches)

    def test_rejected_by(self):
        matches = extract_patterns("The invoice was rejected by the Controller.")
        assert any(m.action_class == ActionClass.REJECTION for m in matches)

    def test_escalated_to(self):
        matches = extract_patterns("The issue was escalated to Senior Management.")
        assert any(m.action_class == ActionClass.ESCALATION for m in matches)

    def test_handoff_sent_to(self):
        matches = extract_patterns("The case was sent to Legal Department.")
        assert any(m.action_class == ActionClass.HANDOFF for m in matches)

    def test_system_entry(self):
        matches = extract_patterns("The invoice was entered in SAP.")
        assert any(m.action_class == ActionClass.SYSTEM_ENTRY for m in matches)

    def test_reconciled_against(self):
        matches = extract_patterns("Balances were reconciled against Oracle.")
        assert any(m.action_class == ActionClass.RECONCILIATION for m in matches)

    def test_changed_from_to(self):
        matches = extract_patterns("Approval threshold changed from $5000 to $10000.")
        change_matches = [
            m for m in matches if m.action_class == ActionClass.CHANGE_MADE
        ]
        assert len(change_matches) > 0
        assert change_matches[0].old_value is not None
        assert change_matches[0].new_value is not None

    def test_threshold_detection(self):
        matches = extract_patterns("Requires approval above $50,000.")
        assert any(m.threshold for m in matches)

    def test_exception_raised(self):
        matches = extract_patterns("An exception was raised during reconciliation.")
        assert any(m.action_class == ActionClass.EXCEPTION_RAISED for m in matches)

    def test_exception_resolved(self):
        matches = extract_patterns("The discrepancy was resolved by the team.")
        assert any(m.action_class == ActionClass.EXCEPTION_RESOLVED for m in matches)


# --- Action classification tests ---


class TestClassifier:
    def test_approval_classification(self):
        result = predict_action_class("The invoice was approved by the manager.")
        assert result.action_class == ActionClass.APPROVAL

    def test_rejection_classification(self):
        result = predict_action_class(
            "The request was denied due to missing documentation."
        )
        assert result.action_class == ActionClass.REJECTION

    def test_escalation_classification(self):
        result = predict_action_class("The matter was escalated to senior leadership.")
        assert result.action_class == ActionClass.ESCALATION

    def test_handoff_classification(self):
        result = predict_action_class("The task was assigned to the operations team.")
        assert result.action_class == ActionClass.HANDOFF

    def test_system_entry_classification(self):
        result = predict_action_class("The data was entered in the system.")
        assert result.action_class == ActionClass.SYSTEM_ENTRY

    def test_unknown_classification(self):
        result = predict_action_class("The weather is nice today.")
        assert result.action_class == ActionClass.UNKNOWN

    def test_classify_sentences_filters_unknown(self):
        text = "The invoice was approved. The weather is nice. The payment was escalated to management."
        results = classify_sentences(text)
        classes = {r.action_class for r in results}
        assert ActionClass.UNKNOWN not in classes
        assert ActionClass.APPROVAL in classes

    def test_confidence_range(self):
        result = predict_action_class("The invoice was approved.")
        assert 0.0 <= result.confidence <= 1.0


# --- Temporal cue tests ---


class TestTemporalCues:
    def test_before_cue(self):
        cues = extract_temporal_cues("The review must happen before the approval.")
        assert any(c.relation == RelationType.PRECEDES for c in cues)

    def test_after_cue(self):
        cues = extract_temporal_cues("After validation, the payment is released.")
        assert any(c.relation == RelationType.FOLLOWS for c in cues)

    def test_then_cue(self):
        cues = extract_temporal_cues("Submit the form, then wait for approval.")
        assert any(c.relation == RelationType.FOLLOWS for c in cues)

    def test_triggered_by(self):
        cues = extract_temporal_cues("Payment is triggered by invoice approval.")
        assert any(c.relation == RelationType.TRIGGERED_BY for c in cues)

    def test_conditioned_on(self):
        cues = extract_temporal_cues("Release is conditioned on manager sign-off.")
        assert any(c.relation == RelationType.CONDITIONED_ON for c in cues)


# --- Negation tests ---


class TestNegation:
    def test_negated_sentence(self):
        assert is_negated("The invoice was not approved.")
        assert is_negated("No approval was granted.")
        assert is_negated("The process has never been completed.")

    def test_non_negated_sentence(self):
        assert not is_negated("The invoice was approved by the manager.")

    def test_speculative_sentence(self):
        assert is_speculative("The process might change in the future.")
        assert is_speculative("We are considering a new approval workflow.")
        assert is_speculative("This could potentially impact the timeline.")

    def test_non_speculative_sentence(self):
        assert not is_speculative("The invoice was approved by the manager.")

    def test_filter_negated_sentences(self):
        sentences = [
            "The invoice was approved.",
            "The payment was not processed.",
            "We might change the process.",
            "The report was submitted.",
        ]
        factual, filtered = filter_negated_sentences(sentences)
        assert len(factual) == 2
        assert len(filtered) == 2
        assert "The invoice was approved." in factual
        assert "The report was submitted." in factual


# --- Full extraction pipeline tests ---


class TestExtractor:
    def test_basic_extraction(self):
        text = "The Finance Manager approved the Invoice in SAP."
        result = extract(text, evidence_id="test_1")
        assert result.evidence_id == "test_1"
        assert len(result.entities) > 0

    def test_entities_have_confidence_and_method(self):
        text = "The Auditor validated the Journal Entry."
        result = extract(text)
        for entity in result.entities:
            assert 0.0 <= entity.confidence <= 1.0
            assert entity.method is not None

    def test_relations_have_confidence_and_method(self):
        text = "The invoice was approved by Finance Manager. The payment was entered in SAP."
        result = extract(text)
        for rel in result.relations:
            assert 0.0 <= rel.confidence <= 1.0
            assert rel.method is not None

    def test_negated_content_filtered(self):
        text = "The invoice was not approved. The payment was processed in SAP."
        result = extract(text)
        assert result.has_negated_content is True
        # Should still find entities from the factual sentence
        systems = [e for e in result.entities if e.type == EntityType.SYSTEM]
        assert len(systems) > 0

    def test_speculative_content_flagged(self):
        text = (
            "We might implement a new approval workflow. The current process uses SAP."
        )
        result = extract(text)
        assert result.has_speculative_content is True

    def test_approval_workflow(self):
        text = (
            "The purchase order is created by the Clerk. "
            "The Finance Manager reviews and approves the purchase order. "
            "Once approved, the payment is entered in SAP."
        )
        result = extract(text)

        # Should find roles
        roles = [e for e in result.entities if e.type == EntityType.ROLE]
        assert len(roles) > 0

        # Should find systems
        systems = [e for e in result.entities if e.type == EntityType.SYSTEM]
        assert any(e.canonical_label == "SAP" for e in systems)

        # Should find workflow objects
        wos = [e for e in result.entities if e.type == EntityType.WORKFLOW_OBJECT]
        assert len(wos) > 0

    def test_handoff_detection(self):
        text = "The case was assigned to the Legal Department for review."
        result = extract(text)
        # Should at least detect the handoff action class
        classes = {c.action_class for c in result.action_classifications}
        assert ActionClass.HANDOFF in classes

    def test_control_detection(self):
        text = "Segregation of duties is enforced for all payment approvals."
        result = extract(text)
        controls = [e for e in result.entities if e.type == EntityType.CONTROL]
        assert len(controls) > 0

    def test_change_event_detection(self):
        text = "The approval threshold changed from $5000 to $10000."
        result = extract(text)
        changes = [e for e in result.entities if e.type == EntityType.CHANGE_EVENT]
        assert len(changes) > 0

    def test_escalation_detection(self):
        text = "The dispute was escalated to Senior Management."
        result = extract(text)
        classes = {c.action_class for c in result.action_classifications}
        assert ActionClass.ESCALATION in classes

    def test_exception_detection(self):
        text = "A discrepancy was identified during the reconciliation process."
        result = extract(text)
        classes = {c.action_class for c in result.action_classifications}
        assert ActionClass.EXCEPTION_RAISED in classes

    def test_negative_example_not_treated_as_fact(self):
        """Negative/speculative statements should not produce entities from the negated clause."""
        text = "The invoice has not been approved yet. The system does not support automatic reconciliation."
        result = extract(text)
        assert result.has_negated_content is True
        # Entities from negated sentences should be filtered out
        # The approval and reconciliation should not appear as completed facts
        approvals = [
            c
            for c in result.action_classifications
            if c.action_class == ActionClass.APPROVAL
        ]
        assert len(approvals) == 0

    def test_multi_sentence_extraction(self):
        text = (
            "Step 1: The Clerk creates a purchase order in SAP. "
            "Step 2: The Finance Manager reviews and approves the order. "
            "Step 3: The payment is reconciled against Oracle. "
            "Step 4: The Auditor validates the reconciliation report."
        )
        result = extract(text)
        assert len(result.entities) >= 4
        assert len(result.action_classifications) >= 2

    def test_empty_text(self):
        result = extract("")
        assert len(result.entities) == 0
        assert len(result.relations) == 0
