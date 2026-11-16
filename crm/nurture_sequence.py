"""Draft-only sales follow-up sequence.

No invented customer wins, testimonials, financial figures or booking URLs.
Every message requires operator review and appropriate contact permission.
"""

NURTURE_SEQUENCE = [
    {
        "day": 1,
        "subject": "Garcar Enterprise — lead follow-up review",
        "body": """Hello,

Garcar Enterprise offers a $497 review of a recent CRM lead export.
The review identifies callback gaps and returns prioritized follow-up recommendations.

If this would be useful, reply to discuss the scope.

Garcar Enterprise
""",
        "requires_operator_approval": True,
    },
    {
        "day": 2,
        "subject": "What a lead follow-up review checks",
        "body": """Hello,

The $497 review examines timestamps, contact attempts and unanswered leads in an export you authorize us to review.

The findings depend on the quality of the source data. No recovery or revenue outcome is guaranteed.

Garcar Enterprise
""",
        "requires_operator_approval": True,
    },
    {
        "day": 3,
        "subject": "Your existing CRM remains the system of record",
        "body": """Hello,

The initial review uses your authorized CRM export; it does not require replacing your CRM.

If you want an implementation after reviewing the findings, we can discuss an appropriately scoped installation.

Garcar Enterprise
""",
        "requires_operator_approval": True,
    },
    {
        "day": 5,
        "subject": "Follow-up workflow questions",
        "body": """Hello,

How does your team identify leads that have not received a timely response?
A lead-export review can identify gaps in the records supplied.

Garcar Enterprise
""",
        "requires_operator_approval": True,
    },
    {
        "day": 7,
        "subject": "An evidence-based review, not a projected ROI",
        "body": """Hello,

We will not promise recovered leads or quote unverified customer results.
The review documents only findings supported by the data supplied and the analysis performed.

Garcar Enterprise
""",
        "requires_operator_approval": True,
    },
    {
        "day": 10,
        "subject": "Lead review and optional installation",
        "body": """Hello,

Our published scope is a $497 lead follow-up review, with an optional $2,500 implementation subject to a confirmed scope and available payment method.

Reply if you would like to review what is included.

Garcar Enterprise
""",
        "requires_operator_approval": True,
    },
    {
        "day": 14,
        "subject": "Closing this follow-up",
        "body": """Hello,

This is the last draft in the follow-up sequence. If the lead review is relevant, you can reply.

If you prefer no further outreach, reply with a stop request.

Garcar Enterprise
""",
        "requires_operator_approval": True,
    },
]


def get_sequence():
    """Return drafts only; do not enroll, schedule or send without authorization."""
    return NURTURE_SEQUENCE


if __name__ == "__main__":
    for email in NURTURE_SEQUENCE:
        print(f"Day {email['day']}: {email['subject']} (operator approval required)")
