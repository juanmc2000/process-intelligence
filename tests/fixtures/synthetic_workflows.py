"""Synthetic operational workflow fixtures for testing explainability and extraction.

All examples are synthetic — no real customer data.  Fixtures cover a range of
operational workflow archetypes:

- Approval workflows (standard, threshold-based)
- Escalation paths
- Override / exception-handling workflows
- Fallback procedures
- Informal operational behavior

Each fixture is a complete ProcessIR dict with evidence_refs included so
explainability tests can verify coverage ratios and confidence tiers.

Fixture schema mirrors packages.core.schemas.process_ir.ProcessIR.
"""

from uuid import uuid4


def _ref(loc: str | None = None) -> dict:
    return {"artifact_uri": "minio://test/synthetic.json", "location_hint": loc}


# ---------------------------------------------------------------------------
# 1. Standard invoice approval workflow
# ---------------------------------------------------------------------------

INVOICE_APPROVAL: dict = {
    "id": "synthetic_invoice_approval",
    "run_id": str(uuid4()),
    "source_artifact_uri": "minio://test/invoice_approval.json",
    "schema_version": "process-ir-v1",
    "workflow_steps": [
        {
            "id": "ia_s1",
            "name": "Submit Invoice",
            "sequence_order": 1,
            "role": "Accounts Payable Clerk",
            "system": "SAP",
            "evidence_refs": [_ref("page 2"), _ref("page 3")],
        },
        {
            "id": "ia_s2",
            "name": "3-Way Match Validation",
            "sequence_order": 2,
            "system": "SAP",
            "evidence_refs": [_ref("page 4"), _ref("page 5"), _ref("page 6")],
        },
        {
            "id": "ia_s3",
            "name": "Manager Approval",
            "sequence_order": 3,
            "role": "Finance Manager",
            "evidence_refs": [_ref("page 7"), _ref("page 8")],
        },
        {
            "id": "ia_s4",
            "name": "Payment Release",
            "sequence_order": 4,
            "role": "Accounts Payable Clerk",
            "system": "SAP",
            "evidence_refs": [_ref("page 9")],
        },
    ],
    "roles": [
        {"id": "ia_r1", "name": "Accounts Payable Clerk"},
        {"id": "ia_r2", "name": "Finance Manager"},
    ],
    "system_touchpoints": [
        {
            "id": "ia_t1",
            "name": "SAP",
            "system_name": "SAP",
            "interaction_type": "write",
            "evidence_refs": [_ref("page 2")],
        }
    ],
    "controls": [
        {
            "id": "ia_c1",
            "name": "3-Way Match Control",
            "control_type": "validation",
            "evidence_refs": [_ref("page 4"), _ref("page 5")],
        },
        {
            "id": "ia_c2",
            "name": "Dual Authorization",
            "control_type": "approval",
            "evidence_refs": [_ref("page 7")],
        },
    ],
    "exceptions": [],
    "decision_points": [
        {
            "id": "ia_d1",
            "name": "Amount Threshold Check",
            "conditions": ["Invoice amount > $50,000"],
            "outcomes": ["Route to CFO approval", "Proceed to Finance Manager"],
            "evidence_refs": [_ref("page 6")],
        }
    ],
    "change_events": [],
}


# ---------------------------------------------------------------------------
# 2. Escalation workflow — purchase order over threshold
# ---------------------------------------------------------------------------

