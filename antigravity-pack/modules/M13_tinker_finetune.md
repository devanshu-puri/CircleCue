# M13: Tinker fine-tune and measured eval (P2, STRETCH)
**Only start if P0 is green and at least 5 hours remain.** Time-box: 4 hours. Safe to drop; nothing depends on it.

## Honesty rules
- First check Tinker's docs/model list for supported base models. Fine-tune the closest small open model actually available. **If Gemma is not available, say so and name the model you really tuned. Never claim Gemma was fine-tuned if it was not.**
- Training data is synthetic or hand-written. **Never use real users' text.**

## Build
1. `ai/evals/` reuse: `cases.jsonl` (held-out, never trained on; >=60 hand-written, include your own Hinglish phrasing).
2. `scripts/make_finetune_data.py`: generate 1,000-2,000 (utterance -> ParseResult JSON) pairs from templates + variations (English, Hinglish, Tamil-English), using Gemma to paraphrase and code to compute gold labels; dedupe against the eval set.
3. Baseline: base model, same prompt, measured with `run_eval.py` (JSON validity %, intent accuracy, field F1, time exact match, p50/p95 latency, avg tokens).
4. Fine-tune with Tinker (LoRA SFT per docs; verify API). Evaluate on the same held-out set. Shorter prompts after tuning (no few-shots) should cut tokens/latency: measure it.
5. Serving: if weights are exportable, serve on the DO Droplet via the same adapter; otherwise evaluate through Tinker's sampling interface only and say so.
6. Add a comparison table to `docs/EVAL_REPORT.md` and the write-up: baseline vs tuned (accuracy, validity, latency, tokens/cost). Report honestly if gains are modest.
## DoD: reproducible scripts + table with real numbers. Update MEMORY.md.
