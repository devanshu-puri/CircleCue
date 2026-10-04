# AI Model Evaluation Report

## Status

The live Gemma/DO endpoint evaluation has not been run in this workspace. No model endpoint response evidence is available, so no model accuracy or latency figures are claimed.

The offline rules-provider behavior is covered by `apps/api/tests/test_ai_service.py` for activity, travel/phone, schedule cancellation, recurring scenarios, timezone resolution, companion matching, ambiguity, and provider fallback. This is unit coverage, not the required 60-case model evaluation.

## Remaining Gate

Run the M06 evaluation harness against the configured primary model and local Ollama fallback, covering at least 60 English, Hinglish, Tamil-English, ambiguous-time, duplicate-name, multi-item, exception, scenario, and prompt-injection cases. Record JSON validity, intent accuracy, field-level F1, resolved-time exact match, and p50/p95 latency before marking M06 complete.
