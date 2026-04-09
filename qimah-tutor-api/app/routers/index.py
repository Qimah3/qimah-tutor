"""Index trigger endpoint — pulls a Drive folder, extracts text, upserts chunks to ChromaDB."""

import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.auth import verify_request
from app.config import get_config
from app.indexer.chunker import chunk_text
from app.indexer.classifier import classify_source
from app.indexer.docx_extractor import extract_docx
from app.indexer.drive_client import DriveClient
from app.indexer.ocr_extractor import extract_image
from app.indexer.pdf_extractor import extract_pdf
from app.services.chroma import get_collection

logger = logging.getLogger(__name__)

router = APIRouter()


class IndexRequest(BaseModel):
    course_id: int
    topic_id: int
    drive_folder_id: str


_EXT_PDF = ".pdf"
_EXT_DOCX = ".docx"
_EXT_IMAGES = (".jpg", ".jpeg", ".png")


@router.post("/index")
async def index_course(request: Request):
    config = get_config()

    # --- 1. Auth (same pattern as /generate) ---
    signature = request.headers.get("X-Signature", "")
    timestamp = request.headers.get("X-Timestamp", "")
    nonce = request.headers.get("X-Nonce", "")
    raw_body = await request.body()

    hmac_secret = (
        os.environ.get("HMAC_SECRET")
        or config.get("security", {}).get("hmac_secret", "")
    )
    if not verify_request(signature, timestamp, nonce, raw_body, hmac_secret):
        raise HTTPException(status_code=401, detail="Authentication failed")

    # --- 2. Parse request ---
    body = IndexRequest.model_validate_json(raw_body)

    # --- 3. List Drive files (L005: wrap in try/except → 500) ---
    drive = DriveClient()
    try:
        files = drive.list_files(body.drive_folder_id)
    except Exception as exc:
        logger.error("Drive list_files failed for folder %s: %s", body.drive_folder_id, exc)
        raise HTTPException(status_code=500, detail="Failed to list Drive folder")

    # --- 4. Prepare collection + indexer config ---
    collection_name = f"course_{body.course_id}_topic_{body.topic_id}"
    collection = get_collection(body.course_id, body.topic_id)
    indexer_cfg = config.get("indexer", {})
    c_size = indexer_cfg.get("chunk_size", 500)
    c_overlap = indexer_cfg.get("overlap", 50)
    indexed_at = datetime.now(timezone.utc).isoformat()

    indexed = 0
    skipped = 0

    # --- 5–9. Download → extract → chunk → upsert (per file) ---
    with tempfile.TemporaryDirectory() as tmpdir:
        for file_info in files:
            file_id = file_info.get("id", "")       # L001: guard dict access
            filename = file_info.get("name", "")     # L001
            ext = os.path.splitext(filename)[1].lower()
            dest = os.path.join(tmpdir, f"{uuid.uuid4()}{ext}")

            # 5. Download (L005: per-item try/except, log + continue)
            try:
                ok = drive.download_file(file_id, dest)
                if not ok:
                    raise RuntimeError(f"download_file returned False for {filename}")
            except Exception as exc:
                logger.warning("Skipping %s: download failed — %s", filename, exc)
                skipped += 1
                continue

            # 6. Extract text by extension + 7. classify source type
            source_type = classify_source(filename)
            try:
                segments = _extract(dest, ext)
            except Exception as exc:
                logger.warning("Skipping %s: extraction failed — %s", filename, exc)
                skipped += 1
                continue

            # 8. Chunk + 9. Upsert
            documents = []
            metadatas = []
            ids = []

            for seg in segments:
                text = seg.get("text", "")           # L001
                if not text.strip():
                    continue
                for chunk in chunk_text(text, c_size, c_overlap):
                    if not chunk.strip():
                        continue
                    documents.append(chunk)
                    metadatas.append({
                        "source_file": filename,
                        "page_number": int(seg.get("page", 0)),
                        "source_type": source_type,
                        "extraction_method": seg.get("method", "unknown"),
                        "text_length": len(chunk),
                        "ocr_confidence": float(seg.get("ocr_confidence", 0.0)),
                        "indexed_at": indexed_at,
                    })
                    ids.append(str(uuid.uuid4()))

            if documents:
                collection.upsert(documents=documents, metadatas=metadatas, ids=ids)

            indexed += 1

    return {"indexed": indexed, "skipped": skipped, "collection": collection_name}


def _extract(path: str, ext: str) -> list[dict]:
    """Route to the correct extractor and normalise output to list[dict].

    Each dict has at least: text, page, method, ocr_confidence.
    """
    if ext == _EXT_PDF:
        return extract_pdf(path)

    if ext == _EXT_DOCX:
        result = extract_docx(path)
        return [{"text": result.get("text", ""), "page": 0, "method": "python-docx"}]

    if ext in _EXT_IMAGES:
        result = extract_image(path)
        return [{
            "text": result.get("text", ""),
            "page": 0,
            "method": "tesseract",
            "ocr_confidence": result.get("confidence", 0.0),
        }]

    raise ValueError(f"Unsupported extension: {ext}")
