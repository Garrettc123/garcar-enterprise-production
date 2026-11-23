"""Evidence-gated RHNS audit integration.

No estimated revenue, unverified customer claims, invented case studies,
automatic report delivery, or archival of unsupported conclusions.
A real fulfillment workflow must use verified customer data and operator approval.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.request
import urllib.error
from typing import Optional

from approval_gate import ApprovalRequired, require_approval

logger = logging.getLogger(__name__)
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "gwc2780@gmail.com")
STARTER_AUDIT_PRODUCT_IDS = {
    value.strip()
    for value in os.getenv("STARTER_AUDIT_PRODUCT_IDS", "").split(",")
    if value.strip().startswith("prod_")
}


def send_audit_report(to_email: str, to_name: str, company: str, html_body: str,
                      approval_id: Optional[str] = None) -> bool:
    """Send the audit report via SendGrid.

    GAR-530: needs a Garrett-issued ``send.email`` approval covering ``to_email``.
    """
    if not SENDGRID_API_KEY:
        logger.warning("SENDGRID_API_KEY not set — skipping email delivery")
        return False

    try:
        require_approval("send.email", approval_id, to=to_email,
                         site="backend.rhns_audit.send_audit_report")
    except ApprovalRequired as exc:
        logger.warning(f"Audit report email refused by approval gate: {exc.reason}")
        return False

    payload = {
        "personalizations": [{"to": [{"email": to_email, "name": to_name}]}],
        "from": {"email": FROM_EMAIL, "name": "Garcar Enterprise"},
        "subject": f"Your RHNS Revenue Audit — {company}",
        "content": [{"type": "text/html", "value": html_body}],
    }

    req = urllib.request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {SENDGRID_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            logger.info(f"Audit report sent to {to_email} — status {resp.status}")
            return True
    except urllib.error.HTTPError as e:
        logger.error(f"SendGrid error {e.code}: {e.read().decode()}")
        return False


def run_rhns_audit(
    customer_email: str,
    customer_name: str,
    company_name: str = "",
    checkout_metadata: Optional[dict] = None,
    engagement_id: Optional[str] = None,
    upsell_url: str = "",
    approval_id: Optional[str] = None,
) -> dict:
    """Do not claim a completed audit from checkout metadata alone.

    Source records, evidence and a signed-off deliverable are required.
    The paid order must be routed to manual fulfillment until that exists.
    """
    logger.error("RHNS audit needs verified customer source data and review; no report sent")
    return {
        "engagement_id": engagement_id,
        "email_sent": False,
        "archive_dispatched": False,
        "status": "requires_verified_data_and_manual_fulfillment",
    }