PURCHASE_ORDER_ESCALATION: dict = {
    "id": "synthetic_po_escalation",
    "run_id": str(uuid4()),
    "source_artifact_uri": "minio://test/po_escalation.json",
    "schema_version": "process-ir-v1",
    "workflow_steps": [
        {
            "id": "po_s1",
            "name": "Create Purchase Order",
            "sequence_order": 1,
            "role": "Procurement Officer",
            "system": "Oracle",
            "evidence_refs": [_ref("para 1"), _ref("para 2")],
        },
        {
            "id": "po_s2",
            "name": "Department Head Review",
            "sequence_order": 2,
            "role": "Department Head",
            "evidence_refs": [_ref("para 3")],
        },
        {
            "id": "po_s3",
            "name": "CFO Escalation",
            "sequence_order": 3,
            "role": "CFO",
            "evidence_refs": [_ref("para 4"), _ref("para 5")],
        },
        {
            "id": "po_s4",
            "name": "Board Approval",
            "sequence_order": 4,
            "role": "Board",
            "evidence_refs": [_ref("para 6")],
        },
    ],
    "roles": [
        {"id": "po_r1", "name": "Procurement Officer"},
        {"id": "po_r2", "name": "Department Head"},
        {"id": "po_r3", "name": "CFO"},
        {"id": "po_r4", "name": "Board"},
    ],
    "system_touchpoints": [
        {
            "id": "po_t1",
            "name": "Oracle",
            "system_name": "Oracle",
            "evidence_refs": [_ref("para 1")],
        }
    ],
    "controls": [
        {
            "id": "po_c1",
            "name": "Spend Threshold Control",
            "control_type": "threshold",
            "evidence_refs": [_ref("para 4")],
        }
    ],
    "exceptions": [
        {
            "id": "po_x1",
            "name": "Emergency Purchase Override",
            "description": "Allows bypass of standard approval chain for urgent purchases",
            "handling_steps": [
                "Document business justification",
                "Notify CFO via email",
                "Retrospective approval within 48 hours",
            ],
            "evidence_refs": [_ref("para 7")],
        }
    ],
    "decision_points": [
        {
            "id": "po_d1",
            "name": "Escalation Gate",
            "conditions": ["Amount > $100,000", "Cross-department impact"],
            "outcomes": ["Escalate to CFO", "Department Head approval sufficient"],
            "evidence_refs": [_ref("para 3")],
        }
    ],
    "change_events": [],
}


# ---------------------------------------------------------------------------
# 3. Exception handling — payment dispute resolution
# ---------------------------------------------------------------------------

PAYMENT_DISPUTE: dict = {
    "id": "synthetic_payment_dispute",
    "run_id": str(uuid4()),
    "source_artifact_uri": "minio://test/payment_dispute.json",
    "schema_version": "process-ir-v1",
    "workflow_steps": [
        {
            "id": "pd_s1",
            "name": "Dispute Raised",
            "sequence_order": 1,
            "role": "Customer",
            "evidence_refs": [_ref("section 1")],
        },
        {
            "id": "pd_s2",
            "name": "Initial Review",
            "sequence_order": 2,
            "role": "Accounts Receivable",
            "system": "Salesforce",
            "evidence_refs": [_ref("section 2"), _ref("section 3")],
        },
        {
            "id": "pd_s3",
            "name": "Document Collection",
            "sequence_order": 3,
            "role": "Accounts Receivable",
            "evidence_refs": [_ref("section 4")],
        },
        {
            "id": "pd_s4",
            "name": "Resolution Decision",
            "sequence_order": 4,
            "role": "Credit Manager",
            "evidence_refs": [_ref("section 5"), _ref("section 6")],
        },
        {
            "id": "pd_s5",
            "name": "Adjustment Posting",
            "sequence_order": 5,
            "role": "Accounts Receivable",
            "system": "SAP",
            "evidence_refs": [_ref("section 7")],
        },
    ],
    "roles": [
        {"id": "pd_r1", "name": "Customer"},
        {"id": "pd_r2", "name": "Accounts Receivable"},
        {"id": "pd_r3", "name": "Credit Manager"},
    ],
    "system_touchpoints": [
        {
            "id": "pd_t1",
            "name": "Salesforce",
            "system_name": "Salesforce",
            "evidence_refs": [_ref("section 2")],
        },
        {
            "id": "pd_t2",
            "name": "SAP",
            "system_name": "SAP",
            "evidence_refs": [_ref("section 7")],
        },
    ],
    "controls": [
        {
            "id": "pd_c1",
            "name": "Dual Sign-Off on Credit Notes",
            "control_type": "segregation_of_duties",
            "evidence_refs": [_ref("section 5")],
        }
    ],
    "exceptions": [
        {
            "id": "pd_x1",
            "name": "Dispute Exceeds Tolerance",
            "description": "Disputes > $10,000 require legal involvement",
            "handling_steps": ["Escalate to Legal", "Freeze account", "Notify CFO"],
            "evidence_refs": [_ref("section 8")],
        },
        {
            "id": "pd_x2",
            "name": "Repeated Disputer",
            "description": "Customer with 3+ disputes in 12 months",
            "handling_steps": ["Flag account", "Require pre-payment"],
            "evidence_refs": [],
        },
    ],
    "decision_points": [],
    "change_events": [
        {
            "id": "pd_ce1",
            "name": "Credit Policy Updated",
            "description": "Tolerance limit raised from $5k to $10k",
            "trigger": "Board decision Q3 2024",
            "impact": "More disputes handled internally without Legal",
            "evidence_refs": [_ref("appendix A")],
        }
    ],
}


