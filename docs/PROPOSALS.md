# Future Proposals & Ideas Parking Lot
Store out-of-scope ideas and proposals here.

## Partner credits: Tinker and Backboard (2026-10-04)
- **Tinker:** Candidate for M13 only after the current Gemma base model and measured parse-eval baseline are recorded. If pursued, use synthetic or explicitly de-identified examples, compare against the existing parse evaluation set, and record the exact fine-tuned base model and measured improvement. Do not send production user text, contact details, or travel metadata to training.
- **Backboard:** Conflicts with MEMORY.md §7 ("Not used: ... Backboard") and AGENTS.md §8 (no vector DB or web search) if used as persistent user context/memory. Do not add it to the app without a documented architecture decision that resolves these constraints. A future non-persistent evaluation of the credit is possible only if it does not receive user data or create a second source of memory.
- This records the user’s request to consider available credits; it does not authorize expanding the product architecture beyond the current source of truth.

## New connection permission editor defaults (2026-10-04)
- The user requested that new people start with all card access and alerts selected, with the owner able to unselect any item. The grant editor now preselects all access only in the unsaved draft, and the owner must explicitly save. This preserves MEMORY.md's zero-access-on-connection rule and AGENTS.md's private-by-default boundary.
- If product intent later changes to automatically persist full access immediately after acceptance, that would conflict with both privacy rules and requires a separate explicit architecture/product decision. Current implementation does not auto-grant.
