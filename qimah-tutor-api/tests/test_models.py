import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models.quiz import QuizResponse, QuizQuestion, QuestionSource, Explanation
from app.models.flashcard import FlashcardResponse, Flashcard, FlashcardSource


def make_source(**kwargs):
    defaults = dict(source_file="midterm.pdf", source_page=3,
                    source_type="old_exam", source_excerpt="indexOf() returns the position")
    return QuestionSource(**{**defaults, **kwargs})


def make_explanation(**kwargs):
    defaults = dict(why_correct="indexOf() returns the position of the first occurrence.",
                    why_wrong="Boolean is returned by contains(), not indexOf().")
    return Explanation(**{**defaults, **kwargs})


def make_question(**kwargs):
    defaults = dict(
        q="What does indexOf() return?",
        question_type="recall",
        difficulty="easy",
        options=["Position", "Boolean", "Character", "Length"],
        correct=0,
        explanation=make_explanation(),
        source=make_source(),
    )
    return QuizQuestion(**{**defaults, **kwargs})


# ── Quiz tests ──────────────────────────────────────────────────────────────

def test_valid_quiz():
    q = make_question()
    quiz = QuizResponse(type="quiz", mode="grounded",
                        grounding_summary="test", title="Test", questions=[q])
    assert quiz.questions[0].correct == 0


def test_correct_out_of_bounds():
    with pytest.raises(Exception):
        make_question(correct=5)  # only 4 options (indices 0-3)


def test_correct_negative():
    with pytest.raises(Exception):
        make_question(correct=-1)


def test_duplicate_options():
    with pytest.raises(Exception):
        make_question(options=["Same", "Same", "C", "D"])


def test_question_too_short():
    with pytest.raises(Exception):
        make_question(q="Hi?")  # less than 10 chars


def test_explanation_why_correct_too_short():
    with pytest.raises(Exception):
        make_question(explanation=Explanation(why_correct="short", why_wrong="y" * 25))


def test_explanation_why_wrong_too_short():
    with pytest.raises(Exception):
        make_question(explanation=Explanation(why_correct="x" * 25, why_wrong="short"))


def test_source_excerpt_too_short():
    with pytest.raises(Exception):
        make_question(source=make_source(source_excerpt="tiny"))


def test_question_source_accepts_lesson_content():
    src = make_source(source_type="lesson_content")
    assert src.source_type == "lesson_content"


def test_must_have_exactly_4_options():
    with pytest.raises(Exception):
        make_question(options=["A", "B", "C"])  # only 3


# ── Flashcard tests ──────────────────────────────────────────────────────────

def make_flashcard(card_type="definition", front="What is a stack?",
                   back="A LIFO data structure", source_file="notes.pdf",
                   source_page=1, source_type="lecture_note",
                   source_excerpt="A stack is a LIFO data structure"):
    return Flashcard(
        card_type=card_type,
        front=front,
        back=back,
        source=FlashcardSource(
            source_file=source_file, source_page=source_page,
            source_type=source_type, source_excerpt=source_excerpt,
        )
    )


def test_valid_flashcard_response():
    cards = [
        make_flashcard(card_type="definition"),
        make_flashcard(card_type="contrast"),
        make_flashcard(card_type="formula"),
    ]
    resp = FlashcardResponse(type="flashcard", mode="grounded",
                              grounding_summary="test", title="Test", cards=cards)
    assert len(resp.cards) == 3


def test_flashcard_invalid_card_type():
    with pytest.raises(Exception):
        make_flashcard(card_type="invalid_type")


def test_flashcard_source_excerpt_too_short():
    with pytest.raises(Exception):
        make_flashcard(source_excerpt="tiny")  # 4 chars, must be > 10


def test_flashcard_source_accepts_lesson_content():
    card = make_flashcard(source_type="lesson_content")
    assert card.source.source_type == "lesson_content"


def test_flashcard_response_requires_3_distinct_types():
    """All same type → should fail validation"""
    cards = [
        make_flashcard(card_type="definition"),
        make_flashcard(card_type="definition"),
        make_flashcard(card_type="definition"),
    ]
    with pytest.raises(Exception):
        FlashcardResponse(type="flashcard", mode="grounded",
                          grounding_summary="test", title="Test", cards=cards)


# ── Request model tests ──────────────────────────────────────────────────────

def test_valid_generate_request():
    from app.models.request import GenerateRequest, TopicContext
    req = GenerateRequest(
        type="quiz",
        count=5,
        difficulty="easy",
        course_id=101,
        topic_id=42,
        user_id=7,
        context=TopicContext(
            text="Java strings are immutable objects.",
            headings=["Java Strings", "Common Methods"],
            code_blocks=["String s = \"hello\";"],
            has_video=False,
        )
    )
    assert req.type == "quiz"
    assert req.context.has_video is False


def test_generate_request_invalid_type():
    from app.models.request import GenerateRequest, TopicContext
    with pytest.raises(Exception):
        GenerateRequest(
            type="essay",  # invalid
            count=5, difficulty="easy", course_id=1, topic_id=1, user_id=1,
            context=TopicContext(text="x", headings=[], code_blocks=[], has_video=False)
        )
