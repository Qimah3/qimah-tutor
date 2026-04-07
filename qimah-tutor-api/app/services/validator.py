"""Output validator for LLM-generated quiz and flashcard responses.

Three stages:
1. sanitize_json — strip markdown fences from raw LLM output
2. validate_quiz_response / validate_flashcard_response — structural checks
3. run_semantic_checks — source excerpt matching against RAG chunks
"""

import copy
import logging
import re

logger = logging.getLogger(__name__)

VALID_CARD_TYPES = {"definition", "contrast", "formula", "code", "mistake", "trap"}


def sanitize_json(raw: str) -> str:
    """Strip markdown code fences from LLM output."""
    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", raw)
    cleaned = re.sub(r"\n?```\s*$", "", cleaned)
    return cleaned


def validate_quiz_response(data: dict) -> list[str]:
    """Structural validation for quiz responses. Returns list of error strings."""
    errors: list[str] = []
    questions = data.get("questions")
    if questions is None:
        errors.append("missing 'questions' field")
        return errors

    for i, q in enumerate(questions):
        prefix = f"question[{i}]"

        # q text length
        q_text = q.get("q")
        if q_text is None:
            errors.append(f"{prefix}: missing 'q' field")
        elif len(q_text) <= 10:
            errors.append(f"{prefix}: q length must be > 10 chars")

        # options: exactly 4, unique
        options = q.get("options")
        if options is None:
            errors.append(f"{prefix}: missing 'options' field")
        elif len(options) != 4:
            errors.append(f"{prefix}: must have exactly 4 options, got {len(options)}")
        else:
            if len(set(options)) != len(options):
                errors.append(f"{prefix}: duplicate options found")

        # correct: 0-3
        correct = q.get("correct")
        if correct is None:
            errors.append(f"{prefix}: missing 'correct' field")
        elif not (0 <= correct <= 3):
            errors.append(f"{prefix}: correct must be 0-3, got {correct}")

        # explanation
        explanation = q.get("explanation")
        if explanation is None:
            errors.append(f"{prefix}: missing 'explanation' field")
        else:
            why_correct = explanation.get("why_correct")
            if why_correct is None:
                errors.append(f"{prefix}: missing 'explanation.why_correct'")
            elif len(why_correct) <= 20:
                errors.append(f"{prefix}: explanation.why_correct must be > 20 chars")

            why_wrong = explanation.get("why_wrong")
            if why_wrong is None:
                errors.append(f"{prefix}: missing 'explanation.why_wrong'")
            elif len(why_wrong) <= 20:
                errors.append(f"{prefix}: explanation.why_wrong must be > 20 chars")

        # source excerpt
        source = q.get("source")
        if source is None:
            errors.append(f"{prefix}: missing 'source' field")
        else:
            excerpt = source.get("source_excerpt")
            if excerpt is None:
                errors.append(f"{prefix}: missing 'source.source_excerpt'")
            elif len(excerpt) <= 10:
                errors.append(f"{prefix}: source_excerpt must be > 10 chars")

    return errors


def validate_flashcard_response(data: dict) -> list[str]:
    """Structural validation for flashcard responses. Returns list of error strings."""
    errors: list[str] = []
    cards = data.get("cards")
    if cards is None:
        errors.append("missing 'cards' field")
        return errors

    if len(cards) == 0:
        errors.append("cards must be non-empty")
        return errors

    card_types_seen: set[str] = set()

    for i, card in enumerate(cards):
        prefix = f"card[{i}]"

        card_type = card.get("card_type")
        if card_type is None:
            errors.append(f"{prefix}: missing 'card_type' field")
        elif card_type not in VALID_CARD_TYPES:
            errors.append(
                f"{prefix}: invalid card_type '{card_type}', "
                f"must be one of {sorted(VALID_CARD_TYPES)}"
            )
        else:
            card_types_seen.add(card_type)

        source = card.get("source")
        if source is None:
            errors.append(f"{prefix}: missing 'source' field")
        else:
            excerpt = source.get("source_excerpt")
            if excerpt is None:
                errors.append(f"{prefix}: missing 'source.source_excerpt'")
            elif len(excerpt) <= 10:
                errors.append(f"{prefix}: source_excerpt must be > 10 chars")

    if len(card_types_seen) < 3:
        errors.append(
            f"need at least 3 distinct card_type values, got {len(card_types_seen)}: "
            f"{sorted(card_types_seen)}"
        )

    return errors


def _normalize_whitespace(text: str) -> str:
    """Collapse multiple whitespace chars to a single space."""
    return re.sub(r"\s+", " ", text).strip()


def _excerpt_matches_any_chunk(excerpt: str, chunks: list[dict]) -> bool:
    """Check if normalized excerpt is a substring of any chunk's text."""
    norm_excerpt = _normalize_whitespace(excerpt)
    for chunk in chunks:
        chunk_text = chunk.get("text", "")
        norm_chunk = _normalize_whitespace(chunk_text)
        if norm_excerpt in norm_chunk:
            return True
    return False


def run_semantic_checks(data: dict, chunks: list[dict]) -> dict:
    """Best-effort semantic checks. Returns a copy of data with modifications."""
    result = copy.deepcopy(data)
    mode = result.get("mode", "grounded")
    is_strict = mode == "grounded"

    # Determine item key: "questions" for quiz, "cards" for flashcard
    item_key = "questions" if result.get("type") == "quiz" else "cards"
    items = result.get(item_key, [])

    kept: list[dict] = []
    for item in items:
        source = item.get("source", {})
        excerpt = source.get("source_excerpt", "")

        if not excerpt:
            if is_strict:
                logger.warning("Removing item with empty excerpt in grounded mode")
                continue
            kept.append(item)
            continue

        if _excerpt_matches_any_chunk(excerpt, chunks):
            kept.append(item)
        elif is_strict:
            logger.warning(
                "Removing item — excerpt not found in chunks: %.60s...", excerpt
            )
        else:
            logger.warning(
                "Excerpt not found in chunks (non-strict, keeping): %.60s...", excerpt
            )
            kept.append(item)

    result[item_key] = kept
    return result
