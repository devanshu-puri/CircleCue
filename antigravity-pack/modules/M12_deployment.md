# M12: Deployment (Render + DigitalOcean + Atlas + Temporal)
**Depends on:** P0 modules. Deploy EARLY (Sunday morning), then keep deploying; do not leave it for the last hour.

## Topology (each host has a distinct purpose)
- **Render:** `web` (Next.js), `api` (FastAPI), `worker` (Temporal worker as a background worker). Blueprint in `infra/render.yaml`. Health check `/healthz`. Claim Render credits via hacktoberfest.com/my. Free web services sleep; use a paid/credit plan for the demo so cold starts don't kill it.
- **DigitalOcean:** GPU Droplet serving Gemma behind an OpenAI-compatible endpoint (check whether a 1-Click Model exists for Gemma; otherwise run vLLM or Ollama in Docker). Put TLS + bearer-token auth in front (Caddy/nginx), firewall to HTTPS only. Document model tag, VRAM, startup command in `infra/do/README.md`. **GPU billing is hourly: note when to power off after judging.**
- **MongoDB Atlas:** M0/M10 cluster, DB user with least privilege, network allowlist (Render outbound IPs if feasible; otherwise 0.0.0.0/0 with strong credentials, noted as a weekend tradeoff).
- **Temporal:** Cloud namespace if credits/trial available (API key/TLS per docs); otherwise a dev server on a small Droplet protected from public access. Verify current options before deciding; log in DECISIONS.md.
- **Sentry:** DSNs for api, worker, web.

## Build
1. `infra/render.yaml` with services, env var groups (no secrets committed), build/start commands, `API_URL` for web rewrites.
2. Env checklist table in `docs/DEPLOY.md`: variable -> where set -> sample (no real secrets).
3. Fallback chain configured: `AI_PROVIDER=openai_compat` (DO) with `AI_FALLBACK=rules`; confirm the app still works with the model offline.
4. `scripts/smoke.py`: against a base URL, registers two users, connects, grants, parses an utterance, triggers a boundary via `/dev/tick` (only when DEMO flag on), asserts a notification arrives, asserts a non-granted read is denied.
5. Release checklist: indexes exist, workers connected, timeline workflows ensured, Sentry receiving, HTTPS, cookies Secure, demo accounts seeded (M14).
6. Record deployment notes and costs for the "open vs closed API cost" paragraph of the write-up (GPU hourly cost vs per-token API estimate for your measured token counts).

## DoD: public URL works on a phone; smoke script green against production; model endpoint reachable only with token. Update MEMORY.md.
