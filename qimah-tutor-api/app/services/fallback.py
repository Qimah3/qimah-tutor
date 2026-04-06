"""Fallback controller — decides generation mode based on grounding quality."""


def determine_mode(
    grounding_level: str,
    topic_content_length: int,
    has_code_blocks: bool,
    has_headings: bool,
) -> dict:
    """Determine generation mode based on grounding level and topic richness.

    Fallback hierarchy:
      grounded      — high grounding: full generation from source material
      concept_review — medium grounding: reduced set from partial sources
      topic_only    — low grounding but topic has enough content
      insufficient  — low grounding and topic too thin

    "Enough content" = topic_content_length >= 200 OR has_code_blocks OR has_headings.

    Returns dict with keys: mode, quiz_count, flashcard_count, quiz_allowed, flashcard_allowed.
    """
    if grounding_level == "high":
        return {
            "mode": "grounded",
            "quiz_count": 5,
            "flashcard_count": 10,
            "quiz_allowed": True,
            "flashcard_allowed": True,
        }

    if grounding_level == "medium":
        return {
            "mode": "concept_review",
            "quiz_count": 3,
            "flashcard_count": 6,
            "quiz_allowed": True,
            "flashcard_allowed": True,
        }

    # grounding_level == "low" — check if topic has enough content
    has_enough_content = (
        topic_content_length >= 200 or has_code_blocks or has_headings
    )

    if has_enough_content:
        return {
            "mode": "topic_only",
            "quiz_count": 0,
            "flashcard_count": 8,
            "quiz_allowed": False,
            "flashcard_allowed": True,
        }

    return {
        "mode": "insufficient",
        "quiz_count": 0,
        "flashcard_count": 0,
        "quiz_allowed": False,
        "flashcard_allowed": False,
    }
