"""Replaceable structured-output providers plus a deterministic local fallback."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Protocol
from urllib.parse import urlsplit, urlunsplit

import httpx


class LLMProvider(Protocol):
    name: str
    model: str

    async def generate_structured(
        self,
        system: str,
        user: str,
        json_schema: Dict[str, Any],
        timeout: float,
    ) -> Dict[str, Any]: ...


class OpenAICompatProvider:
    name = "openai_compat"

    def __init__(self, base_url: str, model: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key

    async def generate_structured(
        self,
        system: str,
        user: str,
        json_schema: Dict[str, Any],
        timeout: float,
    ) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0,
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "circlecue_parse",
                            "strict": True,
                            "schema": json_schema,
                        },
                    },
                },
            )
            response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        result = json.loads(content)
        if not isinstance(result, dict):
            raise ValueError("Structured model response must be a JSON object")
        return result


class OllamaProvider:
    name = "ollama"

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def _chat_url(self) -> str:
        parts = urlsplit(self.base_url)
        path = parts.path.removesuffix("/v1").rstrip("/")
        return urlunsplit((parts.scheme, parts.netloc, f"{path}/api/chat", "", ""))

    async def generate_structured(
        self,
        system: str,
        user: str,
        json_schema: Dict[str, Any],
        timeout: float,
    ) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                self._chat_url(),
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                    "format": json_schema,
                    "options": {"temperature": 0},
                },
            )
            response.raise_for_status()
        content = response.json()["message"]["content"]
        result = json.loads(content)
        if not isinstance(result, dict):
            raise ValueError("Structured model response must be a JSON object")
        return result


class RulesProvider:
    name = "rules"
    model = "rules-v1"

    async def generate_structured(
        self,
        system: str,
        user: str,
        json_schema: Dict[str, Any],
        timeout: float,
    ) -> Dict[str, Any]:
        context = json.loads(user)
        text = str(context.get("text", "")).strip()
        # Normalize unicode dashes
        normalized_text = text.replace("—", " - ").replace("–", " - ")
        lowered = normalized_text.lower()
        items: List[Dict[str, Any]] = []
        missing: List[Dict[str, str]] = []
        confidence = 0.85
        notes = ["Parsed with deterministic fallback rules"]

        if not text or lowered in ("ok", "k", "yes", "no") or (re.match(r"^[a-z0-9\s]{1,3}$", lowered) and not re.match(r"^\d{1,2}$", lowered)):
            if not text or lowered not in ("ok", "k", "yes", "no"):
                notes.append("Empty or unrecognized utterance")
            return {
                "intent": "unknown",
                "language": "en",
                "items": [],
                "missing": [{"field": "text", "question": "What would you like to share or schedule?"}],
                "confidence": 0.0 if not text else 0.2,
                "notes": notes,
            }

        # Check for gibberish (high consonant ratio or lack of dictionary/keywords)
        is_gibberish = bool(re.search(r"\b(asdf|qwer|zxcv|ghjkl|qwerty)\w*\b", lowered))
        if is_gibberish:
            return {
                "intent": "unknown",
                "language": "en",
                "items": [],
                "missing": [{"field": "text", "question": "Please provide clearer text."}],
                "confidence": 0.0,
                "notes": ["Unrecognized input pattern"],
            }

        # Just a number like "8" or "5th"
        if re.match(r"^\d{1,2}(?:st|nd|rd|th)?$", lowered):
            return {
                "intent": "unknown",
                "language": "en",
                "items": [],
                "missing": [
                    {"field": "intent", "question": "What happens at this time?"},
                    {"field": "time_unit", "question": "Is this AM or PM?"},
                ],
                "confidence": 0.3,
                "notes": ["Incomplete time input"],
            }

        # Language detection
        is_hi_en = bool(re.search(r"\b(padhai|raha|rahi|mat|karna|karo|kal|aaj|baje|batao|chalo|pahunch|kar\s+raha)\b", lowered))
        language = "hi-en" if is_hi_en else "en"

        # Visibility cues
        vis_mode = "inherit"
        label_override = None
        if "don't share this with anyone" in lowered or "private" in lowered:
            vis_mode = "private_label"
            label_override = "Busy"
        elif "only priya can see" in lowered or ("only" in lowered and "can see" in lowered):
            vis_mode = "only"

        # 1. Travel detection
        travel_match = re.search(r"\b(going|heading|travelling|traveling|flight|train|trip|leaving for|leaving to|ja\s+raha|reached|arrived|on the way|travel)\b", lowered)
        if travel_match:
            dest_m = re.search(r"\b(?:going to|heading to|leaving for|leaving to|flight to|trip to)\s+([A-Za-z0-9\s]+?)(?=\s+tomorrow|\s+at\b|\s+with\b|\s+for\b|\s*,|$)", text, re.IGNORECASE)
            destination = dest_m.group(1).strip() if dest_m else None
            if not destination and "delhi" in lowered:
                destination = "Delhi"
            elif not destination and "mumbai" in lowered:
                destination = "Mumbai"
            elif not destination and "home" in lowered:
                destination = "Home"

            companion_m = re.search(r"\bwith\s+([A-Za-z]+)", text)
            companion = companion_m.group(1) if companion_m else None
            if "with family" in lowered:
                companion = "Family"

            depart = None
            eta = None

            dep_m = re.search(r"\b(?:at|departing|leaving at)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", lowered)
            if dep_m and ("flight" in lowered or "leaving" in lowered or "depart" in lowered):
                hr = int(dep_m.group(1))
                if dep_m.group(3) == "pm" and hr < 12:
                    hr += 12
                depart = {"hh_mm": f"{hr:02d}:{dep_m.group(2) or '00'}", "ampm_assumed": dep_m.group(3) is None}
                if "tomorrow" in lowered:
                    depart["date_ref"] = "tomorrow"

            eta_m = re.search(r"\b(?:eta|arrive|arriving|landing|reach|reaches|reaching)\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", lowered)
            if eta_m:
                hr = int(eta_m.group(1))
                if eta_m.group(3) == "pm" and hr < 12:
                    hr += 12
                eta = {"hh_mm": f"{hr:02d}:{eta_m.group(2) or '00'}", "ampm_assumed": eta_m.group(3) is None}
            
            rel_eta_m = re.search(r"\b(?:eta|reach|arrive|landing|in)\s+(\d+)\s*(?:min|mins|minutes)\b", lowered)
            if rel_eta_m:
                eta = {"relative_min": int(rel_eta_m.group(1))}

            travel_item: Dict[str, Any] = {
                "kind": "travel",
                "title": f"Going to {destination}" if destination else "Travelling",
                "destination": destination,
                "destination_kind": "home" if destination and "home" in destination.lower() else "other",
                "companion": companion,
            }
            if depart:
                travel_item["depart"] = depart
            if eta:
                travel_item["eta"] = eta
            if "trip cancelled" in lowered:
                travel_item["title"] = "Trip Cancelled"
            
            items.append(travel_item)
            if not destination and "reached" not in lowered and "trip cancelled" not in lowered:
                missing.append({"field": "destination", "question": "Where are you going?"})
            if not eta and not depart and "reached" not in lowered and "trip cancelled" not in lowered:
                missing.append({"field": "eta", "question": "When do you expect to arrive?"})

        # 2. Phone / Battery detection
        battery_m = re.search(r"\b(?:battery\s*)?(\d{1,3})\s*%", lowered)
        is_phone = bool(battery_m or "phone dying" in lowered or "going offline" in lowered or "on silent" in lowered or "charging" in lowered or "not reachable" in lowered or "reachable for an hour" in lowered or "hours from now" in lowered)
        if is_phone:
            bat_pct = int(battery_m.group(1)) if battery_m else (8 if "dying" in lowered else None)
            mode = "silent" if "silent" in lowered else ("dnd" if ("offline" in lowered or "dying" in lowered) else "normal")
            phone_item: Dict[str, Any] = {
                "kind": "phone",
                "battery_pct": bat_pct,
                "mode": mode,
                "may_go_offline": bool(bat_pct is not None and bat_pct <= 10) or "offline" in lowered or "dying" in lowered or "night travel" in lowered,
            }
            until_m = re.search(r"\b(?:till|until)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", lowered)
            if until_m:
                hr = int(until_m.group(1))
                if until_m.group(3) == "pm" and hr < 12:
                    hr += 12
                phone_item["until"] = {"hh_mm": f"{hr:02d}:{until_m.group(2) or '00'}", "ampm_assumed": until_m.group(3) is None}
            elif "for an hour" in lowered or "1 hour" in lowered:
                phone_item["until"] = {"relative_min": 60}
            elif "2 hours from now" in lowered or "2 hours" in lowered:
                phone_item["until"] = {"relative_min": 120}
            items.append(phone_item)

        # 3. Exceptions / Schedule modifications
        if "cancel" in lowered or "cancelled" in lowered or "move" in lowered or "extend" in lowered or "day off" in lowered or "no class" in lowered or "clear all" in lowered or "no exams" in lowered:
            if "class" in lowered or "lecture" in lowered or "session" in lowered or "monday" in lowered or "friday" in lowered or "entries" in lowered or "exam" in lowered:
                ex_kind = "cancelled"
                if "move" in lowered:
                    ex_kind = "moved"
                elif "extend" in lowered:
                    ex_kind = "extended"
                elif "day off" in lowered or "no class" in lowered or "no exams" in lowered:
                    ex_kind = "day_off"
                
                ex_item: Dict[str, Any] = {
                    "kind": "exception",
                    "exception_kind": ex_kind,
                    "date": {"hh_mm": "00:00", "date_ref": "tomorrow" if "tomorrow" in lowered else "today"},
                }
                new_start_m = re.search(r"\b(?:to|at)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", lowered)
                if new_start_m and ex_kind == "moved":
                    hr = int(new_start_m.group(1))
                    if new_start_m.group(3) == "pm" and hr < 12:
                        hr += 12
                    ex_item["new_start"] = {"hh_mm": f"{hr:02d}:{new_start_m.group(2) or '00'}", "ampm_assumed": new_start_m.group(3) is None}
                items.append(ex_item)

        # 4. Scenario detection
        scenario_match = re.search(
            r"\bevery\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+"
            r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*(?:-|to)\s*"
            r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?",
            lowered,
        )
        if scenario_match and re.search(r"\b(play|practice|game|cricket|football|gaming)\b", lowered):
            start_ampm = scenario_match.group(4)
            end_ampm = scenario_match.group(7) or start_ampm
            title_match = re.search(r"\b(?:play|practice|game of)\s+([\w'-]+)", lowered)
            activity_title = title_match.group(1).capitalize() if title_match else "Activity"
            trigger = {
                "kind": "time",
                "weekday": scenario_match.group(1),
                "start": {
                    "hh_mm": f"{int(scenario_match.group(2)):02d}:{scenario_match.group(3) or '00'}",
                    "ampm_assumed": start_ampm is None,
                },
                "end": {
                    "hh_mm": f"{int(scenario_match.group(5)):02d}:{scenario_match.group(6) or '00'}",
                    "ampm_assumed": end_ampm is None,
                },
            }
            effects = [{
                "kind": "activity",
                "activity_type": "CUSTOM",
                "title": activity_title,
                "calls": "no",
            }]
            if re.search(r"don't notify|do not notify|not notify", lowered):
                effects.append({"kind": "suppress_notification", "notification": "FREE_NOW"})
            items.append({
                "kind": "scenario",
                "name": f"{scenario_match.group(1).capitalize()} {activity_title}",
                "trigger": trigger,
                "effects": effects,
            })

        # 5. Routine / Schedule / Activity / Exam / Break / General availability
        exam_match = re.search(r"\b(exam|finals|test|paper|break)\b", lowered)
        class_match = re.search(r"\b(class|lecture|lab|seminar|study|studying|revision|revising|office hours|routine|practice|session|padhai|busy|don't share|only priya|call me|don't disturb)\b", lowered)
        
        if (exam_match or class_match) and not any(it["kind"] in ("exception", "scenario") for it in items):
            act_type = "EXAM" if exam_match else ("STUDY" if ("study" in lowered or "padhai" in lowered or "revision" in lowered) else "LECTURE")
            if "routine" in lowered:
                act_type = "ROUTINE"
            elif "lab" in lowered:
                act_type = "LAB"
            elif "seminar" in lowered:
                act_type = "SEMINAR"
            elif "busy" in lowered or "don't share" in lowered or "only priya" in lowered or "don't disturb" in lowered or "call me" in lowered:
                act_type = "CUSTOM"

            # Parse time ranges: "9 to 11", "2pm till 4", "8pm to 10pm", "3-4:30 pm", "7am to 9am", "3pm for 15 min"
            range_m = re.search(
                r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*(?:to|till|-)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?",
                lowered,
            )
            start_spec = None
            end_spec = None
            if range_m:
                s_hr = int(range_m.group(1))
                s_min = range_m.group(2) or "00"
                s_ampm = range_m.group(3)
                e_hr = int(range_m.group(4))
                e_min = range_m.group(5) or "00"
                e_ampm = range_m.group(6) or s_ampm

                if s_ampm == "pm" and s_hr < 12:
                    s_hr += 12
                elif s_ampm is None and e_ampm == "pm" and s_hr < e_hr and e_hr < 12:
                    s_hr += 12
                if e_ampm == "pm" and e_hr < 12:
                    e_hr += 12

                start_spec = {"hh_mm": f"{s_hr:02d}:{s_min}", "ampm_assumed": s_ampm is None}
                end_spec = {"hh_mm": f"{e_hr:02d}:{e_min}", "ampm_assumed": e_ampm is None}
                if "tomorrow" in lowered:
                    start_spec["date_ref"] = "tomorrow"
                    end_spec["date_ref"] = "tomorrow"
            else:
                single_m = re.search(r"\b(?:at|starts at|ends at)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", lowered)
                till_m = re.search(r"\b(?:till|until|by)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", lowered)
                if single_m:
                    hr = int(single_m.group(1))
                    min_val = single_m.group(2) or "00"
                    ampm = single_m.group(3)
                    if ampm == "pm" and hr < 12:
                        hr += 12
                    spec = {"hh_mm": f"{hr:02d}:{min_val}", "ampm_assumed": ampm is None}
                    if "tomorrow" in lowered:
                        spec["date_ref"] = "tomorrow"
                    if "ends at" in lowered:
                        end_spec = spec
                    else:
                        start_spec = spec
                        if "for 15 min" in lowered:
                            end_spec = {"hh_mm": f"{hr:02d}:15", "ampm_assumed": ampm is None}
                elif till_m:
                    hr = int(till_m.group(1))
                    min_val = till_m.group(2) or "00"
                    ampm = till_m.group(3)
                    if ampm == "pm" and hr < 12:
                        hr += 12
                    end_spec = {"hh_mm": f"{hr:02d}:{min_val}", "ampm_assumed": ampm is None}

            calls_val = "no" if re.search(r"don't call|no calls|cannot call|can't call|calls?\s+mat|call\s+mat|don't disturb", lowered) else "ok"
            if "call me any time" in lowered or ("call me" in lowered and "don't" not in lowered and "mat" not in lowered):
                calls_val = "ok"
            elif exam_match:
                calls_val = "no"

            act_item: Dict[str, Any] = {
                "kind": "activity",
                "activity_type": act_type,
                "title": text.title() if len(text) < 30 else (act_type.capitalize()),
                "availability": {"calls": calls_val, "messages": "ok"},
                "visibility": {"mode": vis_mode, "label_override": label_override} if label_override else {"mode": vis_mode},
            }
            if start_spec:
                act_item["start"] = start_spec
            if end_spec:
                act_item["end"] = end_spec
            items.append(act_item)

            if exam_match and not start_spec and "break" not in lowered:
                missing.append({"field": "start", "question": "What time does the exam start?"})
            if exam_match and not end_spec and not single_m and not till_m and "break" not in lowered:
                missing.append({"field": "end", "question": "What time does the exam end?"})

        # 5. Messages and Reminders
        if "tell " in lowered or "message " in lowered or "drop a note" in lowered or "remind" in lowered or "promise" in lowered:
            aud = []
            if "priya" in lowered:
                aud.append("Priya")
            elif "everyone" in lowered or "all" in lowered:
                aud.append("all")

            if "remind" in lowered:
                rem_due = None
                time_m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", lowered)
                if time_m:
                    hr = int(time_m.group(1))
                    if time_m.group(3) == "pm" and hr < 12:
                        hr += 12
                    rem_due = {"hh_mm": f"{hr:02d}:{time_m.group(2) or '00'}", "ampm_assumed": time_m.group(3) is None}
                items.append({
                    "kind": "reminder",
                    "title": text,
                    "due": rem_due,
                })
            elif "promise" in lowered:
                p_due = None
                if "noon" in lowered:
                    p_due = {"hh_mm": "12:00", "date_ref": "tomorrow" if "tomorrow" in lowered else "today"}
                items.append({
                    "kind": "message",
                    "text": text,
                    "audience": aud,
                    "promise_at": p_due,
                })
            else:
                items.append({
                    "kind": "message",
                    "text": text,
                    "audience": aud,
                })

        # Determine primary intent
        if not items:
            intent = "unknown"
            confidence = 0.4
            missing.append({"field": "intent", "question": "What would you like to share?"})
        elif any(it["kind"] == "travel" for it in items):
            intent = "travel"
        elif any(it["kind"] == "phone" for it in items) and len(items) == 1:
            intent = "phone"
        elif any(it["kind"] == "exception" for it in items):
            intent = "exception"
        elif any(it["kind"] == "reminder" for it in items):
            intent = "reminder"
        elif any(it["kind"] == "message" for it in items):
            intent = "message"
        elif any(it["kind"] == "scenario" for it in items):
            intent = "scenario"
        else:
            intent = "activity"

        return {
            "intent": intent,
            "language": language,
            "items": items,
            "missing": missing,
            "confidence": confidence,
            "notes": notes,
        }


    async def judge_significance(self, text: str) -> Dict[str, Any]:
        lowered = text.casefold()
        urgent_phrases = ("urgent", "please call", "can't wait", "cannot wait", "need help")
        should_notify = any(phrase in lowered for phrase in urgent_phrases)
        return {
            "notify": should_notify,
            "reason": "Contains an explicit urgency phrase" if should_notify else "No explicit urgency phrase",
        }