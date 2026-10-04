# M14: Seed, demo clock, docs, submission
**Depends on:** P0 modules. Start the write-up skeleton early; finalize Monday morning.

## Build
1. **`scripts/seed_demo.py`:** personas: Arjun (college student), Lakshmi (his mom), Rahul (friend), plus Dad. Arjun has a full timetable (A/B weeks), an exam day with two exams, routine, a Friday cricket scenario, connection plans (Mom daily, Dad Sunday). Grants preconfigured to match the demo story. Idempotent, resettable.
2. **Demo clock:** `DEMO_CLOCK=true` shows a visible banner; `/dev/clock/advance`, `/dev/clock/set`, `/dev/tick` (guarded by flag + admin token). Also keep real-timer demos: create a break that starts in 2 minutes so judges can see real Temporal timers.
3. **Demo script** `docs/DEMO.md` (2-3 minute video): story first (the real mother and son), then Workflows 1-5 from MASTER_PROMPT, then Temporal UI + Sentry trace + model endpoint on DO + (P1) best-time-to-call. Include a fallback path if the model is slow.
4. **README.md:** problem, screenshots, architecture diagram, run locally (one command, Ollama + Gemma, fully offline), deploy, env vars, model swap instructions (change AI_BASE_URL/AI_MODEL), how to add a provider, privacy model, limits.
5. **`docs/ARCHITECTURE.md`:** diagram, resolver precedence, visibility choke point, notification pipeline, Temporal workflows.
6. **`docs/SUBMISSION.md`:** the DEV post draft with sections in this order:
   - Title + required tags: `#devchallenge #weekendchallenge #hf26challenge`
   - **What I built** and **who I built it for** (real person, real problem, why calls/chats weren't enough). Include their actual words about it.
   - **Demo** (link + video + screenshots)
   - **Code** (repo link)
   - **How I built it** (frontend, backend, resolver, permissions, notifications, AI pipeline, Temporal, partners)
   - **Open-source AI**: why Gemma/open weights; local run; data stays private; model swappable; fine-tune path (and Tinker results if done); cost vs closed API with real numbers; where open beats closed.
   - **My agent session** (link/embed if available)
   - **Prize categories** (only those genuinely used: Gemma, DigitalOcean, Render, Temporal; Prior Labs if P1 shipped; Tinker if P2 shipped)
   Writing quality is weighted most: concrete moments, one failure and how you fixed it, no marketing fluff.
7. Final checklist: public repo, license, no secrets in history, deployed URL tested on a phone, video uploaded, post tagged, submitted before **10:30 AM IST Mon Oct 5** (deadline 12:29 PM IST).

## DoD: a stranger can watch the video, open the link, and understand the product in 60 seconds. Update MEMORY.md; mark all statuses.
