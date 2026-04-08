import hashlib
import hmac
import json
import os
import sys
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

SECRET = "test-secret-key"

# --- Valid canned data that passes structural validation ---

VALID_QUIZ_JSON = {
    "type": "quiz",
    "mode": "grounded",
    "grounding_summary": "Based on 3 source chunks",
    "title": "Test Quiz",
    "questions": [
        {
            "q": "What does indexOf return when a match is found?",
            "question_type": "recall",
            "difficulty": "easy",
            "options": ["Position index", "Boolean true", "Character value", "Array length"],
            "correct": 0,
            "explanation": {
                "why_correct": "indexOf returns the zero-based position of the first occurrence.",
                "why_wrong": "The other options describe return types of different methods entirely.",
            },
            "source": {
                "source_file": "exam.pdf",
                "source_page": 1,
                "source_type": "old_exam",
                "source_excerpt": "indexOf returns the position of first occurrence",
            },
        }
    ],
}

VALID_FLASHCARD_JSON = {
    "type": "flashcard",
    "mode": "grounded",
    "grounding_summary": "Based on 3 source chunks",
    "title": "Test Flashcards",
    "cards": [
        {
            "card_type": "definition",
            "front": "What is a loop?",
            "back": "A control structure that repeats a block of code.",
            "source": {
                "source_file": "notes.pdf",
                "source_page": 2,
                "source_type": "lecture_note",
                "source_excerpt": "A loop is a control structure",
            },
        },
        {
            "card_type": "contrast",
            "front": "for vs while loop?",
            "back": "for is count-based, while is condition-based.",
            "source": {
                "source_file": "notes.pdf",
                "source_page": 3,
                "source_type": "lecture_note",
                "source_excerpt": "for loops iterate a known number of times",
            },
        },
        {
            "card_type": "mistake",
            "front": "Common loop mistake?",
            "back": "Off-by-one error in loop bounds.",
            "source": {
                "source_file": "notes.pdf",
                "source_page": 4,
                "source_type": "lecture_note",
                "source_excerpt": "off-by-one errors are the most common loop bug",
            },
        },
    ],
}

CANNED_RAG_RESULT = {
    "chunks": [
        {
            "text": "indexOf returns the position of first occurrence in the string. A loop is a control structure. for loops iterate a known number of times. off-by-one errors are the most common loop bug.",
            "source_file": "exam.pdf",
            "page_number": 1,
            "source_type": "old_exam",
            "score": 0.95,
        }
    ],
    "grounding_level": "high",
    "grounding_summary": "Based on 1 source document: exam.pdf",
}

LOW_RAG_RESULT = {
    "chunks": [],
    "grounding_level": "low",
    "grounding_summary": "No relevant source material found",
}


def _make_request_body(gen_type="quiz", count=5):
    return {
        "type": gen_type,
        "count": count,
        "difficulty": "mixed",
        "course_id": 1,
        "topic_id": 10,
        "user_id": 100,
        "context": {
            "text": "This is a long enough topic text for testing. " * 10,
            "headings": ["Introduction", "Chapter 1"],
            "code_blocks": [],
            "has_video": False,
        },
    }


def _sign_request(body_dict, secret=SECRET):
    body_bytes = json.dumps(body_dict).encode()
    ts = str(int(time.time()))
    nonce = str(uuid.uuid4())
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    sig = hmac.new(
        secret.encode(), (ts + nonce + body_hash).encode(), hashlib.sha256
    ).hexdigest()
    headers = {
        "X-Signature": sig,
        "X-Timestamp": ts,
        "X-Nonce": nonce,
        "Content-Type": "application/json",
    }
    return body_bytes, headers


def _patch_all(llm_return_json):
    """Return a stack of patches for chroma, RAG, LLM, and config."""
    mock_collection = MagicMock()
    mock_router = MagicMock()
    mock_router.complete = AsyncMock(return_value=json.dumps(llm_return_json))

    return (
        patch("app.routers.generate.get_collection", return_value=mock_collection),
        patch("app.routers.generate.retrieve", return_value=dict(CANNED_RAG_RESULT)),
        patch("app.routers.generate.get_router", return_value=mock_router),
        patch.dict(os.environ, {"HMAC_SECRET": SECRET}),
    )


# --- Tests ---


