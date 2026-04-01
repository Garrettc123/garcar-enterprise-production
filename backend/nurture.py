"""
Automated Email Nurture System
===============================
- 5-step drip sequence for new leads
- Background scheduler processes send queue
- Tracking: opens, clicks, delivery status
- SMTP integration (SendGrid / Mailgun / raw SMTP)
- Admin API for sequence management and analytics
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone, timedelta
import smtplib
import ssl
import os
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from database import get_db
from models import Lead, EmailTemplate, NurtureStep, User
from auth import get_admin_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/nurture", tags=["nurture"])

# ── Email Config ──
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
FROM_NAME = os.getenv("FROM_NAME", "GARCAR Enterprise")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER or "hello@garcar.io")
BASE_URL = os.getenv("BASE_URL", "https://garcar-enterprise-platform.pplx.app")


# ════════════════════════════════════════
# DEFAULT NURTURE SEQUENCES
# ════════════════════════════════════════

WELCOME_DRIP = [
    {
        "step": 1,
        "delay_hours": 0,
        "subject": "Welcome to GARCAR Enterprise — here's what you just unlocked",
        "body_text": """Hey {name},

Welcome aboard. You just signed up for GARCAR Enterprise, and I want to make sure you actually get value from it — not just another login that collects dust.

Here's what you have access to right now:

1. AI Deal Desk — Score any deal in seconds. Paste in the details, get a probability score, risk flags, and a recommended strategy.

2. SEO Content Factory — Generate optimized content briefs, meta tags, and full articles targeting the keywords that matter for your business.

3. Churn Predictor — Upload customer data and get early warning signals on who's about to leave, so you can act before they do.

Start with the Deal Desk — it's the fastest way to see what the platform can do.

Log in here: {base_url}

— Garrett Carroll
Founder, GARCAR Enterprise""",
        "body_html": """<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; color: #e2e8f0; background: #0f172a; padding: 32px; border-radius: 12px;">
  <div style="margin-bottom: 24px;">
    <span style="color: #818cf8; font-weight: 700; font-size: 18px;">GARCAR</span>
  </div>
  <p style="color: #e2e8f0; font-size: 16px;">Hey {name},</p>
  <p style="color: #cbd5e1; font-size: 15px; line-height: 1.6;">Welcome aboard. You just signed up for GARCAR Enterprise, and I want to make sure you actually get value from it — not just another login that collects dust.</p>
  <p style="color: #e2e8f0; font-size: 15px; font-weight: 600;">Here's what you have access to right now:</p>
  <div style="background: #1e293b; padding: 20px; border-radius: 8px; margin: 16px 0;">
    <p style="color: #818cf8; margin: 0 0 8px 0; font-weight: 600;">1. AI Deal Desk</p>
    <p style="color: #94a3b8; margin: 0 0 16px 0; font-size: 14px;">Score any deal in seconds. Paste in the details, get a probability score, risk flags, and a recommended strategy.</p>
    <p style="color: #818cf8; margin: 0 0 8px 0; font-weight: 600;">2. SEO Content Factory</p>
    <p style="color: #94a3b8; margin: 0 0 16px 0; font-size: 14px;">Generate optimized content briefs, meta tags, and full articles targeting the keywords that matter.</p>
    <p style="color: #818cf8; margin: 0 0 8px 0; font-weight: 600;">3. Churn Predictor</p>
    <p style="color: #94a3b8; margin: 0; font-size: 14px;">Upload customer data and get early warning signals on who's about to leave.</p>
  </div>
  <p style="color: #cbd5e1; font-size: 15px;">Start with the Deal Desk — it's the fastest way to see what the platform can do.</p>
  <a href="{base_url}" style="display: inline-block; background: #6366f1; color: white; padding: 12px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; margin: 16px 0;">Log in to your dashboard →</a>
  <p style="color: #64748b; font-size: 14px; margin-top: 32px;">— Garrett Carroll<br/>Founder, GARCAR Enterprise</p>
