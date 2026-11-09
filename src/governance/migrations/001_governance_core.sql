CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS enterprise_proposals (
    proposal_id VARCHAR(64) PRIMARY KEY,
    agent_id VARCHAR(64) NOT NULL,
    layer VARCHAR(32) NOT NULL,
    target_action VARCHAR(128) NOT NULL,
    parameters JSONB NOT NULL,
    risk_score NUMERIC(3,2) NOT NULL CHECK (risk_score >= 0 AND risk_score <= 1),
    requires_hitl BOOLEAN NOT NULL DEFAULT TRUE,
    status VARCHAR(40) NOT NULL,
    payload_sha256 CHAR(64) NOT NULL,
    authorization_token_hash CHAR(64),
    authorization_expires_at TIMESTAMPTZ,
    authorization_consumed_at TIMESTAMPTZ,
    receipt JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_enterprise_proposals_status_created
    ON enterprise_proposals(status, created_at DESC);

CREATE TABLE IF NOT EXISTS enterprise_approvals (
    approval_id BIGSERIAL PRIMARY KEY,
    proposal_id VARCHAR(64) NOT NULL REFERENCES enterprise_proposals(proposal_id),
    approver_id VARCHAR(128) NOT NULL,
    decision VARCHAR(16) NOT NULL CHECK (decision IN ('APPROVED','REJECTED')),
    note TEXT,
    approved_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_enterprise_approvals_proposal
    ON enterprise_approvals(proposal_id, approved_at DESC);

CREATE TABLE IF NOT EXISTS enterprise_execution_events (
    event_id BIGSERIAL PRIMARY KEY,
    proposal_id VARCHAR(64) NOT NULL REFERENCES enterprise_proposals(proposal_id),
    event_type VARCHAR(40) NOT NULL,
    executor_id VARCHAR(128) NOT NULL,
    receipt JSONB NOT NULL,
    receipt_sha256 CHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS enterprise_audit_events (
    event_id BIGSERIAL PRIMARY KEY,
    proposal_id VARCHAR(64),
    event_type VARCHAR(64) NOT NULL,
    actor_id VARCHAR(128) NOT NULL,
    event_data JSONB NOT NULL,
    previous_event_hash CHAR(64),
    event_hash CHAR(64) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_enterprise_audit_proposal
    ON enterprise_audit_events(proposal_id, event_id);

CREATE OR REPLACE FUNCTION enterprise_reject_audit_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'enterprise_audit_events is append-only';
END;
$$;
DROP TRIGGER IF EXISTS trg_enterprise_audit_immutable ON enterprise_audit_events;
CREATE TRIGGER trg_enterprise_audit_immutable
    BEFORE UPDATE OR DELETE ON enterprise_audit_events
    FOR EACH ROW EXECUTE FUNCTION enterprise_reject_audit_mutation();

CREATE TABLE IF NOT EXISTS enterprise_vector_memory (
    id BIGSERIAL PRIMARY KEY,
    namespace VARCHAR(64) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding VECTOR(1536) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_vector_memory_namespace
    ON enterprise_vector_memory(namespace);
CREATE INDEX IF NOT EXISTS idx_vector_memory_embedding
    ON enterprise_vector_memory USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS enterprise_control_state (
    control_name VARCHAR(64) PRIMARY KEY,
    enabled BOOLEAN NOT NULL,
    updated_by VARCHAR(128) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO enterprise_control_state(control_name, enabled, updated_by)
VALUES ('execution_kill_switch', FALSE, 'migration')
ON CONFLICT (control_name) DO NOTHING;
