# Hacktoberfest 2026 — "Build for a Friend" Submission

## Project: CircleCue

### What Is It?

CircleCue is a private, permission-based life-context network that lets trusted people know what matters right now — are you in an exam? travelling? phone dying? free to talk? — without them having to call or ask.

Built for Hacktoberfest 2026 **"Build for a Friend"**.

---

### The Friend Story

My friend Priya constantly worries when Arjun doesn't pick up. Is he in a lecture? On a train to Delhi? Battery dead? She has no way to know without texting or calling — which interrupts him when he's busy, and leaves her anxious when she gets no reply. CircleCue solves exactly this: Arjun shares his context once (schedule, travel, exam, phone state), Priya gets exactly what she's permitted to see, and both sides gain calm without constant check-ins.

---

### Technical Architecture

- **Backend**: FastAPI + Pydantic v2 + PyMongo async, MongoDB Atlas. 210+ pytest tests covering every domain layer.
- **Frontend**: Next.js 14 App Router + TypeScript strict + Tailwind PWA. 15 routes, zero TypeScript errors, design tokens from `design/tokens.css` (no hardcoded hex or radii).
- **AI**: Gemma 3 (open-weight) via OpenAI-compatible endpoint on DigitalOcean GPU Droplet (vLLM/Ollama). AI parses natural-language input into structured drafts — the user must confirm before anything persists. A 60-case eval suite (`tests/evals/test_parse_eval.py`) measures parse quality; a deterministic `RulesProvider` fallback handles phone/edge cases without any LLM.
- **Workflows**: Temporal Cloud for durable orchestration — `ArrivalWatchWorkflow` nudges the owner if travel ETA is overdue then escalates to safety-granted viewers; `PromiseWorkflow` fires when a promised callback is due.
- **Privacy by design**: One visibility choke point (`domain/visibility.py`) — no router queries another user's data directly. New connection = zero access. Defaults are private. Revocation is immediate and re-checked at read time, before notification delivery, and on SSE streams.

---

### Open-Weight AI Integration

CircleCue uses **Gemma 3-4B-IT** (served via vLLM on a DigitalOcean GPU Droplet or local Ollama) through an OpenAI-compatible endpoint. The model parses free-text messages like _"studying till 8, no calls"_ or _"flight at 14:30, ETA Mumbai 6pm"_ into typed `ParseResult` structs. The provider ladder falls back gracefully: DO Gemma → local Ollama → `RulesProvider` (regex-based deterministic fallback) → form UI. AI is never shown data about other users, never does date math, and never writes to the database directly.

---

### Sponsor Technologies

| Technology | How Used |
|---|---|
| **MongoDB Atlas** | Primary database — 16 collections, async PyMongo client |
| **Render** | Hosting for API + Next.js frontend + Temporal worker |
| **DigitalOcean** | GPU Droplet serving Gemma 3 via vLLM |
| **Temporal** | Durable workflow orchestration (arrival watch, promise tracking, timeline boundaries) |

---

### Live Demo

- **App**: https://circlecue.onrender.com *(deploy after tagging)*
- **API Docs**: https://circlecue-api.onrender.com/docs *(development only)*
- **Repo**: https://github.com/[your-username]/CircleCue

### Demo Credentials (seed with `python scripts/seed_demo.py`)

| Account | Email | Password |
|---|---|---|
| Arjun Kumar | arjun@demo.circlecue.app | demo-password-arjun |
| Priya Singh | priya@demo.circlecue.app | demo-password-priya |

---

### What Makes This Special for Hacktoberfest

1. **Real relationship use case**: Built for an actual person's real anxiety (Priya worrying about Arjun during exams and travel).
2. **Not a chatbot, not a tracker**: No hidden monitoring, no continuous location, no social feed — just context shared on the owner's terms.
3. **Production-grade architecture**: The same patterns (resolver-not-stored state, temporal workflows, single visibility choke point) that would appear in a real production system.
4. **Open-weight AI first**: Uses Gemma (not a proprietary API) and includes a full eval harness so the AI's quality is measurable and improvable.
