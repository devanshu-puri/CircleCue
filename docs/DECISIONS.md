# Architectural Decisions Log
Log architectural decisions here as key trade-offs are evaluated during execution.

## D32 — Rotating Today headline (2026-10-04)
- Add a rotating “Friends / Family / Loved ones” headline above Today’s shared-status card to communicate CircleCue’s purpose.
- Keep it CSS-only, token-colored, and accessible with a stable screen-reader phrase; users who request reduced motion see the static Friends wording.
- No route, data, permission, or notification behavior changes.

## D31 — Make the handoff pack agent-neutral (2026-10-04)
- Rename the repository's `antigravity-pack/` directory to `agent_pack/` and remove tool-specific setup language so the same project memory, rules, design references, and module prompts can be used across coding agents.
- Migration note: update path references in the start guide and continuation prompt. The pack is reference material; the active source of truth remains root `AGENTS.md` and `docs/MEMORY.md`. No application imports or runtime paths depend on this directory.
