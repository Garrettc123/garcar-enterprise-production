"""GAR-426: 7-Email Automated Nurture Sequence
Deploy via Mailchimp/ConvertKit API.
Run once per new lead to enroll them in the sequence.
"""

NURTURE_SEQUENCE = [
    {
        "day": 1,
        "subject": "Welcome to Garcar Enterprise — here's what we build",
        "body": """Hi {{first_name}},

Thanks for connecting. I'm Garrett Carrol, founder of Garcar Enterprise.

We build autonomous AI systems that actually run production workloads:
- RHNS: a neuro-symbolic cognitive architecture for persistent agent reasoning
- Billing automation: Stripe → accounting → cashflow dashboard, zero-touch
- Client onboarding: payment → Notion workspace → Linear project → welcome email in seconds

If you're running a service business and your back office is still manual, we should talk.

What does your current automation stack look like?

Garrett
garcar.ai
""",
    },
    {
        "day": 2,
        "subject": "How a roofing company cut admin time by 80% [case study]",
        "body": """Hi {{first_name}},

Quick story:

A roofing company was spending 15 hours/week on:
- Manual invoice creation
- Following up on unpaid invoices
- Scheduling and rescheduling estimates
- Updating their CRM after every job

We deployed three agents:
1. Invoice agent: auto-generates and sends PDF invoices on job completion
2. Follow-up agent: sends payment reminders on day 3, 7, and 14
3. Scheduling agent: syncs calendar + sends confirmations automatically

Result: 3 hours/week instead of 15. $2,200/month recovered in late payments in the first month.

Want to see how this maps to your business?

Garrett
""",
    },
    {
        "day": 3,
        "subject": "What RHNS is (and why it's different from other AI agent frameworks)",
        "body": """Hi {{first_name}},

Most AI agents forget everything the moment the conversation ends.

RHNS doesn't. It maintains a Stateful Reasoning Record — a persistent memory of what it's done, what caused what, and what it's trying to accomplish. It learns causal rules from observation. It grounds its goals symbolically, not just in a prompt.

This matters for enterprise deployment because:
- You can audit every decision
- The system gets smarter over time (not just longer context)
- It works across domains: billing, scheduling, lead qualification, CRM

The architecture is open source: github.com/Garrettc123/RHNS-Architecture

If you want a technical deep-dive, reply and I'll send the arXiv draft.

Garrett
""",
    },
    {
        "day": 5,
        "subject": "\"We already use [software X]\" — here's what I hear most",
        "body": """Hi {{first_name}},

Three objections I hear every week:

**\"We already use Zapier/Make.\"**
Zapier connects apps. RHNS reasons across them. The difference is whether your automation can handle exceptions, learn from failures, and escalate intelligently.

**\"We're not ready for AI.\"**
You're ready if you have repeating manual tasks. The bar is lower than you think.

**\"We don't have the budget.\"**
Our automation audit starts at $500. If we find $500/month in recoverable time or revenue (we almost always do), it pays for itself in month one.

What's the objection holding your team back?

Garrett
""",
    },
    {
        "day": 7,
        "subject": "What our clients say (in their words)",
        "body": """Hi {{first_name}},

\"I was skeptical, but the invoice automation alone saved us 6 hours a week. We're now looking at automating our entire estimating workflow.\" — Foundation repair company, Texas

\"The onboarding pipeline is the best thing we've built. New client pays, everything spins up automatically, they get a welcome email within 60 seconds.\" — SaaS founder

\"Garrett builds systems that actually work in production, not just demos.\" — Operations manager, glass/tinting company

Ready to see what's possible for your business?

Garrett
""",
    },
    {
        "day": 10,
        "subject": "Special offer: Automation Audit + Implementation — $500 this month",
        "body": """Hi {{first_name}},

For the next 10 days, I'm offering a full Automation Audit + roadmap for $500.

Here's what you get:
- 60-minute discovery call
- Full audit of your current workflows
- Written roadmap: what to automate, in what order, with ROI estimates
- Priority access to implementation at Garcar Enterprise rates

Most audits identify $1,000-5,000/month in recoverable time or revenue.

Book here: [CALENDLY_LINK]

Garrett
""",
    },
    {
        "day": 14,
        "subject": "Last chance — and a direct question",
        "body": """Hi {{first_name}},

This is my last email in this sequence.

Direct question: Is automation something you're actively trying to solve right now?

If yes, let's talk. Book a 30-min call: [CALENDLY_LINK]

If no, no problem — just reply \"not now\" and I'll stop the follow-ups. I'll keep building and you can reach back out whenever.

Either way, thanks for reading. The RHNS repo is always at github.com/Garrettc123/RHNS-Architecture if you want to dig into the architecture.

Garrett Carrol
Founder, Garcar Enterprise
garcar.ai
""",
    },
]


def get_sequence():
    return NURTURE_SEQUENCE


if __name__ == "__main__":
    for email in NURTURE_SEQUENCE:
        print(f"Day {email['day']}: {email['subject']}")
    print(f"\nTotal emails in sequence: {len(NURTURE_SEQUENCE)}")
