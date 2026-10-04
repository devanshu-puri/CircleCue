import html
import re

def sanitize_user_text(text: str, max_len: int = 500) -> str:
    """Strip HTML tags, unescape entities, normalize whitespace, and length-limit."""
    if not text:
        return ""
    # Strip HTML tags
    clean = re.sub(r"<[^>]+>", "", text)
    # Unescape HTML entities
    clean = html.unescape(clean)
    # Normalize whitespace
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:max_len]