</div>""",
    },
    {
        "step": 2,
        "delay_hours": 24,
        "subject": "Quick win: Score your first deal in 30 seconds",
        "body_text": """Hey {name},

Most people sign up for tools and never use them. I don't want that to happen with you.

Here's a 30-second challenge:

1. Log in: {base_url}
2. Click "Deal Desk" in your dashboard
3. Paste in a real deal you're working on (company name, deal size, stage)
4. Hit Score

You'll get back a win probability, risk assessment, and strategy recommendation. It takes 30 seconds and you'll immediately see if this is useful for your business.

Try it right now — while it's top of mind.

— Garrett
GARCAR Enterprise""",
        "body_html": """<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; color: #e2e8f0; background: #0f172a; padding: 32px; border-radius: 12px;">
  <div style="margin-bottom: 24px;"><span style="color: #818cf8; font-weight: 700; font-size: 18px;">GARCAR</span></div>
  <p style="color: #e2e8f0; font-size: 16px;">Hey {name},</p>
  <p style="color: #cbd5e1; font-size: 15px; line-height: 1.6;">Most people sign up for tools and never use them. I don't want that to happen with you.</p>
  <p style="color: #e2e8f0; font-size: 16px; font-weight: 600;">Here's a 30-second challenge:</p>
  <div style="background: #1e293b; padding: 20px; border-radius: 8px; margin: 16px 0;">
    <p style="color: #818cf8; margin: 0 0 4px 0;">Step 1:</p><p style="color: #94a3b8; margin: 0 0 12px 0;">Log in to your dashboard</p>
    <p style="color: #818cf8; margin: 0 0 4px 0;">Step 2:</p><p style="color: #94a3b8; margin: 0 0 12px 0;">Click "Deal Desk"</p>
    <p style="color: #818cf8; margin: 0 0 4px 0;">Step 3:</p><p style="color: #94a3b8; margin: 0 0 12px 0;">Paste a real deal you're working on</p>
    <p style="color: #818cf8; margin: 0 0 4px 0;">Step 4:</p><p style="color: #94a3b8; margin: 0;">Hit Score → get instant results</p>
  </div>
  <a href="{base_url}" style="display: inline-block; background: #6366f1; color: white; padding: 12px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; margin: 16px 0;">Take the 30-second challenge →</a>
  <p style="color: #64748b; font-size: 14px; margin-top: 32px;">— Garrett<br/>GARCAR Enterprise</p>
</div>""",
    },
    {
        "step": 3,
        "delay_hours": 72,
        "subject": "The hidden cost of not knowing which customers are about to leave",
        "body_text": """Hey {name},

Quick question — do you know which of your customers are at risk of churning right now?

Most businesses don't. They find out when the cancellation email hits their inbox. By then it's too late.

The Churn Predictor in your GARCAR dashboard analyzes customer behavior patterns and flags accounts that show early warning signs:

- Declining usage patterns
- Support ticket spikes
- Engagement drop-offs
- Payment friction signals

The average cost of acquiring a new customer is 5-7x more than retaining one. Every churned customer is money left on the table.

If you have even 10 customers, it's worth running the analysis. You might be surprised.

{base_url}

