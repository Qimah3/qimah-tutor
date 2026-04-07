import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_strip_markdown_fences():
    from app.services.validator import sanitize_json

    raw = '```json\n{"type": "quiz"}\n```'
    assert sanitize_json(raw) == '{"type": "quiz"}'


def test_strip_triple_backticks_only():
    from app.services.validator import sanitize_json

    raw = '```\n{"type": "quiz"}\n```'
    assert sanitize_json(raw) == '{"type": "quiz"}'


def test_plain_json_unchanged():
    from app.services.validator import sanitize_json

    raw = '{"type": "quiz"}'
    assert sanitize_json(raw) == '{"type": "quiz"}'


def test_valid_quiz_passes_structural():
    from app.services.validator import validate_quiz_response

    quiz_json = {
        "type": "quiz",
        "mode": "grounded",
        "grounding_summary": "test",
        "title": "Test Quiz",
        "questions": [
            {
                "q": "What does indexOf return?",
                "question_type": "recall",
                "difficulty": "easy",
                "options": ["Position", "Boolean", "Char", "Length"],
                "correct": 0,
                "explanation": {
                    "why_correct": "Returns position of first occurrence in the string.",
                    "why_wrong": "Boolean is returned by contains method, not indexOf.",
                },
                "source": {
                    "source_file": "exam.pdf",
                    "source_page": 1,
                    "source_type": "old_exam",
                    "source_excerpt": "indexOf returns the position...",
                },
            }
        ],
    }
    errors = validate_quiz_response(quiz_json)
    assert errors == []


def test_duplicate_options_detected():
    from app.services.validator import validate_quiz_response

    quiz_json = {
        "type": "quiz",
        "mode": "grounded",
        "grounding_summary": "test",
        "title": "Test",
        "questions": [
            {
                "q": "Test question text here?",
                "question_type": "recall",
                "difficulty": "easy",
                "options": ["Same", "Same", "C", "D"],
                "correct": 0,
                "explanation": {"why_correct": "x" * 25, "why_wrong": "y" * 25},
                "source": {
                    "source_file": "f",
                    "source_page": 1,
                    "source_type": "old_exam",
                    "source_excerpt": "z" * 15,
                },
            }
        ],
    }
    errors = validate_quiz_response(quiz_json)
    assert any("duplicate" in e.lower() for e in errors)


def test_correct_out_of_bounds_detected():
    from app.services.validator import validate_quiz_response

    quiz_json = {
        "type": "quiz",
        "mode": "grounded",
        "grounding_summary": "test",
        "title": "Test",
        "questions": [
            {
                "q": "Test question text here?",
                "question_type": "recall",
                "difficulty": "easy",
                "options": ["A", "B", "C", "D"],
                "correct": 5,
                "explanation": {"why_correct": "x" * 25, "why_wrong": "y" * 25},
                "source": {
                    "source_file": "f",
                    "source_page": 1,
                    "source_type": "old_exam",
                    "source_excerpt": "z" * 15,
                },
            }
        ],
    }
    errors = validate_quiz_response(quiz_json)
    assert any("correct" in e.lower() for e in errors)


def test_valid_flashcard_passes_structural():
    from app.services.validator import validate_flashcard_response

    fc_json = {
        "type": "flashcard",
        "mode": "grounded",
        "grounding_summary": "test",
        "title": "Test",
        "cards": [
            {
                "card_type": "definition",
                "front": "What is a loop?",
                "back": "A control structure.",
                "source": {
                    "source_file": "f",
                    "source_page": 1,
                    "source_type": "old_exam",
                    "source_excerpt": "z" * 15,
                },
            },
            {
                "card_type": "contrast",
                "front": "for vs while?",
                "back": "for is count-based.",
                "source": {
                    "source_file": "f",
                    "source_page": 1,
                    "source_type": "old_exam",
                    "source_excerpt": "z" * 15,
                },
            },
            {
                "card_type": "mistake",
                "front": "Common mistake?",
                "back": "Off-by-one errors.",
                "source": {
                    "source_file": "f",
                    "source_page": 1,
                    "source_type": "old_exam",
                    "source_excerpt": "z" * 15,
                },
            },
        ],
    }
    errors = validate_flashcard_response(fc_json)
    assert errors == []


def test_flashcard_too_few_card_types():
    from app.services.validator import validate_flashcard_response

    fc_json = {
        "type": "flashcard",
        "mode": "grounded",
        "grounding_summary": "test",
        "title": "Test",
        "cards": [
            {
                "card_type": "definition",
                "front": "Q1",
                "back": "A1",
                "source": {
                    "source_file": "f",
                    "source_page": 1,
                    "source_type": "old_exam",
                    "source_excerpt": "z" * 15,
                },
            },
            {
                "card_type": "definition",
                "front": "Q2",
                "back": "A2",
                "source": {
                    "source_file": "f",
                    "source_page": 1,
                    "source_type": "old_exam",
                    "source_excerpt": "z" * 15,
                },
            },
        ],
    }
    errors = validate_flashcard_response(fc_json)
    assert any("card_type" in e.lower() or "type" in e.lower() for e in errors)


def test_source_excerpt_match_grounded_removes_question():
    from app.services.validator import run_semantic_checks

    data = {
        "type": "quiz",
        "mode": "grounded",
        "questions": [
            {
                "q": "What is X?",
                "source": {
                    "source_excerpt": "this text does not appear in any chunk at all"
                },
            }
        ],
    }
    chunks = [{"text": "completely different content here"}]
    result = run_semantic_checks(data, chunks)
    assert len(result["questions"]) == 0


def test_source_excerpt_match_concept_review_keeps_question():
    from app.services.validator import run_semantic_checks

    data = {
        "type": "quiz",
        "mode": "concept_review",
        "questions": [
            {
                "q": "What is X?",
                "source": {
                    "source_excerpt": "this text does not appear in any chunk at all"
                },
            }
        ],
    }
    chunks = [{"text": "completely different content here"}]
    result = run_semantic_checks(data, chunks)
    assert len(result["questions"]) == 1


def test_source_excerpt_match_found():
    from app.services.validator import run_semantic_checks

    data = {
        "type": "quiz",
        "mode": "grounded",
        "questions": [
            {
                "q": "What does indexOf return?",
                "source": {"source_excerpt": "indexOf returns the position"},
            }
        ],
    }
    chunks = [{"text": "indexOf returns the position of the first occurrence."}]
    result = run_semantic_checks(data, chunks)
    assert len(result["questions"]) == 1
