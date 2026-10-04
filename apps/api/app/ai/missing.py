"""Merge deterministic required-field questions into model or rules drafts."""
from app.ai.schemas import Missing, ParseResult


def merge_required_missing(result: ParseResult) -> ParseResult:
    missing = list(result.missing)
    known = {item.field for item in missing}

    def require(field: str, question: str) -> None:
        if field not in known:
            missing.append(Missing(field=field, question=question))
            known.add(field)

    travel_items = [item for item in result.items if item.kind == "travel"]
    phone_items = [item for item in result.items if item.kind == "phone"]
    for travel in travel_items:
        if not travel.destination:
            require("destination", "Where are you going?")
        if not travel.eta and not travel.depart:
            require("eta", "When do you expect to arrive?")

    if travel_items and any(
        item.battery_pct is not None and item.battery_pct <= 10
        for item in phone_items
    ):
        if not travel_items[0].companion:
            require("companion", "Who are you travelling with?")
        if not travel_items[0].eta:
            require("eta", "When do you expect to arrive?")

    for item in result.items:
        if item.kind == "message" and not item.text and not item.template_key:
            require("message", "What would you like the message to say?")
    if result.intent != "unknown" and result.confidence < 0.5:
        require("confirmation", "Please review these details before sharing.")

    return result.model_copy(update={"missing": missing})
