# Autonomous Deployment Mesh (ADM)

Canonical home (with `apex-revenue-system`). Human owns every merge unless a PR is explicitly labeled `automerge`.

## Path (no Cursor Cloud Agents)

1. Branch off `main`
2. Open PR → **ADM CI** must pass (`ci.yml` — backend import smoke)
3. Founder reviews and merges (or applies `automerge` label intentionally)
4. Push to `main` runs **Deploy GARCAR Backend** (Render) when `RENDER_DEPLOY_HOOK` is set
5. Optional health: `API_URL/health`

## Secrets

- `RENDER_DEPLOY_HOOK` — Render deploy hook
- `API_URL` — base URL for post-deploy health check

## Proof

Put CI run links and health output in the PR body. Do not commit media into the branch.
