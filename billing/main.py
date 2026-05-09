"""GAR-420: FastAPI Billing Microservice
/create-invoice, /payment-status, /send-receipt
Connects to Stripe. Logs transactions to SQLite (swap for Postgres in prod).
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, EmailStr
from typing import Optional
import stripe
import os
import sqlite3
import json
from datetime import datetime
import smtplib
from email.mime.text import MIMEText

app = FastAPI(title="Garcar Billing Microservice", version="1.0.0")

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
DB_PATH = os.getenv("DATABASE_PATH", "./garcar.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id TEXT PRIMARY KEY,
            customer_email TEXT,
            amount INTEGER,
            currency TEXT,
            status TEXT,
            stripe_payment_intent_id TEXT,
            created_at TEXT,
            metadata TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()


class InvoiceRequest(BaseModel):
    customer_email: str
    amount_cents: int  # amount in cents
    currency: str = "usd"
    description: str
    metadata: Optional[dict] = {}


class ReceiptRequest(BaseModel):
    payment_intent_id: str
    customer_email: str


@app.post("/create-invoice")
async def create_invoice(req: InvoiceRequest):
    """Create Stripe PaymentIntent and log to DB."""
    try:
        intent = stripe.PaymentIntent.create(
            amount=req.amount_cents,
            currency=req.currency,
            receipt_email=req.customer_email,
            description=req.description,
            metadata=req.metadata or {},
        )
        # Log to DB
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?)",
            (
                intent.id,
                req.customer_email,
                req.amount_cents,
                req.currency,
                intent.status,
                intent.id,
                datetime.utcnow().isoformat(),
                json.dumps(req.metadata),
            ),
        )
        conn.commit()
        conn.close()
        return {
            "payment_intent_id": intent.id,
            "client_secret": intent.client_secret,
            "status": intent.status,
            "amount": req.amount_cents,
            "currency": req.currency,
        }
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/payment-status/{payment_intent_id}")
async def payment_status(payment_intent_id: str):
    """Check Stripe PaymentIntent status."""
    try:
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        # Update DB
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "UPDATE transactions SET status=? WHERE stripe_payment_intent_id=?",
            (intent.status, payment_intent_id),
        )
        conn.commit()
        conn.close()
        return {
            "payment_intent_id": payment_intent_id,
            "status": intent.status,
            "amount": intent.amount,
            "currency": intent.currency,
            "receipt_email": intent.receipt_email,
        }
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/send-receipt")
async def send_receipt(req: ReceiptRequest, background_tasks: BackgroundTasks):
    """Trigger Stripe receipt email + log."""
    try:
        intent = stripe.PaymentIntent.retrieve(req.payment_intent_id)
        if intent.status != "succeeded":
            raise HTTPException(status_code=400, detail=f"Payment not succeeded: {intent.status}")
        # Stripe auto-sends receipt if receipt_email was set on create
        # This endpoint confirms and logs
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "UPDATE transactions SET status='receipt_sent' WHERE stripe_payment_intent_id=?",
            (req.payment_intent_id,),
        )
        conn.commit()
        conn.close()
        return {
            "status": "receipt_queued",
            "customer_email": req.customer_email,
            "payment_intent_id": req.payment_intent_id,
        }
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/transactions")
async def list_transactions(limit: int = 50):
    """List recent transactions from local DB."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT * FROM transactions ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    cols = ["id", "customer_email", "amount", "currency", "status",
            "stripe_payment_intent_id", "created_at", "metadata"]
    return [{cols[i]: row[i] for i in range(len(cols))} for row in rows]


@app.get("/health")
def health():
    return {"status": "ok", "service": "garcar-billing"}
