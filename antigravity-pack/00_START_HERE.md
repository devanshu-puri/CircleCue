# START HERE: Antigravity Build Pack

Working name: `{{APP_NAME}}` (placeholder; ideas: Kinwise, Nearby, Soon). Replace everywhere once chosen.

## What this pack is
A private, permission-based life-context network for trusted people. Not social media. Core promise:
"Know what matters about the people you care about, without constantly calling or asking."

## Hard deadline (verified)
Submissions close **Mon Oct 5, 06:59 UTC = 12:29 PM IST**. Aim to submit by **10:30 AM IST** for buffer. Today is Sat Oct 3.
That is roughly 36 hours of working time, so scope is tiered. Nothing below P0 may block P0.

## Files in this pack
| File | Purpose |
|---|---|
| `AGENTS.md` | Rules the coding agent must follow every session. Copy to repo root. |
| `MEMORY.md` | Locked decisions, contracts, build status. Copy to `/docs/MEMORY.md`. Agent updates it after each module. |
| `01_SCENARIO_CATALOG.md` | All scenarios elaborated: reasons, conditions, edge cases, new major cases, tiers. |
| `MASTER_PROMPT.md` | Full-system prompt: architecture, contracts, module order. Paste first. |
| `modules/M00 ... M14` | One prompt per build module. Paste one at a time, in order. |

## How to run it in Antigravity
1. Create repo. Put `AGENTS.md` at root, `MEMORY.md` in `/docs/`. (If Antigravity has a rules/memory folder, mirror AGENTS.md there too.)
2. Paste `MASTER_PROMPT.md`. Tell the agent: "Read it, read AGENTS.md and docs/MEMORY.md, confirm understanding in 10 lines, build nothing yet."
3. Paste modules one at a time. After each: run its Definition of Done, commit, confirm MEMORY.md "Build Status" was updated.
4. Never skip M01 to M04: they are the spine. Everything else plugs into them.
5. Design is supplied: put `design/DESIGN.md`, `design/APP_DESIGN_MAPPING.md`, `design/tokens.css` in the repo `/design` folder before M10.

## Priority tiers and recommended timeline
| Tier | Contents | Target |
|---|---|---|
| **P0** | M00-M08, M10, M11 (basic), M12 (deploy), M14 (seed + demo + write-up). Gemma on DigitalOcean, Render, Atlas, Sentry, Temporal (2 workflows). | Done by Sun night |
| **P1** | M09 TabPFN best-time-to-call, AI daily summary, urgent override, private-label per viewer, web push, share links | Sun night to Mon 6 AM IST, only if P0 is green |
| **P2** | M13 Tinker fine-tune, voice (ElevenLabs), elder mode, companion proxy-post, timetable photo import | Only if time remains. Safe to drop. |

Suggested clock: Sat = M00-M05 + M06 skeleton. Sun = M06-M08, M10, deploy. Mon early = P1 / polish / record demo / write post / submit.

## Partner map (each one earns its place)
| Partner | Real role in product | Tier |
|---|---|---|
| Gemma (open-weight) | All language understanding: activity/scenario/exception parsing, missing-info detection, significance judging, summaries | P0 |
| DigitalOcean | GPU Droplet serving Gemma (vLLM or Ollama, OpenAI-compatible endpoint). Optional: TabPFN service beside it | P0 |
| Render | Next.js web, FastAPI API, Temporal worker (background worker) | P0 |
| Temporal | Durable timers: per-user timeline boundaries (break starts), arrival/check-on-me escalation, callback promises | P0 |
| MongoDB Atlas | Data layer (not a prize target, just the DB) | P0 |
| Sentry | Errors + AI/workflow tracing | P0 basic |
| Prior Labs TabPFN | Predict P(call is picked up) per time slot from small call history; ranks "best time to call" | P1 |
| Tinker (Thinking Machines) | Fine-tune a small open model for structured extraction; report measurable gain vs baseline | P2 |
| ElevenLabs, Backboard, Mastra, SerpApi, Arduino | Not used. Do not add. | n/a |

## Deviations from your uploaded files (deliberate, logged in MEMORY.md)
- Arrival Watch (check-on-me lite) promoted to P0: it is the best honest Temporal use and costs little.
- Time-based custom scenarios execute in P0; event-triggered ones are P1.
- Activities require an expected end (auto-default) so statuses never go stale and lie.
- Every AI parse is shown to the user as an editable draft; nothing is saved or shared until confirmed.
- Activities and schedules are templates + a pure resolver, not a pile of cron jobs. Temporal only triggers notifications.

## Your two real-world tasks (writing quality is weighted most)
1. Give the app to a real person (your mom or the friend) before Mon morning. Ask one question: "What did this change for you?" Save the exact words.
2. Capture the agent session (DevRelay/Entire if available) for the submission.