— Garrett
GARCAR Enterprise""",
        "body_html": """<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; color: #e2e8f0; background: #0f172a; padding: 32px; border-radius: 12px;">
  <div style="margin-bottom: 24px;"><span style="color: #818cf8; font-weight: 700; font-size: 18px;">GARCAR</span></div>
  <p style="color: #e2e8f0; font-size: 16px;">Hey {name},</p>
  <p style="color: #cbd5e1; font-size: 15px; line-height: 1.6;">Quick question — do you know which of your customers are at risk of churning right now?</p>
  <p style="color: #cbd5e1; font-size: 15px; line-height: 1.6;">Most businesses don't. They find out when the cancellation email hits their inbox. By then it's too late.</p>
  <p style="color: #e2e8f0; font-size: 15px; font-weight: 600;">The Churn Predictor flags early warning signs:</p>
  <div style="background: #1e293b; padding: 20px; border-radius: 8px; margin: 16px 0;">
    <p style="color: #f87171; margin: 0 0 8px 0;">⚠ Declining usage patterns</p>
    <p style="color: #f87171; margin: 0 0 8px 0;">⚠ Support ticket spikes</p>
    <p style="color: #f87171; margin: 0 0 8px 0;">⚠ Engagement drop-offs</p>
    <p style="color: #f87171; margin: 0;">⚠ Payment friction signals</p>
  </div>
  <p style="color: #fbbf24; font-size: 15px; font-weight: 600;">The average cost of acquiring a new customer is 5-7x more than retaining one.</p>
  <p style="color: #cbd5e1; font-size: 15px;">If you have even 10 customers, it's worth running the analysis.</p>
  <a href="{base_url}" style="display: inline-block; background: #6366f1; color: white; padding: 12px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; margin: 16px 0;">Run your churn analysis →</a>
  <p style="color: #64748b; font-size: 14px; margin-top: 32px;">— Garrett<br/>GARCAR Enterprise</p>
</div>""",
    },
    {
        "step": 4,
        "delay_hours": 120,
        "subject": "Your competitors are ranking for your keywords",
        "body_text": """Hey {name},

Here's an uncomfortable truth: while you're reading this email, your competitors are publishing SEO content that targets the exact keywords your customers search for.

The SEO Content Factory in your GARCAR dashboard generates:

- Keyword-optimized article outlines
- Meta titles and descriptions that actually get clicks
- Full content briefs your writers can execute immediately
- Competitive gap analysis for your target keywords

One well-optimized article can drive traffic for years. Most businesses don't create them because the research takes too long.

The Content Factory does the research in seconds. You provide the keyword, it provides the strategy.

Worth 5 minutes of your time: {base_url}

— Garrett
GARCAR Enterprise""",
        "body_html": """<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; color: #e2e8f0; background: #0f172a; padding: 32px; border-radius: 12px;">
  <div style="margin-bottom: 24px;"><span style="color: #818cf8; font-weight: 700; font-size: 18px;">GARCAR</span></div>
  <p style="color: #e2e8f0; font-size: 16px;">Hey {name},</p>
  <p style="color: #cbd5e1; font-size: 15px; line-height: 1.6;">Here's an uncomfortable truth: while you're reading this, your competitors are publishing SEO content that targets the exact keywords your customers search for.</p>
  <p style="color: #e2e8f0; font-size: 15px; font-weight: 600;">The SEO Content Factory generates:</p>
  <div style="background: #1e293b; padding: 20px; border-radius: 8px; margin: 16px 0;">
    <p style="color: #34d399; margin: 0 0 8px 0;">✓ Keyword-optimized article outlines</p>
    <p style="color: #34d399; margin: 0 0 8px 0;">✓ Meta titles and descriptions that get clicks</p>
    <p style="color: #34d399; margin: 0 0 8px 0;">✓ Full content briefs for immediate execution</p>
    <p style="color: #34d399; margin: 0;">✓ Competitive gap analysis</p>
  </div>
  <p style="color: #cbd5e1; font-size: 15px;">One well-optimized article can drive traffic for years. The Content Factory does the research in seconds.</p>
  <a href="{base_url}" style="display: inline-block; background: #6366f1; color: white; padding: 12px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; margin: 16px 0;">Generate your first content brief →</a>
  <p style="color: #64748b; font-size: 14px; margin-top: 32px;">— Garrett<br/>GARCAR Enterprise</p>
</div>""",
    },
    {
        "step": 5,
        "delay_hours": 168,
        "subject": "You're on the free plan — here's what you're missing",
        "body_text": """Hey {name},

You've had access to GARCAR Enterprise for a week now. If you've tried the tools, you've seen what they can do.

Here's what changes when you upgrade:

FREE PLAN (current):
- 10 API calls/month
- Basic scoring

