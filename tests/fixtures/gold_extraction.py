"""Gold dataset for deterministic extraction evaluation.

Each fixture is a synthetic text with expected entities, relations, and action
classifications. All examples are synthetic — no real customer data.

Structure per fixture:
    {
        "id": str,
        "text": str,
        "description": str,
        "expected_entities": [{"type": str, "label": str}],
        "expected_relations": [{"type": str, "source_label": str, "target_label": str}],
        "expected_action_classes": [str],
        "is_negative": bool,   # True for negated/speculative examples
    }
"""

GOLD_FIXTURES: list[dict] = [
    # --- Approval workflow ---
    {
        "id": "gold_approval_01",
        "text": "The Finance Manager approved the Invoice in SAP after reviewing the supporting documentation.",
        "description": "Standard approval by a named role in a known system.",
        "expected_entities": [
            {"type": "ROLE", "label": "Finance Manager"},
            {"type": "WORKFLOW_OBJECT", "label": "Invoice"},
            {"type": "SYSTEM", "label": "SAP"},
        ],
        "expected_relations": [
            {
                "type": "approves",
                "source_label": "Finance Manager",
                "target_label": "Invoice",
            },
        ],
        "expected_action_classes": ["APPROVAL"],
        "is_negative": False,
    },
    # --- Rejection workflow ---
    {
        "id": "gold_rejection_01",
        "text": "The purchase order was rejected by the Controller due to missing vendor details.",
        "description": "Rejection with a reason by a known role.",
        "expected_entities": [
            {"type": "WORKFLOW_OBJECT", "label": "Purchase Order"},
            {"type": "ROLE", "label": "Controller"},
        ],
        "expected_relations": [
            {
                "type": "rejects",
                "source_label": "Controller",
                "target_label": "Purchase Order",
            },
        ],
        "expected_action_classes": ["REJECTION"],
        "is_negative": False,
    },
    # --- Handoff ---
    {
        "id": "gold_handoff_01",
        "text": "The ticket was assigned to the Legal Department for compliance review.",
        "description": "Handoff from one team to another.",
        "expected_entities": [
            {"type": "WORKFLOW_OBJECT", "label": "Ticket"},
            {"type": "DEPARTMENT", "label": "Legal"},
        ],
        "expected_relations": [
            {"type": "handoff_to", "source_label": "Ticket", "target_label": "Legal"},
        ],
        "expected_action_classes": ["HANDOFF"],
        "is_negative": False,
    },
    # --- Escalation ---
    {
        "id": "gold_escalation_01",
        "text": "The payment dispute was escalated to Senior Management after three failed resolution attempts.",
        "description": "Escalation to a higher authority.",
        "expected_entities": [
            {"type": "WORKFLOW_OBJECT", "label": "Payment"},
        ],
        "expected_relations": [
            {
                "type": "escalates_to",
                "source_label": "Payment",
                "target_label": "Senior Management",
            },
        ],
        "expected_action_classes": ["ESCALATION"],
        "is_negative": False,
    },
    # --- System entry ---
    {
        "id": "gold_system_entry_01",
        "text": "The journal entry was entered in Oracle by the Clerk on the last business day of the month.",
        "description": "Data entry into a known system.",
        "expected_entities": [
            {"type": "WORKFLOW_OBJECT", "label": "Journal Entry"},
            {"type": "SYSTEM", "label": "Oracle"},
            {"type": "ROLE", "label": "Clerk"},
        ],
        "expected_relations": [
            {
                "type": "creates_in",
                "source_label": "Journal Entry",
                "target_label": "Oracle",
            },
        ],
        "expected_action_classes": ["SYSTEM_ENTRY"],
        "is_negative": False,
    },
    # --- Reconciliation control ---
    {
        "id": "gold_reconciliation_01",
        "text": "Monthly balances were reconciled against Oracle by the Auditor to ensure accuracy.",
        "description": "Reconciliation against a system.",
        "expected_entities": [
            {"type": "SYSTEM", "label": "Oracle"},
            {"type": "ROLE", "label": "Auditor"},
        ],
        "expected_relations": [],
        "expected_action_classes": ["RECONCILIATION"],
        "is_negative": False,
    },
    # --- Threshold control ---
    {
        "id": "gold_threshold_01",
        "text": "Any purchase order above $50,000 requires approval from the CFO before processing.",
        "description": "Threshold control with a monetary limit.",
        "expected_entities": [
            {"type": "WORKFLOW_OBJECT", "label": "Purchase Order"},
            {"type": "ROLE", "label": "CFO"},
        ],
        "expected_relations": [],
        "expected_action_classes": ["APPROVAL"],
        "is_negative": False,
    },
    # --- Exception raised ---
    {
        "id": "gold_exception_raised_01",
        "text": "A discrepancy was identified during the month-end reconciliation of vendor payments.",
        "description": "Exception detected during a control process.",
        "expected_entities": [
            {"type": "EXCEPTION", "label": "Discrepancy"},
        ],
        "expected_relations": [],
        "expected_action_classes": ["EXCEPTION_RAISED"],
        "is_negative": False,
    },
    # --- Exception resolved ---
    {
        "id": "gold_exception_resolved_01",
        "text": "The variance was resolved by the Finance team after investigating the source transaction.",
        "description": "Exception resolution.",
        "expected_entities": [
            {"type": "DEPARTMENT", "label": "Finance"},
        ],
        "expected_relations": [],
        "expected_action_classes": ["EXCEPTION_RESOLVED"],
        "is_negative": False,
    },
    # --- Change event ---
    {
        "id": "gold_change_01",
        "text": "The approval threshold changed from $10,000 to $25,000 effective January 2025.",
        "description": "Change event with old and new values.",
        "expected_entities": [
            {"type": "CHANGE_EVENT", "label": "Change"},
        ],
        "expected_relations": [],
        "expected_action_classes": ["CHANGE_MADE"],
        "is_negative": False,
    },
    # --- Speculative negative example ---
    {
        "id": "gold_negative_speculative_01",
        "text": "We might implement a new dual-approval process for high-value transactions in the future.",
        "description": "Speculative statement — should NOT produce factual entities.",
        "expected_entities": [],
        "expected_relations": [],
        "expected_action_classes": [],
        "is_negative": True,
    },
    # --- Negation negative example ---
    {
        "id": "gold_negative_negated_01",
        "text": "The invoice has not been approved yet. The payment cannot be processed until approval is received.",
        "description": "Negated statement — approval has NOT happened.",
        "expected_entities": [],
        "expected_relations": [],
        "expected_action_classes": [],
        "is_negative": True,
    },
]
