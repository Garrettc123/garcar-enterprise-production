create extension if not exists pgcrypto;

create table if not exists public.agent_runs (
  id uuid primary key default gen_random_uuid(),
  correlation_id uuid not null default gen_random_uuid(),
  agent_name text not null,
  status text not null check (status in ('queued','running','needs_approval','completed','failed','cancelled')),
  trigger_type text not null check (trigger_type in ('schedule','webhook','manual','retry')),
  started_at timestamptz, finished_at timestamptz, duration_ms integer,
  error_code text, error_message text, metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists agent_runs_status_created_idx on public.agent_runs(status, created_at desc);

create table if not exists public.agent_heartbeats (
  worker_id text primary key, status text not null, current_run_id uuid references public.agent_runs(id),
  last_heartbeat_at timestamptz not null default now(), metadata jsonb not null default '{}'::jsonb
);

create table if not exists public.agent_approvals (
  id uuid primary key default gen_random_uuid(), run_id uuid not null references public.agent_runs(id),
  action_type text not null, payload jsonb not null,
  status text not null default 'pending' check (status in ('pending','approved','rejected','expired')),
  requested_at timestamptz not null default now(), decided_at timestamptz, decided_by text
);
create index if not exists agent_approvals_pending_idx on public.agent_approvals(status, requested_at) where status = 'pending';

alter table public.agent_runs enable row level security;
alter table public.agent_heartbeats enable row level security;
alter table public.agent_approvals enable row level security;