def test_generate_quiz_happy_path():
    body = _make_request_body("quiz", 1)
    body_bytes, headers = _sign_request(body)
    p1, p2, p3, p4 = _patch_all(VALID_QUIZ_JSON)
    with p1, p2, p3, p4:
        resp = client.post("/generate", content=body_bytes, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "questions" in data
    assert data["type"] == "quiz"


def test_generate_flashcard_happy_path():
    body = _make_request_body("flashcard", 3)
    body_bytes, headers = _sign_request(body)

    mock_collection = MagicMock()
    mock_router = MagicMock()
    mock_router.complete = AsyncMock(return_value=json.dumps(VALID_FLASHCARD_JSON))

    with (
        patch("app.routers.generate.get_collection", return_value=mock_collection),
        patch("app.routers.generate.retrieve", return_value=dict(CANNED_RAG_RESULT)),
        patch("app.routers.generate.get_router", return_value=mock_router),
        patch.dict(os.environ, {"HMAC_SECRET": SECRET}),
    ):
        resp = client.post("/generate", content=body_bytes, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "cards" in data
    assert data["type"] == "flashcard"


def test_generate_auth_failure():
    body = _make_request_body("quiz")
    body_bytes = json.dumps(body).encode()
    headers = {
        "X-Signature": "bad-signature",
        "X-Timestamp": str(int(time.time())),
        "X-Nonce": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }
    with patch.dict(os.environ, {"HMAC_SECRET": SECRET}):
        resp = client.post("/generate", content=body_bytes, headers=headers)
    assert resp.status_code == 401


def test_generate_insufficient_mode():
    body = _make_request_body("quiz", 5)
    # Short text + no headings + no code = insufficient when grounding is low
    body["context"]["text"] = "short"
    body["context"]["headings"] = []
    body["context"]["code_blocks"] = []
    body_bytes, headers = _sign_request(body)

    mock_collection = MagicMock()
    with (
        patch("app.routers.generate.get_collection", return_value=mock_collection),
        patch("app.routers.generate.retrieve", return_value=dict(LOW_RAG_RESULT)),
        patch.dict(os.environ, {"HMAC_SECRET": SECRET}),
    ):
        resp = client.post("/generate", content=body_bytes, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "insufficient"
    assert data["questions"] == []


def test_generate_llm_invalid_json():
    body = _make_request_body("quiz", 1)
    body_bytes, headers = _sign_request(body)

    mock_collection = MagicMock()
    mock_router = MagicMock()
    mock_router.complete = AsyncMock(return_value="this is not json at all")

    with (
        patch("app.routers.generate.get_collection", return_value=mock_collection),
        patch("app.routers.generate.retrieve", return_value=dict(CANNED_RAG_RESULT)),
        patch("app.routers.generate.get_router", return_value=mock_router),
        patch.dict(os.environ, {"HMAC_SECRET": SECRET}),
    ):
        resp = client.post("/generate", content=body_bytes, headers=headers)
    assert resp.status_code == 500


def test_generate_validation_errors():
    """LLM returns JSON but with wrong option count -> validation errors."""
    bad_quiz = {
        "type": "quiz",
        "mode": "grounded",
        "grounding_summary": "test",
        "title": "Bad Quiz",
        "questions": [
            {
                "q": "What does indexOf return when called?",
                "question_type": "recall",
                "difficulty": "easy",
                "options": ["A", "B"],  # only 2 options, need 4
                "correct": 0,
                "explanation": {
                    "why_correct": "Returns the position of the match.",
                    "why_wrong": "Other options are wrong for reasons.",
                },
                "source": {
                    "source_file": "exam.pdf",
                    "source_page": 1,
                    "source_type": "old_exam",
                    "source_excerpt": "z" * 15,
                },
            }
        ],
    }
    body = _make_request_body("quiz", 1)
    body_bytes, headers = _sign_request(body)

    mock_collection = MagicMock()
    mock_router = MagicMock()
    mock_router.complete = AsyncMock(return_value=json.dumps(bad_quiz))

    with (
        patch("app.routers.generate.get_collection", return_value=mock_collection),
        patch("app.routers.generate.retrieve", return_value=dict(CANNED_RAG_RESULT)),
        patch("app.routers.generate.get_router", return_value=mock_router),
        patch.dict(os.environ, {"HMAC_SECRET": SECRET}),
    ):
        resp = client.post("/generate", content=body_bytes, headers=headers)
    assert resp.status_code == 500
    data = resp.json()
    assert "validation_errors" in data["detail"]
