# M06: AI service (open-weight Gemma, replaceable)
**Depends on:** M04, M05 (draft schemas), M03 (people matching uses owner's connections only). **This is what the judges grade as "AI at core".**

## Build
1. **Adapter** `ai/adapter.py`: `class LLMProvider: generate_structured(system, user, json_schema, timeout) -> dict`. Implementations: `OpenAICompatProvider` (vLLM, DO endpoint, Ollama /v1, any compatible), `OllamaProvider` (native `format` schema), `RulesProvider` (regex/dateparser fallback for simple patterns: "studying till 8", "battery 5%", "going home with X, eta N min"). Selected by env; add a provider by adding one file. Verify each server's structured-output option from its docs (`response_format` json_schema vs vLLM guided decoding vs Ollama `format`).
2. **Schemas** `ai/schemas.py`: `ParseResult`, `DraftItem` discriminated union (activity, travel, phone, exception, scenario, message, reminder), `TimeSpec`, `Missing`. (Shape in MEMORY 5.6.) Items can reference earlier items ("travel departs after item 0 ends").
3. **Prompts** `ai/prompts/`: one system prompt per task, versioned (`parse_v1.md`). Include: today's date, weekday, owner tz, owner's connection first names, owner's template titles, strict "output JSON only", few-shot examples in English, Hinglish and Tamil-English, rules: never invent names/times, use `ampm_assumed`, put unknowns in `missing`.
4. **Deterministic post-processing:**
   - `timeparse.py`: TimeSpec -> UTC datetimes with owner tz (handles "till 4" => next 4 PM if now is afternoon, "tomorrow", weekdays, "in 40 min"). Never trust model arithmetic.
   - `people.py`: fuzzy-match companion/target names to owner's connections; 1 match -> link; many -> add `missing` question; 0 -> unlinked free-text companion.
   - `missing.py`: required fields per kind (travel needs destination, ETA or depart; low battery needs companion + ETA if travelling) merged with model-reported `missing`.
5. **Service** `ai/service.py`: `parse(user, text, mode, client_now) -> ParseResult` with ladder: primary -> one repair retry (feed validation errors) -> secondary -> RulesProvider -> `intent=unknown`. Timeout from env. Record `ai_invocations` (no raw text unless opted in) and a Sentry span `ai.parse` with attributes: provider, model, latency, schema_valid, repaired, intent, item_count.
6. Endpoints: `POST /ai/parse` (persists nothing, returns drafts with resolved times for preview), `POST /ai/confirm` (accepts possibly edited drafts -> creates entities via M05/M07 services with provenance `ai_parsed_user_confirmed`; marks invocation confirmed).
7. **Other tasks (smaller prompts, same adapter):**
   - `significance_judge` (P0, only for CUSTOM/free-text events): `{notify: bool, reason}`; deterministic table is the floor/ceiling for known kinds.
   - `daily_summary` (P1): from the owner's own day timeline -> one sentence chain; private to owner.
   - `timetable_import` (P1): paste text of a timetable -> SCHEDULE_SLOT drafts.
8. **Eval harness** `ai/evals/`: `cases.jsonl` (>=60: single, multi-item, ambiguous AM/PM, duplicate names, Hinglish, Tamil-English, scenarios, exceptions, battery/travel combos, adversarial/prompt-injection text inside a message). `run_eval.py --provider X` outputs JSON-validity %, intent accuracy, field-level F1, time-resolution exact match, p50/p95 latency. Writes `docs/EVAL_REPORT.md`. This baseline is reused by M13.

## Safety rules
Model never sees other users' states. Free text shown to others is sanitized post-parse. Model output is never executed as instructions. Confidence < 0.5 or missing required -> UI asks, does not guess.

## DoD: `/ai/parse` returns correct drafts for the 5 demo utterances on the primary model; eval report generated; killing the model endpoint still yields rules-parser or a graceful "use the form" response. Update MEMORY.md.