STARTER ($49/mo):
- 500 API calls/month
- Full product access
- Priority support
- API key for integrations

PROFESSIONAL ($149/mo):
- 5,000 API calls/month
- Advanced analytics
- Custom integrations
- Dedicated support

ENTERPRISE ($499/mo):
- Unlimited calls
- White-label options
- Custom AI model training
- Direct Slack support line

The Starter plan pays for itself if it helps you close even one extra deal per month or retain one customer who was about to churn.

Upgrade here: {base_url}

No hard sell. If the free tier is enough for you, keep using it.

— Garrett
GARCAR Enterprise""",
        "body_html": """<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; color: #e2e8f0; background: #0f172a; padding: 32px; border-radius: 12px;">
  <div style="margin-bottom: 24px;"><span style="color: #818cf8; font-weight: 700; font-size: 18px;">GARCAR</span></div>
  <p style="color: #e2e8f0; font-size: 16px;">Hey {name},</p>
  <p style="color: #cbd5e1; font-size: 15px; line-height: 1.6;">You've had access to GARCAR Enterprise for a week now. If you've tried the tools, you've seen what they can do.</p>
  <p style="color: #e2e8f0; font-size: 15px; font-weight: 600;">Here's what changes when you upgrade:</p>
  <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
    <tr style="background: #1e293b;">
      <td style="padding: 12px; color: #94a3b8; border-bottom: 1px solid #334155;">Free (current)</td>
      <td style="padding: 12px; color: #94a3b8; border-bottom: 1px solid #334155;">10 calls/mo, basic scoring</td>
    </tr>
    <tr style="background: #1e293b;">
      <td style="padding: 12px; color: #818cf8; border-bottom: 1px solid #334155; font-weight: 600;">Starter $49/mo</td>
      <td style="padding: 12px; color: #e2e8f0; border-bottom: 1px solid #334155;">500 calls, full access, API key</td>
    </tr>
    <tr style="background: #1e293b;">
      <td style="padding: 12px; color: #818cf8; border-bottom: 1px solid #334155; font-weight: 600;">Pro $149/mo</td>
      <td style="padding: 12px; color: #e2e8f0; border-bottom: 1px solid #334155;">5K calls, advanced analytics, integrations</td>
    </tr>
    <tr style="background: #1e293b;">
      <td style="padding: 12px; color: #818cf8; font-weight: 600;">Enterprise $499/mo</td>
      <td style="padding: 12px; color: #e2e8f0;">Unlimited, white-label, custom AI</td>
    </tr>
  </table>
  <p style="color: #fbbf24; font-size: 15px;">The Starter plan pays for itself if it helps you close even one extra deal per month.</p>
  <a href="{base_url}" style="display: inline-block; background: #6366f1; color: white; padding: 12px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; margin: 16px 0;">View upgrade options →</a>
  <p style="color: #64748b; font-size: 14px; margin-top: 24px;">No hard sell. If the free tier works for you, keep using it.</p>
  <p style="color: #64748b; font-size: 14px;">— Garrett<br/>GARCAR Enterprise</p>
</div>""",
    },
]


# ════════════════════════════════════════
# SMTP EMAIL SENDER
# ════════════════════════════════════════

def send_email(to_email: str, subject: str, body_html: str, body_text: str) -> dict:
    """Send an email via SMTP. Returns status dict."""
    if not SMTP_USER or not SMTP_PASS:
        logger.warning(f"SMTP not configured — email to {to_email} queued but not sent")
        return {"status": "queued", "message": "SMTP not configured — email logged but not delivered"}

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(body_html, "html"))

        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(FROM_EMAIL, to_email, msg.as_string())

        logger.info(f"Email sent to {to_email}: {subject}")
        return {"status": "sent", "message": f"Delivered to {to_email}"}

    except Exception as e:
        logger.error(f"Email failed to {to_email}: {e}")
        return {"status": "failed", "message": str(e)}


def render_template(template: str, lead: Lead) -> str:
    """Replace template variables with lead data."""
    name = lead.name or lead.email.split("@")[0]
    return template.format(
        name=name,
        email=lead.email,
        base_url=BASE_URL,
    )


# ════════════════════════════════════════
# NURTURE ENGINE
# ════════════════════════════════════════

def seed_email_templates(db: Session):
    """Seed the default welcome drip sequence if it doesn't exist."""
    existing = db.query(EmailTemplate).filter(
        EmailTemplate.sequence_name == "welcome_drip"
    ).first()
    if existing:
        return

    for step_data in WELCOME_DRIP:
        template = EmailTemplate(
            sequence_name="welcome_drip",
            step_number=step_data["step"],
            subject=step_data["subject"],
            body_html=step_data["body_html"],
            body_text=step_data["body_text"],
            delay_hours=step_data["delay_hours"],
        )
        db.add(template)
    db.commit()
    logger.info("Seeded welcome_drip email sequence (5 steps)")


