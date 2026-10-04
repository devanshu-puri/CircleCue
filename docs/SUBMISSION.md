# I Built CircleCue for a Friend, Then Taught My Repo to Remember

*This is a submission for the [Hacktoberfest Weekend Challenge: Build for a Friend](https://dev.to/challenges/hacktoberfest-weekend-2026-10-01).* #hf26challenge

## What I Built

CircleCue is a private, permission-based app that helps trusted people share the context that usually leads to repeated calls and unanswered messages: what they are doing, when they expect to be free, whether they are travelling, and whether their phone is on silent or running low on battery.

I built it for a friend who worries when I cannot answer, especially when I am busy or travelling. Instead of asking them to guess, I can share an update once. They see only the cards and details I grant them. There is no background location tracking, public feed, or hidden monitoring.

## Demo

- [Live app](https://circlecue-web.onrender.com/) (sign-in required)
- [Source code](https://github.com/devanshu-puri/CircleCue)

## Code

The project includes four handoff files that preserve what an agent needs between sessions:

- [AGENTS.md](https://github.com/devanshu-puri/CircleCue/blob/master/AGENTS.md) — project rules and safety boundaries
- [docs/MEMORY.md](https://github.com/devanshu-puri/CircleCue/blob/master/docs/MEMORY.md) — product contracts and current module status
- [docs/DECISIONS.md](https://github.com/devanshu-puri/CircleCue/blob/master/docs/DECISIONS.md) — trade-offs and migration notes
- [docs/DEVLOG.md](https://github.com/devanshu-puri/CircleCue/blob/master/docs/DEVLOG.md) — implementation history and lessons

The [agent_pack directory](https://github.com/devanshu-puri/CircleCue/tree/master/agent_pack) contains reusable module prompts, design guidance, and a kickoff guide. It was renamed from an Antigravity-specific pack so a different coding agent can continue from the same project context.

## How I Built It

The app uses Next.js and TypeScript for the PWA, FastAPI and Pydantic for the API, MongoDB Atlas for persistence, and Temporal for durable travel and timeline workflows. Render hosts the app and API; a DigitalOcean GPU serves Gemma.

Gemma turns plain-language updates such as “studying till 8, no calls” into structured drafts. The user reviews and confirms a draft before it is saved or shared. The model receives the owner's text and limited parsing context; it never sees another person's state, grants access, or writes to the database. Deterministic code resolves times and permissions. If the model is unavailable, a rules-based parser and regular forms keep the app usable.

I worked across AI coding-agent sessions, including one with Antigravity. I did not have an unlimited token budget or a higher-tier model available, and context ran out quickly. I started losing the thread between sessions, so I split the work into modules with explicit completion steps and made the repository carry the project memory. The next agent reads the same rules, current status, decisions, and build history instead of relying on a long chat replay. I’ve made that handoff pack agent-neutral so work can continue when a model’s tokens run out or a different agent is a better fit.

That approach connects with other developers’ notes on [project memory versus chat history](https://dev.to/louisen0o0/project-memory-is-not-chat-history-a-tiny-handoff-layer-for-ai-agents-2n03) and [repo contracts for coding agents](https://dev.to/otaready/why-coding-agents-need-repo-contracts-not-bigger-context-windows-40gp). For this app, the files are not a substitute for tests: each module still has a Definition of Done, and the project is verified with backend tests and a production frontend build.

## Why Does Open Innovation Matter?

Using an open-weight model behind a replaceable adapter gives me a path to run inference on infrastructure I control or locally during development, and lets me change models without rebuilding the product around one closed API. That matters for a privacy-focused app: the model receives the current user's text and limited parsing context, never another person's state; permissions and sharing stay in deterministic application code.

Open tools also made the project more resilient to my limited AI budget. I could move between agents, keep the source of truth in versioned files, and use a rules-based fallback when model access was unavailable. The open model did not remove the hard parts; it gave me more control over how I could keep building through them.

## Prize Categories

- Best Use of Render
- Best Use of DigitalOcean
- Best Use of Gemma
- Best Use of MongoDB Atlas
- Best Use of Temporal
