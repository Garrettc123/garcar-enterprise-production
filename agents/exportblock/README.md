# Garcar Enterprise Agent Registry — ExportBlock

This directory integrates the uploaded ExportBlock inventory into Garcar Enterprise as a governed capability registry.

## Imported inventory

- 497 agent records
- 57 Autonomous
- 175 Specialist
- 74 Planner
- 69 Reactive
- 59 Evaluator
- 37 Orchestrator
- 26 Conversational
- 414 Deployed
- 42 Testing
- 21 Building
- 20 Tuning
- 19 business/technical verticals
- Source archive SHA-256: `81830196689bdc4e81c1b8d4de4e5e088f4bd59ad6d58dacb7f9c08cc648bd81`

## Architectural role

ExportBlock is treated as a **capability registry**, not as an uncontrolled executor. The registry gives Garcar Enterprise a catalog of agent identities, types, lifecycle state, model family, complexity and vertical.

CRF can use this identity when an agent executes: execution telemetry → FailureEvent → Failure Genome → repair candidate → isolated branch/worktree → regression → GAR-VERIFY → draft PR → human merge.

Runtime state mapping:

| ExportBlock | Garcar |
|---|---|
| Deployed | available |
| Testing | test-only |
| Building | development-only |
| Tuning | evaluation-only |

## Governance

- Production merge remains human-only.
- Repair workers do not write directly to `main`.
- Secrets, `.env`, workflow and infrastructure mutation are not enabled by this import.
- Registry data is inventory metadata; it does not grant execution permissions by itself.

## Source integrity

`manifest.json` records the source archive hash and inventory counts. `agent-names.txt` preserves the imported agent identities. The original uploaded archive remains the provenance source for full descriptions and per-agent markdown records.