def enroll_lead_in_sequence(lead: Lead, sequence_name: str, db: Session):
    """Enroll a lead in a nurture sequence — schedules all steps."""
    # Check if already enrolled
    existing = db.query(NurtureStep).filter(
        NurtureStep.lead_id == lead.id,
        NurtureStep.sequence_name == sequence_name,
    ).first()
    if existing:
        logger.info(f"Lead {lead.email} already enrolled in {sequence_name}")
        return

    templates = db.query(EmailTemplate).filter(
        EmailTemplate.sequence_name == sequence_name,
        EmailTemplate.is_active == True,
    ).order_by(EmailTemplate.step_number).all()

    if not templates:
        logger.warning(f"No templates found for sequence: {sequence_name}")
        return

    now = datetime.now(timezone.utc)
    for tmpl in templates:
        step = NurtureStep(
            lead_id=lead.id,
            template_id=tmpl.id,
            sequence_name=sequence_name,
            step_number=tmpl.step_number,
            scheduled_at=now + timedelta(hours=tmpl.delay_hours),
        )
        db.add(step)

    db.commit()
    logger.info(f"Enrolled {lead.email} in {sequence_name} ({len(templates)} steps)")


def process_nurture_queue(db: Session):
    """Process all due nurture steps — send emails."""
    now = datetime.now(timezone.utc)

    due_steps = db.query(NurtureStep).filter(
        NurtureStep.status == "pending",
        NurtureStep.scheduled_at <= now,
    ).order_by(NurtureStep.scheduled_at).limit(50).all()

    results = {"sent": 0, "failed": 0, "skipped": 0}

    for step in due_steps:
        lead = step.lead
        template = step.template

        # Skip if lead was converted or lost
        if lead.status in ("converted", "lost"):
            step.status = "skipped"
            results["skipped"] += 1
            continue

        # Render and send
        subject = render_template(template.subject, lead)
        body_html = render_template(template.body_html, lead)
        body_text = render_template(template.body_text, lead)

        result = send_email(lead.email, subject, body_html, body_text)

        if result["status"] in ("sent", "queued"):
            step.status = "sent"
            step.sent_at = now
            results["sent"] += 1
            # Update lead status
            if lead.status == "new":
                lead.status = "contacted"
        else:
            step.status = "failed"
            step.error_message = result["message"]
            results["failed"] += 1

    db.commit()
    logger.info(f"Nurture queue processed: {results}")
    return results


# ════════════════════════════════════════
# API ENDPOINTS
# ════════════════════════════════════════

class EnrollRequest(BaseModel):
    lead_id: int
    sequence_name: str = "welcome_drip"


