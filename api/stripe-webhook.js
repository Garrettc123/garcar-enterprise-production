/**
 * Garcar Stripe Webhook — Production Security Hardened
 *
 * Security controls:
 * 1. Raw body only (bodyParser: false) — required for signature match
 * 2. Explicit missing Stripe-Signature → 400
 * 3. stripe.webhooks.constructEvent (HMAC-SHA256 + timestamp tolerance ≤300s)
 * 4. Event type allowlist — only process known revenue events
 * 5. Idempotency on event.id (in-memory + durable via StripeEvent id storage recommended)
 * 6. No logging of payload, secrets, or full signature
 * 7. Fast 400 on any verification failure; 2xx only after verification succeeds
 * 8. HTTPS assumed at platform edge (Vercel/Railway)
 *
 * Required env:
 *   STRIPE_SECRET_KEY
 *   STRIPE_WEBHOOK_SECRET   (whsec_... from Dashboard endpoint)
 * Optional:
 *   NOTION_API_KEY, NOTION_DEALS_DB_ID
 *   GITHUB_REPO, GITHUB_PAT
 *
 * IP allowlist (platform/firewall level):
 *   https://docs.stripe.com/ips#webhook-notifications
 */

const stripe = require('stripe')(process.env.STRIPE_SECRET_KEY);
const { Client } = require('@notionhq/client');

const notion = process.env.NOTION_API_KEY
  ? new Client({ auth: process.env.NOTION_API_KEY })
  : null;

// Disable any automatic body parsing — signature must see exact bytes Stripe sent
export const config = { api: { bodyParser: false } };

// Allowed event types for the revenue engine (expand only when needed)
const ALLOWED_EVENTS = new Set([
  'checkout.session.completed',
  'payment_intent.succeeded',
  'customer.subscription.created',
  'customer.subscription.updated',
  'customer.subscription.deleted',
  'invoice.paid',
  'invoice.payment_failed',
]);

// Short-lived in-memory dedupe (serverless cold starts reset it).
// For multi-instance production, replace with Redis / Supabase unique constraint on event.id.
const processedEventIds = new Set();
const MAX_PROCESSED_CACHE = 5000;

async function getRawBody(req) {
  const chunks = [];
  for await (const chunk of req) {
    chunks.push(Buffer.from(chunk));
  }
  return Buffer.concat(chunks);
}

function safeLog(message, meta = {}) {
  // Never log secrets, full payloads, or raw signatures
  const safe = { ...meta };
  delete safe.payload;
  delete safe.body;
  delete safe.signature;
  delete safe.secret;
  console.log(`[stripe-webhook] ${message}`, safe);
}

export default async function handler(req, res) {
  // Method gate
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return res.status(405).json({ error: 'Method not allowed' });
  }

  // Config gate — refuse to process if secrets missing
  if (!process.env.STRIPE_WEBHOOK_SECRET || !process.env.STRIPE_SECRET_KEY) {
    safeLog('Webhook not configured — missing env');
    return res.status(503).json({ error: 'Webhook not configured' });
  }

  // Signature header must exist before any body work
  const sig = req.headers['stripe-signature'];
  if (!sig || typeof sig !== 'string') {
    safeLog('Missing Stripe-Signature header');
    return res.status(400).json({ error: 'Missing Stripe-Signature' });
  }

  let buf;
  try {
    buf = await getRawBody(req);
  } catch (err) {
    safeLog('Failed to read raw body', { error: err.message });
    return res.status(400).json({ error: 'Invalid body' });
  }

  // Core security: verify signature against exact raw bytes + endpoint secret
  // constructEvent also enforces timestamp tolerance (default 300 seconds)
  let event;
  try {
    event = stripe.webhooks.constructEvent(
      buf,
      sig,
      process.env.STRIPE_WEBHOOK_SECRET
    );
  } catch (err) {
    // Do not leak internal details; Stripe signature failures are expected on attack traffic
    safeLog('Signature verification failed', { error: err.message });
    return res.status(400).json({ error: 'Webhook signature verification failed' });
  }

  // Event type allowlist — ignore anything outside the revenue surface
  if (!ALLOWED_EVENTS.has(event.type)) {
    safeLog('Ignored unallowed event type', { type: event.type, id: event.id });
    return res.status(200).json({ received: true, ignored: true });
  }

  // Idempotency: already processed this event.id
  if (processedEventIds.has(event.id)) {
    safeLog('Duplicate event', { id: event.id });
    return res.status(200).json({ received: true, duplicate: true });
  }

  // Process only after verification + allowlist + dedupe
  try {
    if (event.type === 'checkout.session.completed') {
      await handleCheckoutCompleted(event);
    }
    // Add other handlers here as the revenue loop expands

    // Mark processed (trim cache if unbounded growth)
    processedEventIds.add(event.id);
    if (processedEventIds.size > MAX_PROCESSED_CACHE) {
      const first = processedEventIds.values().next().value;
      processedEventIds.delete(first);
    }

    safeLog('Processed', { type: event.type, id: event.id });
    return res.status(200).json({ received: true, event_id: event.id });
  } catch (err) {
    // Processing failure after verification — return 500 so Stripe retries
    safeLog('Handler error after verification', {
      type: event.type,
      id: event.id,
      error: err.message,
    });
    return res.status(500).json({ error: 'Handler error' });
  }
}

async function handleCheckoutCompleted(event) {
  const s = event.data.object;

  if (notion && process.env.NOTION_DEALS_DB_ID) {
    await notion.pages.create({
      parent: { database_id: process.env.NOTION_DEALS_DB_ID },
      properties: {
        Name: {
          title: [{ text: { content: s.customer_email || 'unknown' } }],
        },
        Email: { email: s.customer_email || null },
        Status: { select: { name: 'Paid' } },
        Amount: { number: (s.amount_total || 0) / 100 },
        Product: {
          rich_text: [
            {
              text: {
                content:
                  (s.metadata && s.metadata.product) || 'Garcar',
              },
            },
          ],
        },
        StripeSession: {
          rich_text: [{ text: { content: s.id } }],
        },
        StripeEvent: {
          rich_text: [{ text: { content: event.id } }],
        },
        CreatedAt: { date: { start: new Date().toISOString() } },
      },
    });
  }

  if (process.env.GITHUB_REPO && process.env.GITHUB_PAT) {
    await fetch(
      `https://api.github.com/repos/${process.env.GITHUB_REPO}/dispatches`,
      {
        method: 'POST',
        headers: {
          Authorization: `token ${process.env.GITHUB_PAT}`,
          'Content-Type': 'application/json',
          Accept: 'application/vnd.github.v3+json',
        },
        body: JSON.stringify({
          event_type: 'provision-customer',
          client_payload: {
            email: s.customer_email,
            product: (s.metadata && s.metadata.product) || '',
            stripe_event_id: event.id,
            amount_total: s.amount_total,
          },
        }),
      }
    );
  }
}
