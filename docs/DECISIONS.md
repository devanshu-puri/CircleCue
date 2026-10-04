# Architectural Decisions Log
Log architectural decisions here as key trade-offs are evaluated during execution.

## D31 — Make the handoff pack agent-neutral (2026-10-04)
- Rename the repository's `antigravity-pack/` directory to `agent_pack/` and remove tool-specific setup language so the same project memory, rules, design references, and module prompts can be used across coding agents.
- Migration note: update path references in the start guide and continuation prompt. The pack is reference material; the active source of truth remains root `AGENTS.md` and `docs/MEMORY.md`. No application imports or runtime paths depend on this directory.
