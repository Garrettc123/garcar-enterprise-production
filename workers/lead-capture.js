/**
 * Garcar Enterprise — Cloudflare Worker Lead Capture
 *
 * POST /leads
 *   Captures a lead, optionally scores it with HF_SCORER_URL,
 *   then persists the result to Supabase.
 *
 * GET /health
 *   Returns service health without exposing secrets.
 */

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization",
  "Content-Type": "application/json",
};

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: corsHeaders,
  });
}

function normalizeLead(input) {
  return {
    name: typeof input.name === "string" ? input.name.trim() : null,
    email: typeof input.email === "string" ? input.email.trim().toLowerCase() : null,
    phone: typeof input.phone === "string" ? input.phone.trim() : null,
    company: typeof input.company === "string" ? input.company.trim() : null,
    website: typeof input.website === "string" ? input.website.trim() : null,
    message: typeof input.message === "string" ? input.message.trim() : null,
    source: typeof input.source === "string" ? input.source.trim() : "website",
    metadata: input.metadata && typeof input.metadata === "object" ? input.metadata : {},
  };
}

function validateLead(lead) {
  if (!lead.email && !lead.phone) {
    return "At least one of email or phone is required";
  }

  if (lead.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(lead.email)) {
    return "Invalid email address";
  }

  return null;
}

async function scoreLead(lead, env) {
  if (!env.HF_SCORER_URL) {
    return { score: null, label: null, raw: null };
  }

  const response = await fetch(env.HF_SCORER_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: lead.name,
      email: lead.email,
      phone: lead.phone,
      company: lead.company,
      website: lead.website,
      message: lead.message,
      source: lead.source,
      metadata: lead.metadata,
    }),
  });

  if (!response.ok) {
    throw new Error(`Scorer returned HTTP ${response.status}`);
  }

  const raw = await response.json();
  const score = Number(raw.score ?? raw.probability ?? raw.lead_score);

  return {
    score: Number.isFinite(score) ? score : null,
    label: raw.label ?? raw.classification ?? null,
    raw,
  };
}

async function persistLead(lead, scoring, env) {
  if (!env.SUPABASE_URL || !env.SUPABASE_ANON_KEY) {
    throw new Error("Supabase environment is not configured");
  }

  const payload = {
    ...lead,
    lead_score: scoring.score,
    lead_label: scoring.label,
    scoring_result: scoring.raw,
  };

  const response = await fetch(`${env.SUPABASE_URL.replace(/\/$/, "")}/rest/v1/leads`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      apikey: env.SUPABASE_ANON_KEY,
      Authorization: `Bearer ${env.SUPABASE_ANON_KEY}`,
      Prefer: "return=representation",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Supabase returned HTTP ${response.status}: ${detail}`);
  }

  const rows = await response.json();
  return Array.isArray(rows) ? rows[0] ?? null : rows;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders });
    }

    if (request.method === "GET" && url.pathname === "/health") {
      return json({
        ok: true,
        service: "garcar-lead-capture",
        supabase_configured: Boolean(env.SUPABASE_URL && env.SUPABASE_ANON_KEY),
        scorer_configured: Boolean(env.HF_SCORER_URL),
      });
    }

    if (request.method !== "POST" || url.pathname !== "/leads") {
      return json({ error: "Not found" }, 404);
    }

    try {
      const body = await request.json();
      const lead = normalizeLead(body);
      const validationError = validateLead(lead);

      if (validationError) {
        return json({ error: validationError }, 400);
      }

      const scoring = await scoreLead(lead, env);
      const savedLead = await persistLead(lead, scoring, env);

      return json({
        ok: true,
        lead: savedLead,
        scoring: {
          score: scoring.score,
          label: scoring.label,
        },
      }, 201);
    } catch (error) {
      console.error("lead_capture_error", error);
      return json({
        ok: false,
        error: "Lead capture failed",
      }, 500);
    }
  },
};
