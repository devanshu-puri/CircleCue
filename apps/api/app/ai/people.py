"""Match extracted people only against the owner's active connections."""
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple


def match_person(
    name: str,
    connections: List[Dict[str, str]],
) -> Tuple[Optional[str], bool]:
    normalized = " ".join(name.casefold().split())
    exact = [
        person for person in connections
        if " ".join(person.get("name", "").casefold().split()) == normalized
    ]
    if len(exact) == 1:
        return exact[0].get("id"), False
    if len(exact) > 1:
        return None, True

    first_name_matches = [
        person for person in connections
        if " ".join(person.get("name", "").casefold().split()).split(" ")[0] == normalized
    ]
    if len(first_name_matches) == 1:
        return first_name_matches[0].get("id"), False
    if len(first_name_matches) > 1:
        return None, True

    scored = sorted(
        [
            (
            SequenceMatcher(
                None,
                normalized,
                " ".join(person.get("name", "").casefold().split()),
            ).ratio(),
            person,
            )
            for person in connections
        ],
        key=lambda pair: pair[0],
        reverse=True,
    )
    if not scored or scored[0][0] < 0.82:
        return None, False
    if len(scored) > 1 and scored[0][0] - scored[1][0] < 0.03:
        return None, True
    return scored[0][1].get("id"), False