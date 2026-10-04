# Future Proposals & Ideas Parking Lot
Store out-of-scope ideas and proposals here.

## Partner credits: Tinker and Backboard (2026-10-04)
- **Tinker:** Candidate for M13 only after the current Gemma base model and measured parse-eval baseline are recorded. If pursued, use synthetic or explicitly de-identified examples, compare against the existing parse evaluation set, and record the exact fine-tuned base model and measured improvement. Do not send production user text, contact details, or travel metadata to training.
- **Backboard:** Conflicts with MEMORY.md §7 ("Not used: ... Backboard") and AGENTS.md §8 (no vector DB or web search) if used as persistent user context/memory. Do not add it to the app without a documented architecture decision that resolves these constraints. A future non-persistent evaluation of the credit is possible only if it does not receive user data or create a second source of memory.
- This records the user’s request to consider available credits; it does not authorize expanding the product architecture beyond the current source of truth.
