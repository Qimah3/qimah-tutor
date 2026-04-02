import re

_PATTERNS = [
    ("old_exam", re.compile(r"major|midterm|final|quiz|exam", re.IGNORECASE)),
    ("lecture_note", re.compile(r"lab|lecture|notes|slide", re.IGNORECASE)),
    ("screenshot", re.compile(r"^(whatsapp|screenshot)", re.IGNORECASE)),
]


def classify_source(filename: str, overrides: dict | None = None) -> str:
    if overrides and filename in overrides:
        return overrides[filename]
    for source_type, pattern in _PATTERNS:
        if pattern.search(filename):
            return source_type
    return "handout"
