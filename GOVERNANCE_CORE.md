# Garcar Governance Core — PostgreSQL + pgvector

This branch adds a guarded governance and semantic-memory API to the existing FastAPI application.

## Included

- Versioned startup migration with bounded PostgreSQL connection retries and an advisory lock.
- PostgreSQL proposal, approval, execution-event, audit-event, control-state, and vector-memory tables.
- pgvector 1536-dimensional embeddings with an HNSW cosine index.
- Agent API-key authentication and a separate owner API key for approval and kill-switch control.
- Idempotent proposal submission.
- Budget and layer policy checks; risk above the automated threshold requires an authenticated owner decision with a written justification (at least 20 characters).
- Short-lived, single-use authorization tokens stored only as SHA-256 hashes.
- Signed execution receipts; the gateway accepts a receipt only when the configured executor signature validates and the receipt explicitly says `success: true`.
- Append-only audit rows with a SHA-256 hash chain and database trigger blocking ordinary UPDATE/DELETE operations.
- Persistent emergency kill switch.

## Startup

The existing container remains compatible by default. Enable database migrations and the routes with `ENABLE_GOVERNANCE_DB=true`. The Docker command then runs `python init_db.py` before starting Uvicorn and fails startup if migration cannot complete.

For a local Compose deployment, set these secrets in the deployment environment (do not commit them):

- `POSTGRES_PASSWORD`
- In the existing Vault KV v2 path `secret/garcar/production/keys`, provision `GARCAR_AGENT_API_KEYS` (comma-separated `agent_id:api_key` pairs; legacy bare keys receive a deterministic `agent_<sha256-prefix>` identity), `GARCAR_OWNER_API_KEY` (independent owner approval key), and `GARCAR_EXECUTION_SIGNING_KEY` (shared only with the trusted executor for receipt signing). The application fails production startup if any required secret is missing.

Then run:

```sh
docker compose -f docker-compose.yml -f docker-compose.governance.yml up --build
```

The base Compose file still requires its existing Vault and S3 configuration. The governance overlay adds a persistent pgvector PostgreSQL service and enables migrations. On a new database volume, startup creates or hardens the dedicated runtime role and grants only the table operations required by the API; it rejects runtime roles that inherit privileges from other roles. Existing PostgreSQL volumes must be reviewed before changing the configured migration username.

## API surface

All routes are under `/v1`.

- `GET /governance/health` — authenticated database health check.
- `POST /governance/propose` — agent submits an idempotent proposal.
- `POST /governance/evaluate` — owner independently approves or rejects a proposal.
- `POST /governance/verify` — agent submits a one-time grant and signed executor receipt.
- `GET /governance/execution-allowed` — authenticated executors check the persistent stop before side effects.
- `POST /governance/kill-switch?enabled=true|false` — owner controls the persistent execution stop.
- `POST /memory/store` — store a 1536-dimensional embedding.
- `POST /memory/search` — namespace-scoped cosine similarity search.

Headers:

- Agent operations: `X-Agent-API-Key`; each configured key resolves to one stable agent ID.
- Proposal `agent_id` must exactly match the authenticated key's agent ID.
- Memory `namespace` must exactly match that authenticated agent ID; cross-agent namespace reads and writes are rejected.
- Owner operations: `X-Owner-API-Key`
- Execution verification: `X-Execution-Signature`

The execution signature is HMAC-SHA256 over canonical UTF-8 JSON:
`{"proposal_id": "...", "executor_id": "...", "receipt": {...}}`
where JSON keys are sorted and separators are `(",", ":")`. The trusted executor must hold the signing key; it must not be exposed to ordinary agents.

## Security and operational limits

- Never use source-code default credentials. No credentials are provided by this implementation.
- Use separate PostgreSQL migration-owner and runtime roles in production. The runtime role should not own tables or have permission to alter triggers/schema.
- The audit table is append-only at the application/database-trigger layer and hash chained. This is not equivalent to externally enforced WORM storage against a database superuser; periodically export/hash-anchor audit batches to the existing immutable S3 ledger for stronger tamper resistance.
- The kill switch is checked before accepting execution verification. Executors must also check it before performing side effects; a gateway cannot stop an external process that ignores the control plane.
- A signed receipt is an attestation by the configured executor, not independent proof that a third-party system performed the claimed work. Reconcile high-value operations against the authoritative provider (for example, Stripe) before treating them as financially settled.
- Production deployment, real database connectivity, secret provisioning, executor integration, and live end-to-end tests are not performed by this source change.
