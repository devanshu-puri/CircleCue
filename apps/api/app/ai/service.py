"""Schema validation, deterministic post-processing, and provider fallback."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.ai.adapter import LLMProvider, OllamaProvider, OpenAICompatProvider, RulesProvider
from app.ai.missing import merge_required_missing
from app.ai.people import match_person
from app.ai.schemas import Missing, ParseResult, SignificanceResult, TimeSpec
from app.ai.timeparse import resolve_time_spec
from app.config import Settings, settings
from app.core.errors import AIParseError

logger = logging.getLogger("circlecue.ai")
PARSE_SYSTEM_PROMPT = (
    Path(__file__).parent.joinpath("prompts", "parse_v1.md").read_text(encoding="utf-8")
)


@dataclass
class ParseOutcome:
    result: ParseResult
    provider: str
    model: str
    latency_ms: float
    schema_valid: bool
    repaired: bool
    error: Optional[str] = None


def providers_for(config: Settings) -> List[LLMProvider]:
    primary: List[LLMProvider] = []
    if config.AI_PROVIDER == "openai_compat":
        primary.append(OpenAICompatProvider(config.AI_BASE_URL, config.AI_MODEL, config.AI_API_KEY or ""))
        primary.append(OllamaProvider(config.AI_BASE_URL, config.AI_MODEL))
    elif config.AI_PROVIDER == "ollama":
        primary.append(OllamaProvider(config.AI_BASE_URL, config.AI_MODEL))
    primary.append(RulesProvider())
    return primary


def _resolve_times(result: ParseResult, now: datetime, tz: str, connections: List[Dict[str, str]]) -> ParseResult:
    time_fields = {
        "activity": {"start": "resolved_start_at", "end": "resolved_end_at"},
        "travel": {"depart": "resolved_depart_at", "eta": "resolved_eta_at"},
        "phone": {"until": "resolved_until"},
        "exception": {
            "date": "resolved_date",
            "new_start": "resolved_new_start",
            "new_end": "resolved_new_end",
        },
        "message": {"promise_at": "resolved_promise_at"},
        "reminder": {"due": "resolved_due"},
    }
    resolved_items = []
    missing = list(result.missing)
    missing_fields = {item.field for item in missing}

    for item in result.items:
        data = item.model_dump(mode="python")
        for field_name, output_name in time_fields.get(item.kind, {}).items():
            time_spec = getattr(item, field_name, None)
            if isinstance(time_spec, TimeSpec):
                data[output_name] = resolve_time_spec(time_spec, now, tz).isoformat()
        if item.kind == "travel" and item.companion:
            person_id, ambiguous = match_person(item.companion, connections)
            if person_id:
                data["companion_id"] = person_id
            elif ambiguous and "companion" not in missing_fields:
                missing.append(Missing(
                    field="companion",
                    question=f"Which {item.companion} do you mean?",
                ))
                missing_fields.add("companion")
        if item.kind == "message":
            audience_ids = []
            for audience_name in item.audience:
                existing_id = next(
                    (person.get("id") for person in connections if person.get("id") == audience_name),
                    None,
                )
                person_id, ambiguous = (
                    (existing_id, False)
                    if existing_id
                    else match_person(audience_name, connections)
                )
                if person_id:
                    audience_ids.append(person_id)
                elif audience_name not in missing_fields:
                    question = (
                        f"Which {audience_name} should receive this message?"
                        if ambiguous
                        else f"Who is {audience_name}? Choose a connected person."
                    )
                    missing.append(Missing(field=audience_name, question=question))
                    missing_fields.add(audience_name)
            data["audience"] = audience_ids
        if item.kind == "scenario" and item.audience:
            audience_ids = []
            for audience_name in item.audience:
                existing_id = next(
                    (person.get("id") for person in connections if person.get("id") == audience_name),
                    None,
                )
                person_id, ambiguous = (
                    (existing_id, False)
                    if existing_id
                    else match_person(audience_name, connections)
                )
                if person_id:
                    audience_ids.append(person_id)
                elif audience_name not in missing_fields:
                    question = (
                        f"Which {audience_name} should be included?"
                        if ambiguous
                        else f"Who is {audience_name}? Choose a connected person."
                    )
                    missing.append(Missing(field=audience_name, question=question))
                    missing_fields.add(audience_name)
            data["audience"] = audience_ids
        resolved_items.append(type(item).model_validate(data))

    return result.model_copy(update={"items": resolved_items, "missing": missing})


class AIService:
    def __init__(self, providers: Optional[List[LLMProvider]] = None, timeout_s: Optional[float] = None):
        self.providers = providers or providers_for(settings)
        self.timeout_s = timeout_s if timeout_s is not None else settings.AI_TIMEOUT_S

    async def parse(
        self,
        text: str,
        mode: str,
        now: datetime,
        tz: str,
        connections: Optional[List[Dict[str, str]]] = None,
        template_titles: Optional[List[str]] = None,
    ) -> ParseOutcome:
        context = {
            "text": text,
            "mode": mode,
            "now": now.isoformat(),
            "tz": tz,
            "connection_names": [person.get("name", "") for person in connections or []],
            "template_titles": template_titles or [],
        }
        user_prompt = json.dumps(context, ensure_ascii=True)
        schema = ParseResult.model_json_schema()
        system_prompt = (
            PARSE_SYSTEM_PROMPT
            + "\nThe current JSON schema is:\n"
            + json.dumps(schema, ensure_ascii=True)
        )
        last_error: Optional[Exception] = None
        for provider in self.providers:
            started = time.perf_counter()
            repaired = False
            repair_prompt = system_prompt
            for attempt in range(2):
                try:
                    raw = await asyncio.wait_for(
                        provider.generate_structured(
                            repair_prompt,
                            user_prompt,
                            schema,
                            self.timeout_s,
                        ),
                        timeout=self.timeout_s,
                    )
                    parsed = ParseResult.model_validate(raw)
                    parsed = _resolve_times(parsed, now, tz, connections or [])
                    parsed = merge_required_missing(parsed)
                    return ParseOutcome(
                        result=parsed,
                        provider=provider.name,
                        model=provider.model,
                        latency_ms=(time.perf_counter() - started) * 1000,
                        schema_valid=True,
                        repaired=repaired,
                    )
                except Exception as exc:
                    last_error = exc
                    if attempt == 0:
                        repaired = True
                        repair_prompt = (
                            system_prompt
                            + " Correct the previous schema error and return valid JSON. Error category: "
                            + type(exc).__name__
                            + ". Validation details: "
                            + json.dumps(exc.errors(), ensure_ascii=True, default=str)
                            if hasattr(exc, "errors")
                            else system_prompt
                            + " Correct the previous provider response and return valid JSON. Error category: "
                            + type(exc).__name__
                        )
                    else:
                        logger.warning(
                            "AI provider failed; trying configured fallback",
                            extra={"provider": provider.name, "error_type": type(exc).__name__},
                        )
        raise AIParseError(
            "No configured AI parser could produce a valid draft",
            details={"error_type": type(last_error).__name__ if last_error else "unknown"},
        )

    async def significance_judge(self, event_kind: str, text: str) -> SignificanceResult:
        if event_kind != "CUSTOM":
            raise ValueError("AI significance is restricted to custom/free-text events")
        schema = SignificanceResult.model_json_schema()
        for provider in self.providers:
            try:
                if isinstance(provider, RulesProvider):
                    raw = await provider.judge_significance(text)
                else:
                    raw = await asyncio.wait_for(
                        provider.generate_structured(
                            "Judge only whether this custom event is significant enough to notify. "
                            "Do not authorize recipients. Return JSON matching the schema.",
                            json.dumps({"text": text}, ensure_ascii=True),
                            schema,
                            self.timeout_s,
                        ),
                        timeout=self.timeout_s,
                    )
                return SignificanceResult.model_validate(raw)
            except Exception as exc:
                logger.warning(
                    "AI significance provider failed",
                    extra={"provider": provider.name, "error_type": type(exc).__name__},
                )
        return SignificanceResult(notify=False, reason="No provider produced a valid significance decision")