# ---------------------------------------------------------------------------
# 4. Fallback procedure — system outage
# ---------------------------------------------------------------------------

SYSTEM_OUTAGE_FALLBACK: dict = {
    "id": "synthetic_system_outage_fallback",
    "run_id": str(uuid4()),
    "source_artifact_uri": "minio://test/outage_fallback.json",
    "schema_version": "process-ir-v1",
    "workflow_steps": [
        {
            "id": "sf_s1",
            "name": "Detect System Outage",
            "sequence_order": 1,
            "role": "IT Operations",
            "evidence_refs": [_ref("procedure 1.1")],
        },
        {
            "id": "sf_s2",
            "name": "Switch to Manual Processing",
            "sequence_order": 2,
            "role": "Operations Team",
            "evidence_refs": [_ref("procedure 1.2"), _ref("procedure 1.3")],
        },
        {
            "id": "sf_s3",
            "name": "Log Transactions in Spreadsheet",
            "sequence_order": 3,
            "role": "Operations Team",
            "evidence_refs": [_ref("procedure 2.1")],
        },
        {
            "id": "sf_s4",
            "name": "Notify Stakeholders",
            "sequence_order": 4,
            "role": "IT Operations",
            "evidence_refs": [_ref("procedure 2.2")],
        },
        {
            "id": "sf_s5",
            "name": "Reconcile on System Restoration",
            "sequence_order": 5,
            "role": "Operations Team",
            "evidence_refs": [_ref("procedure 3.1"), _ref("procedure 3.2")],
        },
    ],
    "roles": [
        {"id": "sf_r1", "name": "IT Operations"},
        {"id": "sf_r2", "name": "Operations Team"},
    ],
    "system_touchpoints": [],
    "controls": [
        {
            "id": "sf_c1",
            "name": "Manual Reconciliation Check",
            "control_type": "reconciliation",
            "evidence_refs": [_ref("procedure 3.1")],
        }
    ],
    "exceptions": [
        {
            "id": "sf_x1",
            "name": "Outage Exceeds 4 Hours",
            "description": "Extended outage triggers crisis protocol",
            "handling_steps": [
                "Escalate to CTO",
                "Activate disaster recovery",
                "Notify customers",
            ],
            "evidence_refs": [_ref("appendix B")],
        }
    ],
    "decision_points": [
        {
            "id": "sf_d1",
            "name": "Outage Duration Gate",
            "conditions": ["Outage < 4 hours", "Outage >= 4 hours"],
            "outcomes": ["Continue manual processing", "Activate crisis protocol"],
            "evidence_refs": [_ref("procedure 2.3")],
        }
    ],
    "change_events": [],
}


# ---------------------------------------------------------------------------
# 5. Informal / low-evidence workflow — sparse documentation
# ---------------------------------------------------------------------------

INFORMAL_WORKFLOW: dict = {
    "id": "synthetic_informal_workflow",
    "run_id": str(uuid4()),
    "source_artifact_uri": "minio://test/informal.json",
    "schema_version": "process-ir-v1",
    "workflow_steps": [
        {
            "id": "iw_s1",
            "name": "Someone checks the spreadsheet",
            "sequence_order": 1,
            "evidence_refs": [],  # no evidence
        },
        {
            "id": "iw_s2",
            "name": "Email sent to manager",
            "sequence_order": 2,
            "evidence_refs": [],  # no evidence
        },
    ],
    "roles": [
        {"id": "iw_r1", "name": "Someone"},  # vague role
    ],
    "system_touchpoints": [],
    "controls": [],
    "exceptions": [],
    "decision_points": [],
    "change_events": [],
}


# ---------------------------------------------------------------------------
# Exported collection
# ---------------------------------------------------------------------------

ALL_SYNTHETIC_WORKFLOWS: list[dict] = [
    INVOICE_APPROVAL,
    PURCHASE_ORDER_ESCALATION,
    PAYMENT_DISPUTE,
    SYSTEM_OUTAGE_FALLBACK,
    INFORMAL_WORKFLOW,
]

# Workflow IDs for convenient lookup
WORKFLOW_IDS = [w["id"] for w in ALL_SYNTHETIC_WORKFLOWS]
