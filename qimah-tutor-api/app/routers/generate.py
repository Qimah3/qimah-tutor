"""MVP Generate endpoint — wires all services into POST /generate."""

import json
import logging
import os

from fastapi import APIRouter, HTTPException, Request

from app.auth import verify_request
from app.config import get_config
from app.models.flashcard import FlashcardResponse
from app.models.quiz import QuizResponse
from app.models.request import GenerateRequest
from app.services.chroma import get_collection
from app.services.fallback import determine_mode
from app.services.llm_router import get_router
from app.services.prompt_builder import build_flashcard_prompt, build_quiz_prompt
from app.services.rag_service import retrieve
from app.services.validator import (
    run_semantic_checks,
    sanitize_json,
    validate_flashcard_response,
    validate_quiz_response,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _insufficient_response(gen_type: str, summary: str) -> dict:
    if gen_type == "quiz":
        return {
            "type": "quiz",
            "mode": "insufficient",
            "grounding_summary": summary,
            "title": "Insufficient material",
            "questions": [],
        }
    return {
        "type": "flashcard",
        "mode": "insufficient",
        "grounding_summary": summary,
        "title": "Insufficient material",
        "cards": [],
    }


@router.post("/generate")
async def generate(request: Request):
    config = get_config()

    # 1. Read HMAC headers and raw body
    signature = request.headers.get("X-Signature", "")
    timestamp = request.headers.get("X-Timestamp", "")
    nonce = request.headers.get("X-Nonce", "")
    raw_body = await request.body()

    # 2. Verify auth
    hmac_secret = os.environ.get("HMAC_SECRET") or config.get("security", {}).get("hmac_secret", "")
    if not verify_request(signature, timestamp, nonce, raw_body, hmac_secret):
        raise HTTPException(status_code=401, detail="Authentication failed")

    # 3. Parse body
    body = GenerateRequest.model_validate_json(raw_body)

    # 4. Get collection
    collection = get_collection(body.course_id, body.topic_id)

    # 5. RAG retrieve
    rag_result = retrieve(
        query=body.context.text[:500],
        collection=collection,
        config=config["rag"],
    )

    # 6. Determine mode
    mode_result = determine_mode(
        grounding_level=rag_result["grounding_level"],
        topic_content_length=len(body.context.text),
        has_code_blocks=bool(body.context.code_blocks),
        has_headings=bool(body.context.headings),
    )

    # 7. Guard: insufficient or type not allowed
    type_allowed_key = "quiz_allowed" if body.type == "quiz" else "flashcard_allowed"
    if mode_result["mode"] == "insufficient" or not mode_result[type_allowed_key]:
        return _insufficient_response(body.type, rag_result["grounding_summary"])

    # 8. Build prompt
    gen_config = dict(config["generation"])
    count_key = "quiz_count" if body.type == "quiz" else "flashcard_count"
    gen_config[count_key] = min(body.count, mode_result[count_key])
    gen_config["difficulty"] = body.difficulty

    chunks = rag_result["chunks"]
    mode = mode_result["mode"]

    if body.type == "quiz":
        messages = build_quiz_prompt(body.context.model_dump(), chunks, mode, gen_config)
    else:
        messages = build_flashcard_prompt(body.context.model_dump(), chunks, mode, gen_config)

    # 9. LLM call (L005: wrap in try/except)
    try:
        raw = await get_router(config["llm"]).complete(messages)
    except Exception as exc:
        logger.error("LLM generation failed: %s", exc)
        raise HTTPException(status_code=500, detail="LLM generation failed")

    # 10. Sanitize + parse JSON
    cleaned = sanitize_json(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="LLM returned invalid JSON")

    # 11. Structural validation
    if body.type == "quiz":
        errors = validate_quiz_response(data)
    else:
        errors = validate_flashcard_response(data)

    if errors:
        raise HTTPException(status_code=500, detail={"validation_errors": errors})

    # 12. Semantic checks
    data = run_semantic_checks(data, chunks)

    # 13. Return validated response
    if body.type == "quiz":
        return QuizResponse.model_validate(data).model_dump()
    return FlashcardResponse.model_validate(data).model_dump()
