"""Tests for fallback controller — Task 10."""


def test_grounded_mode():
    from app.services.fallback import determine_mode

    result = determine_mode(
        grounding_level="high",
        topic_content_length=500,
        has_code_blocks=True,
        has_headings=True,
    )
    assert result["mode"] == "grounded"
    assert result["quiz_allowed"] is True
    assert result["flashcard_allowed"] is True


def test_grounded_quiz_count():
    from app.services.fallback import determine_mode

    result = determine_mode(
        grounding_level="high",
        topic_content_length=500,
        has_code_blocks=False,
        has_headings=True,
    )
    assert result["quiz_count"] == 5
    assert result["flashcard_count"] == 10


def test_concept_review_mode():
    from app.services.fallback import determine_mode

    result = determine_mode(
        grounding_level="medium",
        topic_content_length=500,
        has_code_blocks=True,
        has_headings=True,
    )
    assert result["mode"] == "concept_review"
    assert result["quiz_count"] == 3
    assert result["flashcard_count"] == 6
    assert result["quiz_allowed"] is True
    assert result["flashcard_allowed"] is True


def test_topic_only_mode():
    from app.services.fallback import determine_mode

    result = determine_mode(
        grounding_level="low",
        topic_content_length=500,
        has_code_blocks=True,
        has_headings=True,
    )
    assert result["mode"] == "topic_only"
    assert result["quiz_allowed"] is False
    assert result["flashcard_allowed"] is True
    assert result["flashcard_count"] == 8


def test_topic_only_with_headings_only():
    from app.services.fallback import determine_mode

    result = determine_mode(
        grounding_level="low",
        topic_content_length=100,
        has_code_blocks=False,
        has_headings=True,
    )
    assert result["mode"] == "topic_only"


def test_topic_only_with_code_blocks_only():
    from app.services.fallback import determine_mode

    result = determine_mode(
        grounding_level="low",
        topic_content_length=100,
        has_code_blocks=True,
        has_headings=False,
    )
    assert result["mode"] == "topic_only"


def test_topic_only_with_enough_text():
    from app.services.fallback import determine_mode

    result = determine_mode(
        grounding_level="low",
        topic_content_length=200,
        has_code_blocks=False,
        has_headings=False,
    )
    assert result["mode"] == "topic_only"


def test_insufficient_material():
    from app.services.fallback import determine_mode

    result = determine_mode(
        grounding_level="low",
        topic_content_length=100,
        has_code_blocks=False,
        has_headings=False,
    )
    assert result["mode"] == "insufficient"
    assert result["quiz_allowed"] is False
    assert result["flashcard_allowed"] is False


def test_insufficient_quiz_count_zero():
    from app.services.fallback import determine_mode

    result = determine_mode(
        grounding_level="low",
        topic_content_length=50,
        has_code_blocks=False,
        has_headings=False,
    )
    assert result["quiz_count"] == 0
    assert result["flashcard_count"] == 0


def test_topic_only_quiz_count_zero():
    from app.services.fallback import determine_mode

    result = determine_mode(
        grounding_level="low",
        topic_content_length=500,
        has_code_blocks=True,
        has_headings=True,
    )
    assert result["quiz_count"] == 0


def test_boundary_topic_length_199():
    """199 chars with no code/headings = insufficient (below 200 threshold)."""
    from app.services.fallback import determine_mode

    result = determine_mode(
        grounding_level="low",
        topic_content_length=199,
        has_code_blocks=False,
        has_headings=False,
    )
    assert result["mode"] == "insufficient"


def test_boundary_topic_length_200():
    """Exactly 200 chars = enough content for topic_only."""
    from app.services.fallback import determine_mode

    result = determine_mode(
        grounding_level="low",
        topic_content_length=200,
        has_code_blocks=False,
        has_headings=False,
    )
    assert result["mode"] == "topic_only"


def test_return_dict_keys():
    from app.services.fallback import determine_mode

    result = determine_mode(
        grounding_level="high",
        topic_content_length=500,
        has_code_blocks=True,
        has_headings=True,
    )
    expected_keys = {"mode", "quiz_count", "flashcard_count", "quiz_allowed", "flashcard_allowed"}
    assert set(result.keys()) == expected_keys
