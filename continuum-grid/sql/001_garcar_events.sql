-- Garcar Event Bus Schema
-- Run in Supabase SQL Editor
-- Part of Continuum Grid v1
-- Generated 2026-09-13

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS garcar_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type TEXT NOT NULL,
    source_system TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    correlation_id UUID,
    causation_id UUID,
    trace_id UUID,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed BOOLEAN NOT NULL DEFAULT FALSE,
    processed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_garcar_events_type ON garcar_events(event_type);
CREATE INDEX IF NOT EXISTS idx_garcar_events_source ON garcar_events(source_system);
CREATE INDEX IF NOT EXISTS idx_garcar_events_timestamp ON garcar_events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_garcar_events_correlation ON garcar_events(correlation_id);
CREATE INDEX IF NOT EXISTS idx_garcar_events_trace ON garcar_events(trace_id);
CREATE INDEX IF NOT EXISTS idx_garcar_events_unprocessed ON garcar_events(processed) WHERE processed = FALSE;

ALTER TABLE garcar_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role full access" ON garcar_events;
CREATE POLICY "Service role full access" ON garcar_events
    FOR ALL USING (auth.role() = 'service_role');

DROP POLICY IF EXISTS "Anonymous insert" ON garcar_events;
CREATE POLICY "Anonymous insert" ON garcar_events
    FOR INSERT WITH CHECK (auth.role() = 'anon');

DROP POLICY IF EXISTS "System read own" ON garcar_events;
CREATE POLICY "System read own" ON garcar_events
    FOR SELECT USING (
        auth.role() = 'authenticated' AND
        source_system = current_setting('app.current_system', true)
    );

COMMENT ON TABLE garcar_events IS 'Universal event bus for Garcar Continuum Grid. All systems publish/consume here.';

CREATE OR REPLACE FUNCTION mark_events_processed(p_ids UUID[])
RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    UPDATE garcar_events SET processed = TRUE, processed_at = NOW() WHERE id = ANY(p_ids);
END;
$$;

CREATE OR REPLACE FUNCTION get_unprocessed_events(
    p_consumer_system TEXT,
    p_event_types TEXT[],
    p_limit INT DEFAULT 100
)
RETURNS SETOF garcar_events LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM garcar_events
    WHERE processed = FALSE
      AND event_type = ANY(p_event_types)
      AND source_system != p_consumer_system
    ORDER BY timestamp ASC
    LIMIT p_limit
    FOR UPDATE SKIP LOCKED;
END;
$$;

-- Enable realtime (run in Supabase Dashboard > Replication)
-- ALTER PUBLICATION supabase_realtime ADD TABLE garcar_events;