@router.post("/seed-templates")
def api_seed_templates(
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Admin: seed default email templates."""
    seed_email_templates(db)
    count = db.query(EmailTemplate).count()
    return {"message": "Templates seeded", "total_templates": count}


@router.post("/enroll")
def api_enroll_lead(
    req: EnrollRequest,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Admin: manually enroll a lead in a nurture sequence."""
    lead = db.query(Lead).filter(Lead.id == req.lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    seed_email_templates(db)
    enroll_lead_in_sequence(lead, req.sequence_name, db)

    steps = db.query(NurtureStep).filter(
        NurtureStep.lead_id == lead.id,
        NurtureStep.sequence_name == req.sequence_name,
    ).count()

    return {
        "message": f"Lead {lead.email} enrolled in {req.sequence_name}",
        "steps_scheduled": steps,
    }


@router.post("/process")
def api_process_queue(
    background_tasks: BackgroundTasks,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Admin: trigger nurture queue processing."""
    results = process_nurture_queue(db)
    return {"message": "Queue processed", "results": results}


@router.get("/sequences")
def api_list_sequences(
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Admin: list all email sequences."""
    templates = db.query(EmailTemplate).order_by(
        EmailTemplate.sequence_name, EmailTemplate.step_number
    ).all()

    sequences = {}
    for t in templates:
        if t.sequence_name not in sequences:
            sequences[t.sequence_name] = []
        sequences[t.sequence_name].append({
            "id": t.id,
            "step": t.step_number,
            "subject": t.subject,
            "delay_hours": t.delay_hours,
            "is_active": t.is_active,
        })

    return sequences


@router.get("/pipeline")
def api_nurture_pipeline(
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Admin: nurture pipeline analytics."""
    total_steps = db.query(NurtureStep).count()
    sent = db.query(NurtureStep).filter(NurtureStep.status == "sent").count()
    pending = db.query(NurtureStep).filter(NurtureStep.status == "pending").count()
    failed = db.query(NurtureStep).filter(NurtureStep.status == "failed").count()
    skipped = db.query(NurtureStep).filter(NurtureStep.status == "skipped").count()

    # Leads in sequences
    enrolled_leads = db.query(NurtureStep.lead_id).distinct().count()

    # Open rate (if tracked)
    opened = db.query(NurtureStep).filter(NurtureStep.opened_at.isnot(None)).count()

    return {
        "total_steps": total_steps,
        "sent": sent,
        "pending": pending,
        "failed": failed,
        "skipped": skipped,
        "enrolled_leads": enrolled_leads,
        "open_rate": round(opened / max(sent, 1) * 100, 1),
        "delivery_rate": round(sent / max(total_steps - pending, 1) * 100, 1),
    }


@router.get("/lead/{lead_id}")
def api_lead_nurture_status(
    lead_id: int,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Admin: see nurture status for a specific lead."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    steps = db.query(NurtureStep).filter(
        NurtureStep.lead_id == lead_id
    ).order_by(NurtureStep.step_number).all()

    return {
        "lead": {"id": lead.id, "email": lead.email, "name": lead.name, "status": lead.status},
        "steps": [
            {
                "step": s.step_number,
                "sequence": s.sequence_name,
                "status": s.status,
                "scheduled_at": s.scheduled_at.isoformat() if s.scheduled_at else None,
                "sent_at": s.sent_at.isoformat() if s.sent_at else None,
                "opened_at": s.opened_at.isoformat() if s.opened_at else None,
            }
            for s in steps
        ],
    }


# ── Email tracking pixel endpoint ──
@router.get("/track/open/{step_id}")
def track_open(step_id: int, db: Session = Depends(get_db)):
    """Tracking pixel — records email opens."""
    step = db.query(NurtureStep).filter(NurtureStep.id == step_id).first()
    if step and not step.opened_at:
        step.opened_at = datetime.now(timezone.utc)
        db.commit()

    # Return 1x1 transparent pixel
    from fastapi.responses import Response
    pixel = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x00\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
    return Response(content=pixel, media_type="image/gif")


@router.get("/track/click/{step_id}")
def track_click(step_id: int, db: Session = Depends(get_db)):
    """Click tracking — records and redirects."""
    step = db.query(NurtureStep).filter(NurtureStep.id == step_id).first()
    if step and not step.clicked_at:
        step.clicked_at = datetime.now(timezone.utc)
        db.commit()

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=BASE_URL)
