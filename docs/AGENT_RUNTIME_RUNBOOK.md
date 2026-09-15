# Agent Runtime Runbook

## Safe default

The runtime starts with `EXTERNAL_ACTIONS_ENABLED=false`. It may record health, worker heartbeats, and safe test runs, but it must not send messages, write CRM data, bill customers, or deploy services.

## Local start

1. Copy `.env.agent-runtime.example` to `.env.agent-runtime` and supply non-production test database and Redis URLs.
2. Run `docker compose -f docker-compose.agent-runtime.yml up --build`.
3. Check `GET /healthz`; it must return `status: ok`.
4. Check `GET /readyz`; it returns 503 until both database and Redis URLs are configured.
5. Check `GET /runtime/status`; heartbeat age should remain below 90 seconds.
6. Check `GET /metrics` and run `POST /runs/test`.

## Production release gate

- Use a non-production environment first.
- Apply the SQL migration only after reviewing it in Supabase.
- Confirm health, readiness, metrics, and a worker heartbeat before routing traffic.
- Keep external actions disabled until approval logging and specific connector tests pass.
- Alert when heartbeat age exceeds 300 seconds, readiness fails, or failed runs exceed 3 in 15 minutes.

## Rollback

Set `EXTERNAL_ACTIONS_ENABLED=false`, stop the worker, route traffic to the prior deployment, and preserve logs plus agent-run records for incident review.
