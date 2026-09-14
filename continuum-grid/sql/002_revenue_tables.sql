-- Garcar Revenue Loop Schema
-- Prospects → Audits → Implementations → Retainers
-- Part of Continuum Grid v1 — Agent Reliability Audit business
-- Generated 2026-09-13

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS prospects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT,
    first_name TEXT,
    last_name TEXT,
    company TEXT,
    title TEXT,
    source TEXT NOT NULL DEFAULT 'outbound',
    segment TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    last_touch_at TIMESTAMPTZ,
    reply_flag BOOLEAN DEFAULT FALSE,
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prospects_status ON prospects(status);
CREATE INDEX IF NOT EXISTS idx_prospects_email ON prospects(email);
CREATE INDEX IF NOT EXISTS idx_prospects_source ON prospects(source);
CREATE INDEX IF NOT EXISTS idx_prospects_last_touch ON prospects(last_touch_at DESC);

CREATE TABLE IF NOT EXISTS audits (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    prospect_id UUID REFERENCES prospects(id),
    customer_email TEXT NOT NULL,
    customer_name TEXT,
    company TEXT,
    scope TEXT,
    status TEXT NOT NULL DEFAULT 'pending_payment',
    stripe_payment_id TEXT,
    stripe_checkout_session_id TEXT,
    amount_cents INTEGER NOT NULL DEFAULT 250000,
    deliverable_url TEXT,
    findings_summary TEXT,
    roadmap_url TEXT,
    started_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audits_status ON audits(status);
CREATE INDEX IF NOT EXISTS idx_audits_stripe ON audits(stripe_payment_id);
CREATE INDEX IF NOT EXISTS idx_audits_customer ON audits(customer_email);

CREATE TABLE IF NOT EXISTS implementations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    audit_id UUID REFERENCES audits(id),
    customer_email TEXT NOT NULL,
    company TEXT,
    phase TEXT NOT NULL DEFAULT 'scoping',
    hours_logged NUMERIC(8,2) DEFAULT 0,
    invoiced_amount_cents INTEGER DEFAULT 0,
    contract_value_cents INTEGER,
    status TEXT NOT NULL DEFAULT 'proposed',
    sow_url TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_implementations_status ON implementations(status);
CREATE INDEX IF NOT EXISTS idx_implementations_audit ON implementations(audit_id);

CREATE TABLE IF NOT EXISTS retainers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_email TEXT NOT NULL,
    company TEXT,
    monthly_amount_cents INTEGER NOT NULL,
    billing_cycle TEXT NOT NULL DEFAULT 'monthly',
    status TEXT NOT NULL DEFAULT 'active',
    agent_system_slug TEXT,
    stripe_subscription_id TEXT,
    next_billing_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    cancelled_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_retainers_status ON retainers(status);
CREATE INDEX IF NOT EXISTS idx_retainers_stripe ON retainers(stripe_subscription_id);

ALTER TABLE prospects ENABLE ROW LEVEL SECURITY;
ALTER TABLE audits ENABLE ROW LEVEL SECURITY;
ALTER TABLE implementations ENABLE ROW LEVEL SECURITY;
ALTER TABLE retainers ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access prospects" ON prospects FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access audits" ON audits FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access implementations" ON implementations FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access retainers" ON retainers FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Anon insert prospects" ON prospects FOR INSERT WITH CHECK (auth.role() = 'anon');

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_prospects_updated ON prospects;
CREATE TRIGGER trg_prospects_updated BEFORE UPDATE ON prospects FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_audits_updated ON audits;
CREATE TRIGGER trg_audits_updated BEFORE UPDATE ON audits FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_implementations_updated ON implementations;
CREATE TRIGGER trg_implementations_updated BEFORE UPDATE ON implementations FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_retainers_updated ON retainers;
CREATE TRIGGER trg_retainers_updated BEFORE UPDATE ON retainers FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE prospects IS 'Outbound + inbound lead state for Agent Reliability Audit';
COMMENT ON TABLE audits IS '$2,500 fixed-scope Agent Reliability Audit records';
COMMENT ON TABLE implementations IS 'Control Foundation implementation projects linked to audits';
COMMENT ON TABLE retainers IS 'Managed Reliability monthly retainers';
