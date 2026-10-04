# M11: Observability and security hardening
**Depends on:** all P0 modules (run incrementally, finalize here).

## Build
1. Sentry: backend exception capture; spans for `ai.parse`, `ai.significance`, `notify.pipeline`, each Temporal activity (use the SDK's Temporal support if available in your version, else interceptor/manual capture); frontend error boundary; release + env tags; scrub PII (no free text, tokens, codes). Dashboard screenshot for write-up.
2. Rate limits (in-memory or Mongo-backed): login, register, code lookup, `/ai/parse`, urgent override.
3. Security pass: cookie flags, CSRF posture (SameSite + JSON + Origin check), input length caps, sanitizer on all text shown to others, secrets only from env, dependency audit, HTTPS only, no tokens in logs, security headers via Next.
4. Audit log viewer endpoint for owner (grant changes, code use, safety events).
5. Authorization test sweep: automated test that iterates every router with a non-granted viewer and asserts no data leaks.
6. Privacy statement page text: what is stored, what the model sees, who sees what, how to pause/export/delete.
## DoD: forced backend error, AI failure (kill model) and notification failure each appear in Sentry with useful tags; authorization sweep green. Update MEMORY.md.
