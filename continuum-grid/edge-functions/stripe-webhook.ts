/**
 * Garcar Stripe Webhook → audits / retainers / garcar_events
 * Supabase Edge Function — Continuum Grid v1 (Security Hardened)
 *
 * Deploy: supabase functions deploy stripe-webhook --no-verify-jwt
 * Secrets: STRIPE_WEBHOOK_SECRET, STRIPE_SECRET_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL
 *
 * Security:
 * - Raw body via req.text()
 * - Missing Stripe-Signature → 400 before any work
 * - constructEvent (HMAC + 300s timestamp tolerance)
 * - Event type allowlist
 * - No payload / secret logging
 * - Idempotent insert into garcar_events (use unique constraint on event id in production)
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import Stripe from "https://esm.sh/stripe@14.21.0?target=deno";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.0";

const stripe = new Stripe(Deno.env.get("STRIPE_SECRET_KEY") || "", {
  apiVersion: "2023-10-16",
  httpClient: Stripe.createFetchHttpClient(),
});

const supabase = createClient(
  Deno.env.get("SUPABASE_URL") || "",
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || ""
);

const webhookSecret = Deno.env.get("STRIPE_WEBHOOK_SECRET") || "";

const ALLOWED_EVENTS = new Set([
  "checkout.session.completed",
  "payment_intent.succeeded",
  "customer.subscription.created",
  "customer.subscription.updated",
  "customer.subscription.deleted",
  "invoice.paid",
  "invoice.payment_failed",
]);

function safeLog(msg: string, meta: Record<string, unknown> = {}) {
  const safe = { ...meta };
  delete safe.payload;
  delete safe.body;
  delete safe.signature;
  console.log(`[stripe-webhook] ${msg}`, safe);
}

serve(async (req) => {
  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      status: 405,
      headers: { "Content-Type": "application/json", Allow: "POST" },
    });
  }

  if (!webhookSecret || !Deno.env.get("STRIPE_SECRET_KEY")) {
    safeLog("Webhook not configured");
    return new Response(JSON.stringify({ error: "Webhook not configured" }), {
      status: 503,
      headers: { "Content-Type": "application/json" },
    });
  }

  const signature = req.headers.get("stripe-signature");
  if (!signature) {
    safeLog("Missing Stripe-Signature");
    return new Response(JSON.stringify({ error: "Missing Stripe-Signature" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const body = await req.text();
  let event: Stripe.Event;

  try {
    event = stripe.webhooks.constructEvent(body, signature, webhookSecret);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    safeLog("Signature verification failed", { error: message });
    return new Response(
      JSON.stringify({ error: "Webhook signature verification failed" }),
      { status: 400, headers: { "Content-Type": "application/json" } }
    );
  }

  if (!ALLOWED_EVENTS.has(event.type)) {
    safeLog("Ignored unallowed event", { type: event.type, id: event.id });
    return new Response(JSON.stringify({ received: true, ignored: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  try {
    switch (event.type) {
      case "checkout.session.completed": {
        const session = event.data.object as Stripe.Checkout.Session;
        await handleCheckoutCompleted(session);
        break;
      }
      case "payment_intent.succeeded": {
        const pi = event.data.object as Stripe.PaymentIntent;
        await handlePaymentSucceeded(pi);
        break;
      }
      case "customer.subscription.created":
      case "customer.subscription.updated": {
        const sub = event.data.object as Stripe.Subscription;
        await handleSubscription(sub);
        break;
      }
      case "customer.subscription.deleted": {
        const sub = event.data.object as Stripe.Subscription;
        await handleSubscriptionCancelled(sub);
        break;
      }
      default:
        safeLog("Unhandled allowed type", { type: event.type });
    }

    // Durable event log — enforce unique on payload->>'id' or a dedicated column in production
    await supabase.from("garcar_events").insert({
      event_type: `stripe.${event.type.replace(/\./g, "_")}`,
      source_system: "stripe-webhook",
      payload: { id: event.id, type: event.type },
      processed: true,
    });

    safeLog("Processed", { type: event.type, id: event.id });
    return new Response(JSON.stringify({ received: true, event_id: event.id }), {
      headers: { "Content-Type": "application/json" },
      status: 200,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    safeLog("Handler error", { type: event.type, id: event.id, error: message });
    return new Response(JSON.stringify({ error: "Handler error" }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
});

async function handleCheckoutCompleted(session: Stripe.Checkout.Session) {
  const email = session.customer_details?.email || session.customer_email;
  const paymentIntent = session.payment_intent as string | null;
  if (!email) {
    safeLog("No email on checkout session", { sessionId: session.id });
    return;
  }
  const auditId = session.metadata?.audit_id;
  if (auditId) {
    const { error } = await supabase
      .from("audits")
      .update({
        status: "active",
        stripe_payment_id: paymentIntent,
        stripe_checkout_session_id: session.id,
        started_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      .eq("id", auditId);
    if (error) safeLog("Update audit failed", { error: error.message });
  } else {
    const { error } = await supabase.from("audits").insert({
      customer_email: email,
      customer_name: session.customer_details?.name || null,
      status: "active",
      stripe_payment_id: paymentIntent,
      stripe_checkout_session_id: session.id,
      amount_cents: session.amount_total || 250000,
      started_at: new Date().toISOString(),
      scope: session.metadata?.scope || "Agent Reliability Audit — one workflow",
    });
    if (error) safeLog("Insert audit failed", { error: error.message });
  }
}

async function handlePaymentSucceeded(pi: Stripe.PaymentIntent) {
  const { data } = await supabase
    .from("audits")
    .select("id")
    .eq("stripe_payment_id", pi.id)
    .maybeSingle();
  if (data) {
    await supabase
      .from("audits")
      .update({ status: "active", updated_at: new Date().toISOString() })
      .eq("id", data.id);
  }
}

async function handleSubscription(sub: Stripe.Subscription) {
  const email = sub.metadata?.customer_email;
  if (!email) return;
  await supabase.from("retainers").upsert(
    {
      customer_email: email,
      monthly_amount_cents: sub.items.data[0]?.price?.unit_amount || 0,
      status: sub.status === "active" ? "active" : "paused",
      stripe_subscription_id: sub.id,
      next_billing_at: new Date(sub.current_period_end * 1000).toISOString(),
      updated_at: new Date().toISOString(),
    },
    { onConflict: "stripe_subscription_id" }
  );
}

async function handleSubscriptionCancelled(sub: Stripe.Subscription) {
  await supabase
    .from("retainers")
    .update({
      status: "cancelled",
      cancelled_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    })
    .eq("stripe_subscription_id", sub.id);
}
