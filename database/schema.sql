-- Production Database Schema for Universal Revenue Aggregator
-- PostgreSQL 15+

CREATE DATABASE revenue_aggregator;
\c revenue_aggregator;

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fuzzy text search

-- ============================================================
-- REVENUE TRACKING
-- ============================================================

CREATE TABLE systems (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    url TEXT NOT NULL,
    revenue_endpoint TEXT NOT NULL,
    annual_potential DECIMAL(15,2) NOT NULL,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE revenue_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    system_id UUID REFERENCES systems(id) ON DELETE CASCADE,
    current_revenue DECIMAL(15,2) NOT NULL,
    mrr DECIMAL(15,2),
    arr DECIMAL(15,2),
    growth_rate DECIMAL(5,4),
    active_customers INTEGER,
    snapshot_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

CREATE INDEX idx_revenue_snapshots_timestamp ON revenue_snapshots(snapshot_timestamp DESC);
CREATE INDEX idx_revenue_snapshots_system ON revenue_snapshots(system_id, snapshot_timestamp DESC);
CREATE INDEX idx_revenue_snapshots_metadata ON revenue_snapshots USING GIN(metadata);

-- ============================================================
-- PAYOUT MANAGEMENT
-- ============================================================

CREATE TABLE payout_destinations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    type VARCHAR(50) NOT NULL,
    address TEXT NOT NULL,
    percentage DECIMAL(5,2) NOT NULL CHECK (percentage >= 0 AND percentage <= 100),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE payouts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    total_amount DECIMAL(15,2) NOT NULL,
    paypal_amount DECIMAL(15,2),
    crypto_amount DECIMAL(15,2),
    status VARCHAR(50) DEFAULT 'pending',
    transaction_hash TEXT,
    paypal_transaction_id TEXT,
    initiated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    metadata JSONB
);

CREATE INDEX idx_payouts_status ON payouts(status);
CREATE INDEX idx_payouts_initiated ON payouts(initiated_at DESC);

-- ============================================================
-- AI AGENT NETWORK
-- ============================================================

CREATE TABLE ai_agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id VARCHAR(255) UNIQUE NOT NULL,
    type VARCHAR(100) NOT NULL,
    system VARCHAR(255) NOT NULL,
    endpoint TEXT NOT NULL,
    capabilities TEXT[] NOT NULL,
    performance_score DECIMAL(5,3) DEFAULT 0.0 CHECK (performance_score >= 0 AND performance_score <= 1),
    total_tasks_completed INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE agent_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID REFERENCES ai_agents(id) ON DELETE CASCADE,
    task_name VARCHAR(255) NOT NULL,
    task_type VARCHAR(100) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    result JSONB,
    execution_time DECIMAL(10,3),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX idx_agent_tasks_agent ON agent_tasks(agent_id, started_at DESC);
CREATE INDEX idx_agent_tasks_status ON agent_tasks(status);

-- ============================================================
-- API GATEWAY & MONITORING
-- ============================================================

CREATE TABLE api_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    system VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    path TEXT NOT NULL,
    user_id VARCHAR(255),
    ip_address INET,
    status_code INTEGER,
    response_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_api_requests_system ON api_requests(system, created_at DESC);
CREATE INDEX idx_api_requests_user ON api_requests(user_id, created_at DESC);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role VARCHAR(50) DEFAULT 'user',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- VIEWS FOR ANALYTICS
-- ============================================================

CREATE VIEW v_total_revenue AS
SELECT 
    SUM(current_revenue) as total_revenue,
    SUM(mrr) as total_mrr,
    SUM(arr) as total_arr,
    COUNT(DISTINCT system_id) as active_systems
FROM (
    SELECT DISTINCT ON (system_id) 
        system_id, current_revenue, mrr, arr
    FROM revenue_snapshots
    ORDER BY system_id, snapshot_timestamp DESC
) latest_snapshots;

CREATE VIEW v_agent_performance AS
SELECT 
    a.agent_id,
    a.type,
    a.performance_score,
    COUNT(t.id) as total_tasks,
    AVG(t.execution_time) as avg_execution_time,
    COUNT(CASE WHEN t.status = 'completed' THEN 1 END) as completed_tasks
FROM ai_agents a
LEFT JOIN agent_tasks t ON a.id = t.agent_id
GROUP BY a.id, a.agent_id, a.type, a.performance_score;

-- ============================================================
-- SEED DATA
-- ============================================================

INSERT INTO systems (name, display_name, url, revenue_endpoint, annual_potential) VALUES
('nwu-protocol', 'NWU Protocol', 'http://localhost:8000', '/api/revenue/current', 98500000),
('tree-of-life', 'Tree of Life System', 'https://tree-of-life-system.vercel.app', '/api/subscriptions/mrr', 131796),
('mars-ai', 'MARS AI', 'http://localhost:3000', '/api/revenue', 10000000),
('ai-orchestrator', 'AI Orchestrator', 'http://localhost:8001', '/api/health', 490000),
('ai-business-platform', 'AI Business Platform', 'http://localhost:3001', '/api/v1/status', 946000);

INSERT INTO payout_destinations (type, address, percentage) VALUES
('paypal', 'gwc2780@gmail.com', 70.0),
('ethereum', '0x5C92DCa91ac3251c17c94d69E93b8784fE8dcd30', 30.0);

-- ============================================================
-- FUNCTIONS & TRIGGERS
-- ============================================================

CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_systems_timestamp
    BEFORE UPDATE ON systems
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_payout_destinations_timestamp
    BEFORE UPDATE ON payout_destinations
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_ai_agents_timestamp
    BEFORE UPDATE ON ai_agents
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_users_timestamp
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();
