# Qimah Tutor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an AI quiz & flashcard generator for LearnDash Focus Mode, backed by a Python microservice with Google Drive-indexed course materials.

**Architecture:** WordPress plugin injects buttons into Focus Mode topic pages. Clicks trigger a REST call that proxies (HMAC-signed) to a FastAPI microservice on a dedicated VPS. The microservice does hybrid RAG retrieval from ChromaDB (pre-indexed Drive PDFs/images/DOCX), generates typed quiz/flashcard JSON via LLM, validates output, and returns it. The frontend renders interactive widgets inline.

**Tech Stack:** PHP 7.4+ (WP plugin), Python 3.11+ (FastAPI, ChromaDB, PyMuPDF, Tesseract, openai SDK), vanilla JS (frontend widgets)

**Spec:** `docs/superpowers/specs/2026-03-20-qimah-tutor-design.md`

**Dev environment notes:**
- No local WordPress installation - WP plugin tested via FTP deploy to staging
- Microservice developed and tested locally (Windows), deployed to VPS
- Test Drive folder: `test drive/` in repo root (3 PDFs, 8 images, 1 DOCX)

**Pilot constraints (explicit):**
- **VPS: 4GB+ RAM recommended** (not 2GB). ChromaDB is memory-hungry, Tesseract spikes during OCR. Set up swap file immediately on provisioning to prevent OOM during 6h index cycles.
- Single-process uvicorn deployment (no horizontal scaling)
- In-memory cache and rate limits - wiped on process restart, which is acceptable
- WP is the primary rate limiter; microservice rate limiting is defense-in-depth
- Cache/rate loss on restart is tolerable for ~50 students
- Embedding model: ChromaDB default (`all-MiniLM-L6-v2`) everywhere for v1 - simpler, free, validated locally. Switching to OpenAI embeddings later requires full re-index.

**Testing tiers:**
- **Unit tests** (pytest): structural validation, config, auth, routing logic
- **Integration tests** (pytest + local ChromaDB): index -> retrieve -> prompt build -> validate pipeline using `test drive/` files
- **Manual acceptance tests** (staging): FTP deploy WP plugin, real CS101 topics in Focus Mode, end-to-end with live microservice

**Known risks:**
- WP integration failures only visible after FTP deploy (nonce, injection, timeout, JSON shape)
- Retrieval quality validated on CS101 test folder - other courses may vary
- Source classifier is naive (filename-based) - manual overrides in `courses.yaml` are the escape hatch
- Academic trust: students will assume content is exam-relevant. Grounding contract + fallback labeling mitigate but don't fully solve this

---

## Phase 1: Microservice Scaffold (local development)

### Task 1: Project skeleton + config loader

**Files:**
- Create: `qimah-tutor-api/app/__init__.py`
- Create: `qimah-tutor-api/app/main.py`
- Create: `qimah-tutor-api/app/config.py`
- Create: `qimah-tutor-api/config.yaml`
- Create: `qimah-tutor-api/courses.yaml`
- Create: `qimah-tutor-api/requirements.txt`
- Create: `qimah-tutor-api/tests/__init__.py`
- Create: `qimah-tutor-api/tests/test_config.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p qimah-tutor-api/app/routers qimah-tutor-api/app/services qimah-tutor-api/app/indexer qimah-tutor-api/app/models qimah-tutor-api/tests
touch qimah-tutor-api/app/__init__.py qimah-tutor-api/app/routers/__init__.py qimah-tutor-api/app/services/__init__.py qimah-tutor-api/app/indexer/__init__.py qimah-tutor-api/app/models/__init__.py qimah-tutor-api/tests/__init__.py
```

- [ ] **Step 2: Write requirements.txt**

```
fastapi>=0.115.0
uvicorn>=0.34.0
pyyaml>=6.0
pydantic>=2.0
pydantic-settings>=2.0
chromadb>=1.0
pymupdf>=1.25
pytesseract>=0.3
python-docx>=1.0
openai>=1.50
anthropic>=0.40
google-api-python-client>=2.150
google-auth>=2.35
httpx>=0.27
pytest>=8.0
pytest-asyncio>=0.24
```

- [ ] **Step 3: Write config.yaml with all spec defaults**

See spec Section 15 for full config. Include llm, embedding, rag, generation, security, indexer sections.

- [ ] **Step 4: Write courses.yaml with placeholder entries**

```yaml
courses:
  - course_id: 0
    drive_folder_id: "placeholder"
    name: "CS101 - Test"
```

- [ ] **Step 5: Write test for config loader**

```python
# tests/test_config.py
def test_load_config():
    from app.config import load_config
    cfg = load_config("config.yaml")
    assert cfg["llm"]["provider"] == "openai"
    assert cfg["rag"]["initial_candidates"] == 15
    assert cfg["security"]["hmac_timestamp_window_seconds"] == 60
```

- [ ] **Step 6: Run test, verify it fails**

```bash
cd qimah-tutor-api && python -m pytest tests/test_config.py -v
```

- [ ] **Step 7: Implement config.py**

```python
# app/config.py
import yaml
from pathlib import Path

_config = None

def load_config(path: str = None) -> dict:
    global _config
    if _config and not path:
        return _config
    config_path = Path(path) if path else Path(__file__).parent.parent / "config.yaml"
    with open(config_path) as f:
        _config = yaml.safe_load(f)
    return _config

def get_config() -> dict:
    if _config is None:
        return load_config()
    return _config
```

- [ ] **Step 8: Run test, verify it passes**

- [ ] **Step 9: Write main.py (minimal FastAPI app)**

```python
# app/main.py
from fastapi import FastAPI

app = FastAPI(title="Qimah Tutor API", version="1.0.0")

@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 10: Verify server starts**

```bash
cd qimah-tutor-api && python -m uvicorn app.main:app --port 8100
# Visit http://localhost:8100/health -> {"status": "ok"}
```

- [ ] **Step 11: Commit**

```bash
git add qimah-tutor-api/
git commit -m "feat(tutor-api): project scaffold with config loader and FastAPI health endpoint"
```

---

### Task 2: Pydantic models (request + quiz + flashcard schemas)

**Files:**
- Create: `qimah-tutor-api/app/models/request.py`
- Create: `qimah-tutor-api/app/models/quiz.py`
- Create: `qimah-tutor-api/app/models/flashcard.py`
- Create: `qimah-tutor-api/tests/test_models.py`

- [ ] **Step 1: Write test for quiz model validation**

```python
# tests/test_models.py
import pytest
from app.models.quiz import QuizResponse, QuizQuestion, QuestionSource, Explanation

def test_valid_quiz():
    q = QuizQuestion(
        q="What does indexOf() return?",
        question_type="recall",
        difficulty="easy",
        options=["Position", "Boolean", "Character", "Length"],
        correct=0,
        explanation=Explanation(
            why_correct="indexOf() returns the position of the first occurrence.",
            why_wrong="Boolean is returned by contains(), not indexOf()."
        ),
        source=QuestionSource(
            source_file="midterm.pdf", source_page=3,
            source_type="old_exam", source_excerpt="indexOf() returns..."
        )
    )
    quiz = QuizResponse(type="quiz", mode="grounded",
        grounding_summary="test", title="Test", questions=[q])
    assert quiz.questions[0].correct == 0

def test_correct_out_of_bounds():
    with pytest.raises(Exception):
        QuizQuestion(
            q="Test?", question_type="recall", difficulty="easy",
            options=["A", "B", "C", "D"], correct=5,
            explanation=Explanation(why_correct="x" * 25, why_wrong="y" * 25),
            source=QuestionSource(source_file="f", source_page=1,
                source_type="old_exam", source_excerpt="z" * 15)
        )

def test_duplicate_options():
    with pytest.raises(Exception):
        QuizQuestion(
            q="Test question here?", question_type="recall", difficulty="easy",
            options=["Same", "Same", "C", "D"], correct=0,
            explanation=Explanation(why_correct="x" * 25, why_wrong="y" * 25),
            source=QuestionSource(source_file="f", source_page=1,
                source_type="old_exam", source_excerpt="z" * 15)
        )
```

- [ ] **Step 2: Run test, verify fails**

- [ ] **Step 3: Implement all three model files**

`request.py`: `GenerateRequest` with type, count, difficulty, context (nested TopicContext with text, headings, code_blocks, has_video), user_id.

`quiz.py`: `QuestionSource`, `Explanation`, `QuizQuestion` (with validators: correct in bounds, 4 unique options, q length >10, explanation lengths >20), `QuizResponse`.

`flashcard.py`: `FlashcardSource`, `Flashcard` (with card_type enum: definition/contrast/formula/code/mistake/trap), `FlashcardResponse` (with validator: at least 3 different card types).

Use Pydantic v2 `model_validator` for cross-field checks. See spec Section 8 for exact schemas and Section 9.1 for validation rules.

- [ ] **Step 4: Run tests, verify pass**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(tutor-api): pydantic models with structural validators for quiz and flashcard schemas"
```

---

### Task 3: HMAC auth middleware

**Files:**
- Create: `qimah-tutor-api/app/auth.py`
- Create: `qimah-tutor-api/tests/test_auth.py`

- [ ] **Step 1: Write test for HMAC validation**

```python
# tests/test_auth.py
import hashlib, hmac, time, json, uuid

def _sign(body, secret, timestamp=None, nonce=None):
    ts = timestamp or str(int(time.time()))
    n = nonce or str(uuid.uuid4())
    body_hash = hashlib.sha256(body).hexdigest()
    sig = hmac.new(secret.encode(), (ts + n + body_hash).encode(), hashlib.sha256).hexdigest()
    return sig, ts, n

def test_valid_request():
    from app.auth import verify_request
    body = json.dumps({"type": "quiz"}).encode()
    sig, ts, nonce = _sign(body, "test-secret")
    assert verify_request(sig, ts, nonce, body, "test-secret") is True

def test_expired_timestamp():
    from app.auth import verify_request
    body = b'{"type":"quiz"}'
    sig, ts, nonce = _sign(body, "test-secret", timestamp=str(int(time.time()) - 120))
    assert verify_request(sig, ts, nonce, body, "test-secret", window=60) is False

def test_wrong_signature():
    from app.auth import verify_request
    assert verify_request("badsig", str(int(time.time())), "nonce1", b'{}', "secret") is False

def test_replay_rejected():
    from app.auth import verify_request, _seen_nonces
    _seen_nonces.clear()
    body = b'{"type":"quiz"}'
    sig, ts, nonce = _sign(body, "secret")
    assert verify_request(sig, ts, nonce, body, "secret") is True
    # Same nonce again = replay
    assert verify_request(sig, ts, nonce, body, "secret") is False

def test_malformed_timestamp():
    from app.auth import verify_request
    assert verify_request("sig", "not-a-number", "nonce", b'{}', "secret") is False
    assert verify_request("sig", "", "nonce", b'{}', "secret") is False
```

- [ ] **Step 2: Run test, verify fails**

- [ ] **Step 3: Implement auth.py**

Timestamp-bounded HMAC verification with nonce deduplication:

```python
# app/auth.py
import hashlib, hmac, time
from collections import OrderedDict

# Bounded nonce cache - prevents replay within the timestamp window
_seen_nonces = OrderedDict()
_MAX_NONCES = 10000

def verify_request(signature: str, timestamp: str, nonce: str, body: bytes, secret: str, window: int = 60) -> bool:
    # Validate timestamp
    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        return False
    if abs(time.time() - ts) > window:
        return False

    # Prune expired nonces first (older than window)
    cutoff = time.time() - window
    expired = [k for k, v in _seen_nonces.items() if v < cutoff]
    for k in expired:
        del _seen_nonces[k]

    # Reject replayed nonces
    if nonce in _seen_nonces:
        return False
    _seen_nonces[nonce] = ts
    # Cap size as safety net
    while len(_seen_nonces) > _MAX_NONCES:
        _seen_nonces.popitem(last=False)

    # Verify signature
    body_hash = hashlib.sha256(body).hexdigest()
    expected = hmac.new(secret.encode(), (timestamp + nonce + body_hash).encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)
```

**Note:** This is NOT labeled "replay protection" - it's timestamp-bounded HMAC with nonce deduplication. The nonce cache is in-memory, so replay protection resets on restart (acceptable for pilot - WP is the primary auth gate).

- [ ] **Step 4: Run tests, verify pass**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(tutor-api): timestamp-bounded HMAC auth with nonce deduplication"
```

---

### Task 4: LLM Router (provider-agnostic)

**Files:**
- Create: `qimah-tutor-api/app/services/llm_router.py`
- Create: `qimah-tutor-api/tests/test_llm_router.py`

- [ ] **Step 1: Write test for router factory**

```python
# tests/test_llm_router.py
def test_get_router_openai():
    from app.services.llm_router import get_router
    router = get_router({"provider": "openai", "model": "gpt-4o-mini"})
    assert router.__class__.__name__ == "OpenAIRouter"

def test_get_router_claude():
    from app.services.llm_router import get_router
    router = get_router({"provider": "claude", "model": "claude-sonnet-4-5-20250514"})
    assert router.__class__.__name__ == "ClaudeRouter"

def test_get_router_unknown():
    import pytest
    from app.services.llm_router import get_router
    with pytest.raises(ValueError):
        get_router({"provider": "gemini"})
```

- [ ] **Step 2: Run test, verify fails**

- [ ] **Step 3: Implement llm_router.py**

Abstract base class `LLMRouter` with `async complete(messages, **kwargs) -> str`. Two implementations: `OpenAIRouter` (openai SDK), `ClaudeRouter` (anthropic SDK). Factory function `get_router(config) -> LLMRouter`. Each reads API key from env var (`OPENAI_API_KEY` / `ANTHROPIC_API_KEY`). Include `temperature`, `max_tokens`, `timeout` from config.

- [ ] **Step 4: Run tests, verify pass**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(tutor-api): provider-agnostic LLM router with OpenAI and Claude implementations"
```

---

## Phase 2: Indexer Pipeline

### Task 5: Text extractors (PDF, OCR, DOCX)

**Files:**
- Create: `qimah-tutor-api/app/indexer/pdf_extractor.py`
- Create: `qimah-tutor-api/app/indexer/ocr_extractor.py`
- Create: `qimah-tutor-api/app/indexer/docx_extractor.py`
- Create: `qimah-tutor-api/tests/test_extractors.py`

- [ ] **Step 1: Write tests using real test files from `test drive/`**

```python
# tests/test_extractors.py
import os
TEST_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "test drive")

def test_pdf_text_extraction():
    from app.indexer.pdf_extractor import extract_pdf
    segments = extract_pdf(os.path.join(TEST_DIR, "Quiz.pdf"))
    assert len(segments) >= 4  # 4 pages
    assert "Prince Sultan University" in segments[0]["text"]
    assert segments[0]["method"] == "pymupdf"

def test_scanned_pdf_ocr_fallback():
    from app.indexer.pdf_extractor import extract_pdf
    segments = extract_pdf(os.path.join(TEST_DIR, "Major CS101 251.pdf"))
    assert len(segments) >= 6  # scanned pages with images
    assert any(s["method"] == "tesseract" for s in segments)

def test_image_ocr():
    from app.indexer.ocr_extractor import extract_image
    result = extract_image(os.path.join(TEST_DIR, "lab6.jpg"))
    assert result["chars"] > 500
    assert "Lab 6" in result["text"] or "lab 6" in result["text"].lower()

def test_docx_extraction():
    from app.indexer.docx_extractor import extract_docx
    result = extract_docx(os.path.join(TEST_DIR, "Quiz4_215110365.docx"))
    assert "sortedArray" in result["text"]
```

- [ ] **Step 2: Run tests, verify they fail**

- [ ] **Step 3: Implement pdf_extractor.py**

`extract_pdf(path) -> list[dict]`: Uses PyMuPDF. Per page: if `get_text()` returns >50 chars, store as pymupdf segment. Otherwise, extract embedded images and OCR each with Tesseract. Return list of `{text, page, method, ocr_confidence}`.

Scanned PDF threshold: configurable (default 50 chars). See spec Section 6.1.

- [ ] **Step 4: Implement ocr_extractor.py**

`extract_image(path) -> dict`: Uses pytesseract with `eng+ara`. Returns `{text, chars, confidence}`. Configure tesseract_cmd path from env var `TESSERACT_CMD` (default platform-dependent).

- [ ] **Step 5: Implement docx_extractor.py**

`extract_docx(path) -> dict`: Uses python-docx. Joins non-empty paragraph text. Returns `{text, chars}`.

- [ ] **Step 6: Run tests, verify pass**

- [ ] **Step 7: Commit**

```bash
git commit -m "feat(tutor-api): PDF, OCR, and DOCX text extractors with scanned PDF detection"
```

---

### Task 6: Source classifier + chunker

**Files:**
- Create: `qimah-tutor-api/app/indexer/classifier.py`
- Create: `qimah-tutor-api/app/indexer/chunker.py`
- Create: `qimah-tutor-api/tests/test_chunker.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_chunker.py
def test_classify_exam():
    from app.indexer.classifier import classify_source
    assert classify_source("Major CS101 251.pdf") == "old_exam"
    assert classify_source("Quiz4_answers.pdf") == "old_exam"
    assert classify_source("midterm-2024.pdf") == "old_exam"

def test_classify_lecture():
    from app.indexer.classifier import classify_source
    assert classify_source("lab6.jpg") == "lecture_note"
    assert classify_source("lecture-notes.pdf") == "lecture_note"

def test_classify_screenshot():
    from app.indexer.classifier import classify_source
    assert classify_source("WhatsApp Image 2025-10-11.jpg") == "screenshot"

def test_chunking_covers_all_content():
    from app.indexer.chunker import chunk_text
    text = "A" * 1200
    chunks = chunk_text(text, chunk_size=500, overlap=50)
    # All content should be represented - every char in at least one chunk
    assert len(chunks) >= 2  # must produce multiple chunks
    assert all(len(c) > 0 for c in chunks)
    assert all(len(c) <= 500 for c in chunks)  # no chunk exceeds size

def test_chunking_short_text_single_chunk():
    from app.indexer.chunker import chunk_text
    text = "short text"
    chunks = chunk_text(text, chunk_size=500, overlap=50)
    assert len(chunks) == 1
    assert chunks[0] == "short text"

def test_chunking_overlap_creates_continuity():
    from app.indexer.chunker import chunk_text
    # Use distinct words so we can check overlap
    text = " ".join(f"word{i}" for i in range(100))
    chunks = chunk_text(text, chunk_size=200, overlap=50)
    # Adjacent chunks should share some content (overlap)
    for i in range(len(chunks) - 1):
        tail = chunks[i][-50:]
        assert any(word in chunks[i+1] for word in tail.split() if word)
```

- [ ] **Step 2: Run tests, verify fail**

- [ ] **Step 3: Implement classifier.py**

`classify_source(filename, overrides=None) -> str`: Pattern matching on filename (case-insensitive). Returns `old_exam`, `lecture_note`, `handout`, or `screenshot`. WhatsApp pattern: starts with "WhatsApp". Supports `overrides` dict from `courses.yaml`. See spec Section 6.1 for patterns.

**Classifier limitations (explicit):** This is a best-guess heuristic. Screenshots can contain exam content, lab images can be assessments. The classifier output is used for retrieval weighting (old_exam gets 1.5x boost), NOT as ground truth. Manual per-course overrides in `courses.yaml` are the escape hatch. Do NOT treat classifier output as high-confidence - it's a soft signal for reranking, not a hard filter.

- [ ] **Step 4: Implement chunker.py**

`chunk_text(text, chunk_size=500, overlap=50) -> list[str]`: Sliding window chunker. Strips empty chunks. Returns list of text strings.

- [ ] **Step 5: Run tests, verify pass**

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(tutor-api): source type classifier and text chunker with overlap"
```

---

### Task 7: Index runner (orchestrator + ChromaDB storage)

**Files:**
- Create: `qimah-tutor-api/app/indexer/index_runner.py`
- Create: `qimah-tutor-api/tests/test_index_runner.py`

- [ ] **Step 1: Write test for local folder indexing (no Drive API)**

```python
# tests/test_index_runner.py
import os, tempfile
import chromadb

TEST_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "test drive")

def test_index_local_folder():
    from app.indexer.index_runner import index_local_folder
    client = chromadb.Client()
    collection = index_local_folder(TEST_DIR, "cs101_test", client)
    assert collection.count() > 30  # 63 chunks in our validation test
    # Verify metadata is stored
    result = collection.get(limit=1, include=["metadatas"])
    meta = result["metadatas"][0]
    assert "source_file" in meta
    assert "source_type" in meta
    assert "extraction_method" in meta
```

- [ ] **Step 2: Run test, verify fails**

- [ ] **Step 3: Implement index_runner.py**

`index_local_folder(folder_path, collection_name, client) -> Collection`: Orchestrates extraction. For each file in folder: route to extractor by extension (.pdf/.jpg/.jpeg/.png/.docx), classify source type, chunk text, generate UUID per chunk, store in ChromaDB with full metadata (source_file, page_number, source_type, extraction_method, text_length, ocr_confidence, indexed_at).

**Embedding note:** Use ChromaDB's default embedding function (`all-MiniLM-L6-v2`) for the pilot. It performed well in validation testing (8/8 queries correct). Switching to OpenAI `text-embedding-3-small` is a config change for later if quality needs improvement - but requires re-indexing all chunks when switching. The key constraint: **indexing and retrieval must use the same embedding model**. ChromaDB's default handles this automatically.

Also implement `index_from_drive(course_config, client)` stub that will use `drive_client.py` (Task 8).

- [ ] **Step 4: Run test, verify passes**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(tutor-api): index runner with ChromaDB storage and rich metadata per chunk"
```

---

### Task 8: Google Drive client

**Files:**
- Create: `qimah-tutor-api/app/indexer/drive_client.py`
- Create: `qimah-tutor-api/tests/test_drive_client.py`

- [ ] **Step 1: Write test (mocked - no real Drive API in CI)**

```python
# tests/test_drive_client.py
from unittest.mock import MagicMock, patch

def test_list_files():
    from app.indexer.drive_client import DriveClient
    mock_service = MagicMock()
    mock_service.files().list().execute.return_value = {
        "files": [
            {"id": "abc", "name": "midterm.pdf", "md5Checksum": "hash1"},
            {"id": "def", "name": "lab6.jpg", "md5Checksum": "hash2"},
        ]
    }
    client = DriveClient(service=mock_service)
    files = client.list_files("folder_id_123")
    assert len(files) == 2
    assert files[0]["name"] == "midterm.pdf"

def test_skip_unchanged_files():
    from app.indexer.drive_client import DriveClient
    client = DriveClient(service=MagicMock())
    existing_hashes = {"file_id_abc": "hash1"}  # keyed by Drive file ID
    files = [
        {"id": "file_id_abc", "name": "midterm.pdf", "md5Checksum": "hash1"},  # unchanged
        {"id": "file_id_def", "name": "quiz.pdf", "md5Checksum": "hash2"},     # new
    ]
    changed = client.filter_changed(files, existing_hashes)
    assert len(changed) == 1
    assert changed[0]["name"] == "quiz.pdf"
```

- [ ] **Step 2: Run tests, verify fail**

- [ ] **Step 3: Implement drive_client.py**

`DriveClient` class: wraps Google Drive API v3. Methods: `list_files(folder_id)` (list all PDFs/images/DOCX in folder, with id + md5), `filter_changed(files, existing_hashes)` (compare checksums **keyed by Drive file ID**, not filename - handles renames and duplicates safely), `download_file(file_id, dest_path)` (download to local temp). Authenticates via service account JSON (path from env var `GOOGLE_SERVICE_ACCOUNT_JSON`).

**Change detection key:** `{drive_file_id: md5_checksum}` stored in a local JSON file. Using file ID (not filename) because filenames can be duplicated across subfolders or renamed.

- [ ] **Step 4: Run tests, verify pass**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(tutor-api): Google Drive client with change detection via md5 hashes"
```

---

## Phase 3: RAG + Generation

### Task 9: RAG service (hybrid retrieval + reranking)

**Files:**
- Create: `qimah-tutor-api/app/services/rag_service.py`
- Create: `qimah-tutor-api/tests/test_rag_service.py`

- [ ] **Step 1: Write test for hybrid retrieval**

```python
# tests/test_rag_service.py
import os
import chromadb

TEST_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "test drive")

def _build_test_collection():
    from app.indexer.index_runner import index_local_folder
    client = chromadb.Client()
    return index_local_folder(TEST_DIR, "cs101_rag_test", client), client

def test_retrieve_relevant_chunks():
    from app.services.rag_service import retrieve
    collection, client = _build_test_collection()
    result = retrieve("What does indexOf() do in Java?", collection,
        config={"initial_candidates": 15, "final_top_k": 5,
                "ocr_confidence_min": 60, "ocr_text_length_min": 100,
                "weak_threshold": 1.3, "min_grounding_chunks": 3,
                "source_weights": {"old_exam": 1.5, "lecture_note": 1.2, "handout": 1.0, "screenshot": 0.8}})
    assert len(result["chunks"]) <= 5
    assert result["grounding_level"] in ("high", "medium", "low")
    assert "indexOf" in result["chunks"][0]["text"].lower() or "indexof" in result["chunks"][0]["text"].lower()

def test_weak_retrieval_detected():
    from app.services.rag_service import retrieve
    collection, client = _build_test_collection()
    result = retrieve("quantum entanglement in physics", collection,
        config={"initial_candidates": 15, "final_top_k": 5,
                "ocr_confidence_min": 60, "ocr_text_length_min": 100,
                "weak_threshold": 1.3, "min_grounding_chunks": 3,
                "source_weights": {"old_exam": 1.5, "lecture_note": 1.2, "handout": 1.0, "screenshot": 0.8}})
    # Totally unrelated query - should be weak
    assert result["grounding_level"] in ("low", "medium")
```

- [ ] **Step 2: Run tests, verify fail**

- [ ] **Step 3: Implement rag_service.py**

`retrieve(query, collection, config) -> dict`: Implements the 6-stage hybrid retrieval from spec Section 6.3:
1. Retrieve 15 candidates via ChromaDB vector search
2. Keyword boost (topic term overlap)
3. Quality filter (OCR confidence, text length)
4. Source type weighting (exam > lecture > screenshot)
5. Select top 5 by combined score
6. Assess grounding level (high/medium/low)

Returns `{chunks: [...], grounding_level: str, grounding_summary: str}`.

- [ ] **Step 4: Run tests, verify pass**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(tutor-api): hybrid RAG retrieval with reranking, quality filtering, and grounding assessment"
```

---

### Task 10: Prompt builder + fallback controller

**Files:**
- Create: `qimah-tutor-api/app/services/prompt_builder.py`
- Create: `qimah-tutor-api/app/services/fallback.py`
- Create: `qimah-tutor-api/tests/test_fallback.py`

- [ ] **Step 1: Write test for fallback decisions**

```python
# tests/test_fallback.py
def test_grounded_mode():
    from app.services.fallback import determine_mode
    result = determine_mode(grounding_level="high", topic_content_length=500,
                            has_code_blocks=True, has_headings=True)
    assert result["mode"] == "grounded"
    assert result["count"] == 5

def test_concept_review_mode():
    from app.services.fallback import determine_mode
    result = determine_mode(grounding_level="medium", topic_content_length=500,
                            has_code_blocks=True, has_headings=True)
    assert result["mode"] == "concept_review"
    assert result["count"] == 3  # fewer questions

def test_topic_only_mode():
    from app.services.fallback import determine_mode
    result = determine_mode(grounding_level="low", topic_content_length=500,
                            has_code_blocks=True, has_headings=True)
    assert result["mode"] == "topic_only"

def test_insufficient_material():
    from app.services.fallback import determine_mode
    result = determine_mode(grounding_level="low", topic_content_length=100,
                            has_code_blocks=False, has_headings=False)
    assert result["mode"] == "insufficient"
```

- [ ] **Step 2: Run tests, verify fail**

- [ ] **Step 3: Implement fallback.py**

`determine_mode(grounding_level, topic_content_length, has_code_blocks, has_headings) -> dict`: Implements spec Section 6.5 fallback hierarchy. Returns `{mode, count, quiz_allowed, flashcard_allowed}`.

- [ ] **Step 4: Implement prompt_builder.py**

`build_quiz_prompt(context, chunks, config) -> list[dict]`: Assembles system + user messages from spec Section 6.6 quiz template. Includes topic context, headings, code blocks, grounding level, language mode, schema.

`build_flashcard_prompt(context, chunks, config) -> list[dict]`: Same for flashcard template.

- [ ] **Step 5: Run tests, verify pass**

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(tutor-api): fallback controller and prompt builder with quiz/flashcard templates"
```

---

### Task 11: Output validator

**Files:**
- Create: `qimah-tutor-api/app/services/validator.py`
- Create: `qimah-tutor-api/tests/test_validator.py`

- [ ] **Step 1: Write test for JSON sanitization + structural validation**

```python
# tests/test_validator.py
import json

def test_strip_markdown_fences():
    from app.services.validator import sanitize_json
    raw = '```json\n{"type": "quiz"}\n```'
    assert sanitize_json(raw) == '{"type": "quiz"}'

def test_strip_triple_backticks_only():
    from app.services.validator import sanitize_json
    raw = '```\n{"type": "quiz"}\n```'
    assert sanitize_json(raw) == '{"type": "quiz"}'

def test_valid_quiz_passes_structural():
    from app.services.validator import validate_quiz_response
    quiz_json = {
        "type": "quiz", "mode": "grounded", "grounding_summary": "test",
        "title": "Test Quiz",
        "questions": [{
            "q": "What does indexOf return?",
            "question_type": "recall", "difficulty": "easy",
            "options": ["Position", "Boolean", "Char", "Length"],
            "correct": 0,
            "explanation": {"why_correct": "Returns position of first occurrence in the string.",
                          "why_wrong": "Boolean is returned by contains method, not indexOf."},
            "source": {"source_file": "exam.pdf", "source_page": 1,
                      "source_type": "old_exam", "source_excerpt": "indexOf returns the position..."}
        }]
    }
    errors = validate_quiz_response(quiz_json)
    assert len(errors) == 0

def test_duplicate_options_detected():
    from app.services.validator import validate_quiz_response
    quiz_json = {
        "type": "quiz", "mode": "grounded", "grounding_summary": "test",
        "title": "Test", "questions": [{
            "q": "Test question text here?",
            "question_type": "recall", "difficulty": "easy",
            "options": ["Same", "Same", "C", "D"], "correct": 0,
            "explanation": {"why_correct": "x" * 25, "why_wrong": "y" * 25},
            "source": {"source_file": "f", "source_page": 1,
                      "source_type": "old_exam", "source_excerpt": "z" * 15}
        }]
    }
    errors = validate_quiz_response(quiz_json)
    assert any("duplicate" in e.lower() for e in errors)
```

- [ ] **Step 2: Run tests, verify fail**

- [ ] **Step 3: Implement validator.py**

`sanitize_json(raw: str) -> str`: Strip markdown fences (```` ```json ... ``` ````, ```` ``` ... ``` ````).

`validate_quiz_response(data: dict) -> list[str]`: Run all structural checks from spec Section 9.1 (correct in bounds, unique options, 4 options, q length, explanation lengths, source fields). Returns list of error strings (empty = valid).

`validate_flashcard_response(data: dict) -> list[str]`: Same for flashcards (card type valid, at least 3 types in deck).

`run_semantic_checks(data: dict, chunks: list) -> list[str]`: Best-effort checks from spec Section 9.2. Returns warnings (logged, not blocking):
- **Source excerpt match**: `source_excerpt` must be an actual substring of one of the retrieved chunks (not just semantically similar - literal substring match after whitespace normalization). **BLOCKING in `grounded` mode** - if no match found, that question is removed from the response (not just warned). In `concept_review` or `topic_only` mode, log warning only.
- **Language consistency**: All questions should be in the same language mode.
- **Duplicate detection**: No two questions with >80% text overlap (use simple ratio).
- **Explanation grounding**: At least one technical term from `why_correct` should appear in the cited chunk text (catches fabricated explanations).

- [ ] **Step 4: Run tests, verify pass**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(tutor-api): output validator with structural checks and JSON sanitizer"
```

---

### Task 12: Quiz + flashcard generation services

**Files:**
- Create: `qimah-tutor-api/app/services/quiz_service.py`
- Create: `qimah-tutor-api/app/services/flashcard_service.py`
- Create: `qimah-tutor-api/tests/test_generation.py`

- [ ] **Step 1: Write tests with mocked LLM**

```python
# tests/test_generation.py
import pytest, json
from unittest.mock import AsyncMock, patch

VALID_QUIZ_JSON = json.dumps({
    "type": "quiz", "mode": "grounded", "grounding_summary": "test",
    "title": "Test", "questions": [{
        "q": "What does indexOf return?",
        "question_type": "recall", "difficulty": "easy",
        "options": ["Position", "Boolean", "Char", "Length"],
        "correct": 0,
        "explanation": {"why_correct": "Returns position of first occurrence in the string.",
                       "why_wrong": "Boolean is returned by contains method, not indexOf."},
        "source": {"source_file": "exam.pdf", "source_page": 1,
                   "source_type": "old_exam", "source_excerpt": "indexOf returns the position of..."}
    }]
})

@pytest.mark.asyncio
async def test_quiz_generation_success():
    from app.services.quiz_service import generate_quiz
    mock_router = AsyncMock()
    mock_router.complete.return_value = VALID_QUIZ_JSON
    context = {"course_name": "CS101", "topic_title": "Strings",
               "topic_content": {"text": "x" * 500, "headings": ["Strings"], "code_blocks": [], "has_video": False}}
    chunks = [{"text": "indexOf returns...", "metadata": {"source_file": "exam.pdf"}}]
    result = await generate_quiz(context, chunks, "high", {"generation": {"max_retries": 2}}, mock_router)
    assert result["type"] == "quiz"
    assert result["mode"] == "grounded"

@pytest.mark.asyncio
async def test_quiz_retries_on_bad_json():
    from app.services.quiz_service import generate_quiz
    mock_router = AsyncMock()
    mock_router.complete.side_effect = ["not valid json", VALID_QUIZ_JSON]
    context = {"course_name": "CS101", "topic_title": "Strings",
               "topic_content": {"text": "x" * 500, "headings": [], "code_blocks": [], "has_video": False}}
    result = await generate_quiz(context, [], "high", {"generation": {"max_retries": 2}}, mock_router)
    assert result["type"] == "quiz"
    assert mock_router.complete.call_count == 2  # retried once

@pytest.mark.asyncio
async def test_quiz_returns_error_after_exhausted_retries():
    from app.services.quiz_service import generate_quiz
    mock_router = AsyncMock()
    mock_router.complete.return_value = "always broken json"
    context = {"course_name": "CS101", "topic_title": "X",
               "topic_content": {"text": "x" * 500, "headings": [], "code_blocks": [], "has_video": False}}
    result = await generate_quiz(context, [], "high", {"generation": {"max_retries": 2}}, mock_router)
    assert result.get("error") is not None or result.get("mode") == "error"

@pytest.mark.asyncio
async def test_insufficient_mode_skips_llm():
    from app.services.quiz_service import generate_quiz
    mock_router = AsyncMock()
    context = {"course_name": "CS101", "topic_title": "X",
               "topic_content": {"text": "short", "headings": [], "code_blocks": [], "has_video": False}}
    result = await generate_quiz(context, [], "low", {"generation": {"max_retries": 2}}, mock_router)
    assert result["mode"] in ("insufficient", "error")
    mock_router.complete.assert_not_called()  # should not call LLM
```

- [ ] **Step 2: Run tests, verify fail**

- [ ] **Step 3: Implement quiz_service.py**

`async generate_quiz(context, chunks, grounding_level, config) -> dict`: Determines fallback mode, builds prompt, calls LLM, sanitizes JSON, validates, retries up to 2x on failure. Returns validated quiz dict or error dict.

- [ ] **Step 2: Implement flashcard_service.py**

`async generate_flashcards(context, chunks, grounding_level, config) -> dict`: Same flow for flashcards.

Both services follow the same pattern:
1. `fallback.determine_mode()` -> check if generation is allowed
2. `prompt_builder.build_*_prompt()` -> build messages
3. `llm_router.complete()` -> call LLM
4. `validator.sanitize_json()` -> strip fences
5. `json.loads()` -> parse
6. `validator.validate_*_response()` -> check structural validity
7. If errors: retry (max 2), then return error response
8. `validator.run_semantic_checks()` -> log warnings
9. Return validated response with mode and grounding metadata

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(tutor-api): quiz and flashcard generation services with retry and validation"
```

---

### Task 13: Generate endpoint (wires everything together)

**Files:**
- Create: `qimah-tutor-api/app/routers/generate.py`
- Modify: `qimah-tutor-api/app/main.py` (register router + auth middleware)

- [ ] **Step 1: Implement generate.py**

`POST /api/generate`: Receives `GenerateRequest`, loads course collection from ChromaDB, runs RAG retrieval, dispatches to quiz or flashcard service, returns response.

Security layers:
1. HMAC auth check via FastAPI dependency (call `verify_hmac()` from `auth.py`)
2. Per-user rate limiting: in-memory `dict[int, list[float]]` mapping user_id to list of request timestamps. On each request, prune timestamps older than 1 hour, reject if count >= `per_user_rate_limit` from config. This is defense-in-depth (WP also rate-limits). In-memory is fine - VPS restarts are rare, and WP is the primary gate.
3. Request body size: FastAPI middleware rejecting bodies > 10KB
4. Response timeout: 45s on the endpoint, 30s on the LLM call

Wire up auth middleware in `main.py` using FastAPI dependency injection. Add `max_body_size` middleware.

- [ ] **Step 2: Test manually with uvicorn**

```bash
cd qimah-tutor-api && python -m uvicorn app.main:app --port 8100
# Use curl or httpie to POST /api/generate with test payload + HMAC headers
```

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(tutor-api): /api/generate endpoint with auth, rate limiting, and full pipeline"
```

---

### Task 14: Caching layer + cost monitoring

**Files:**
- Create: `qimah-tutor-api/app/services/cache.py`
- Create: `qimah-tutor-api/app/services/cost_monitor.py`
- Create: `qimah-tutor-api/tests/test_cache.py`

- [ ] **Step 1: Write cache tests**

Test retrieval cache hit/miss (24h TTL), generation variant rotation (up to 3 variants, cycling through them), and course invalidation.

- [ ] **Step 2: Run tests, verify fail**

- [ ] **Step 3: Implement cache.py**

`TutorCache` class with in-memory dict storage:
- `get_retrieval(course_id, topic_id) -> dict or None`: Check TTL (24h default). Retrieval cache is topic-scoped because the query is always derived the same way from topic title + content. If query formulation changes in the future, add a query hash to the key.
- `set_retrieval(course_id, topic_id, chunks, grounding)`: Store with timestamp
- `get_generation(course_id, topic_id, gen_type, difficulty, count, language) -> dict or None`: Rotate through stored variants. Cache key includes ALL generation parameters to prevent serving wrong variant for a different request shape.
- `set_generation(course_id, topic_id, gen_type, difficulty, count, language, data)`: Add to variant pool (evict oldest if at max)
- `invalidate_course(course_id)`: Clear all caches for a course (called by indexer after re-index)

**Cache key design (explicit):**
- Retrieval: `(course_id, topic_id)` - query is deterministic from topic
- Generation: `(course_id, topic_id, gen_type, difficulty, count, language_mode)` - all params that affect output

In-memory is fine for pilot scale (~50 students). Switch to Redis if needed later.

- [ ] **Step 4: Implement cost_monitor.py**

`CostMonitor` class: tracks daily input/output tokens per model, estimates daily cost, logs warnings when daily cost exceeds $0.66 (= $20/30 days). Store price-per-token for gpt-4o-mini ($0.15/1M input, $0.60/1M output).

Features:
- `log_usage(input_tokens, output_tokens)`: increment daily counters, log cost estimate
- `log_cache_hit(gen_type)`: track cache hit rate (important for cost modeling)
- `get_daily_summary() -> dict`: returns today's tokens, estimated cost, cache hit rate, request count
- `is_budget_exceeded() -> bool`: returns True if daily cost > threshold
- Expose via `GET /api/stats` endpoint (requires `X-Tutor-Secret` header - same shared secret as generate endpoint) for monitoring
- When `is_budget_exceeded()` is True, generate endpoint returns cached results only (no new LLM calls). This is the emergency kill switch.

- [ ] **Step 5: Wire cache into generate endpoint**

Modify `app/routers/generate.py` to:
1. Check retrieval cache before querying ChromaDB
2. Check generation cache before calling LLM
3. Store results in both caches after successful generation
4. Wire `CostMonitor` to log tokens from LLM responses

- [ ] **Step 6: Run tests, verify pass**

- [ ] **Step 7: Commit**

```bash
git commit -m "feat(tutor-api): caching layer with variant rotation and cost monitoring"
```

---

## Phase 4: WordPress Plugin

### Task 15: WP plugin bootstrap + settings page

**Files:**
- Create: `qimah-tutor/qimah-tutor.php`
- Create: `qimah-tutor/includes/class-qimah-tutor-core.php`
- Create: `qimah-tutor/includes/class-qimah-tutor-settings.php`

- [ ] **Step 1: Create plugin directory**

```bash
mkdir -p qimah-tutor/includes qimah-tutor/assets/js qimah-tutor/assets/css qimah-tutor/languages
```

- [ ] **Step 2: Write qimah-tutor.php (plugin header + bootstrap)**

Plugin Name: Qimah Tutor. Version: 1.0.0. Requires: LearnDash 4.0+, PHP 7.4+. Define constants: `QIMAH_TUTOR_VERSION`, `QIMAH_TUTOR_PATH`, `QIMAH_TUTOR_URL`. Load core class on `plugins_loaded`.

- [ ] **Step 3: Write class-qimah-tutor-core.php**

`Qimah_Tutor_Core`: singleton. On init, load settings, inject, and REST classes. Enqueue JS/CSS only on `sfwd-topic` post type when Focus Mode is active (check `LearnDash_Settings_Section::get_section_setting('LearnDash_Settings_Theme_LD30', 'focus_mode_enabled')`).

- [ ] **Step 4: Write class-qimah-tutor-settings.php**

`Qimah_Tutor_Settings`: register settings page under `Settings > Qimah Tutor`. Fields per spec Section 15: enable toggle, microservice URL, shared secret (write-only - never echo value), rate limit, quiz/flashcard counts, difficulty, language mode, enabled courses. Use `register_setting()` + `add_settings_section()` + `add_settings_field()`.

- [ ] **Step 5: FTP deploy to staging, verify settings page renders**

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(tutor): WP plugin bootstrap with settings page"
```

---

### Task 16: Context extractor

**Files:**
- Create: `qimah-tutor/includes/class-qimah-tutor-context.php`

- [ ] **Step 1: Implement context extraction**

`Qimah_Tutor_Context::extract( $topic_id ) -> array`: Given a topic ID:
1. Get topic post object
2. Get parent lesson (chapter) and course via LD functions: `learndash_get_course_id()`, `learndash_get_lesson_id()`
3. Get course/lesson/topic titles
4. Extract rich content from topic post_content:
   - Strip shortcodes (`strip_shortcodes()`)
   - Extract `<code>` and `<pre>` blocks before stripping HTML (store separately)
   - Extract headings (`<h1>` through `<h4>`) before stripping
   - Strip remaining HTML (`wp_strip_all_tags()`)
   - Trim to 2000 chars
   - Detect video presence (check for video shortcodes or embeds)
5. Return structured array matching spec Section 5.6

- [ ] **Step 2: FTP deploy, test via `wp_die( print_r( Qimah_Tutor_Context::extract( $topic_id ), true ) )` on a real topic**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(tutor): rich topic context extractor with code blocks and headings"
```

---

### Task 17: REST endpoint + HMAC proxy

**Files:**
- Create: `qimah-tutor/includes/class-qimah-tutor-rest.php`

- [ ] **Step 1: Implement REST endpoint**

`Qimah_Tutor_Rest`: register `POST /qimah/v1/tutor/generate` via `rest_api_init`.

**WP REST auth (exact pattern):**
- `permission_callback`: return `is_user_logged_in()`. Nonce validation is handled automatically by WP REST when the client sends `X-WP-Nonce` header - WP sets `current_user` from the nonce. No manual `wp_verify_nonce()` call needed.
- Nonce source: `wp_localize_script()` passes `wp_create_nonce('wp_rest')` to JS. JS sends it as `X-WP-Nonce` header.
- Logged-out users: `permission_callback` returns false, WP returns 401 automatically.
- `get_current_user_id()` is safe inside the callback because WP already authenticated via the nonce.

Route callback:
1. `$user_id = get_current_user_id()` (already authenticated by permission_callback)
2. Verify enrollment (`sfwd_lms_has_access( $course_id, $user_id )`) - return `WP_Error` with 403 if not enrolled
3. Check rate limit (transient `qimah_tutor_rate_{user_id}`, increment, check against setting) - return `WP_Error` with 429 if exceeded. Note: site has Redis object cache, so transients are stored in Redis, not wp_options - no bloat risk.
4. Build context via `Qimah_Tutor_Context::extract( $topic_id )`
5. Build proxy body (add context, user_id, type, count, difficulty)
6. Generate nonce: `$nonce = wp_generate_uuid4()`
7. Sign: `$timestamp = time()` (UTC - matches Python's `time.time()`), `$body_hash = hash('sha256', $body_json)`, `$signature = hash_hmac('sha256', $timestamp . $nonce . $body_hash, $secret)`
8. cURL POST to microservice URL with headers `X-Tutor-Signature`, `X-Tutor-Timestamp`, `X-Tutor-Nonce`
9. Timeout: 45 seconds
10. Return JSON response to browser (pass through microservice response as-is)

Route args: `type` (quiz|flashcard), `count` (int), `difficulty` (easy|medium|hard), `course_id` (int), `lesson_id` (int), `topic_id` (int). All sanitized.

- [ ] **Step 2: FTP deploy, test with browser console**

```js
fetch('/wp-json/qimah/v1/tutor/generate', {
    method: 'POST',
    headers: {'X-WP-Nonce': qimahTutor.nonce, 'Content-Type': 'application/json'},
    body: JSON.stringify({type: 'quiz', count: 5, course_id: 123, topic_id: 456})
}).then(r => r.json()).then(console.log)
```

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(tutor): REST endpoint with enrollment check, rate limiting, and HMAC-signed proxy"
```

---

### Task 18: Focus Mode injection (buttons + widget container)

**Files:**
- Create: `qimah-tutor/includes/class-qimah-tutor-inject.php`

- [ ] **Step 1: Implement content injection**

`Qimah_Tutor_Inject`: hook `the_content` at priority 25. On `sfwd-topic` posts only:
1. Check plugin is enabled (`get_option('qimah_tutor_enabled')`)
2. Check user is enrolled (`sfwd_lms_has_access()`)
3. Check course is in enabled list
4. Append HTML: two buttons + empty widget container div with `id="qimah-tutor-widget"`
5. Buttons: `<button class="qimah-tutor-btn" data-type="quiz">اختبرني</button>` and `<button class="qimah-tutor-btn" data-type="flashcard">بطاقات تعلم</button>`

- [ ] **Step 2: FTP deploy, verify buttons appear below topic content in Focus Mode**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(tutor): Focus Mode button injection via the_content filter"
```

---

## Phase 5: Frontend Widgets

### Task 19: JavaScript - quiz widget

**Files:**
- Create: `qimah-tutor/assets/js/qimah-tutor.js`

- [ ] **Step 1: Implement quiz renderer**

Vanilla JS IIFE. On button click:
1. Disable both buttons, show spinner on clicked one
2. Fetch POST to REST endpoint with course/topic context from `wp_localize_script` data
3. On response, check `mode` field and render accordingly:

**Exact frontend behavior by mode:**

| Mode | UI behavior |
|------|-------------|
| `grounded` | Normal quiz card. Badge: "مبني على مصادر المادة". Full source attribution per question. |
| `concept_review` | Quiz card with reduced count (3 Qs). Yellow banner: "مراجعة مفاهيم - المصادر محدودة". Source attribution where available. |
| `topic_only` | If quiz was requested: show message first "ما لقينا مصادر كافية للاختبار، جرّب البطاقات" with flashcard button CTA (don't auto-switch). If flashcards were requested: render flashcards with info banner "بطاقات من محتوى الدرس فقط". No source attribution. |
| `insufficient` | No generation. Gray card: "لا يوجد محتوى كافٍ لهذا الدرس بعد". Retry button. |
| `error` | Red-tinted card: "حصل خطأ، حاول مرة ثانية". Retry button. Log error to console. |

4. Quiz card: question text with cognitive type label, 4 option buttons (2x2 grid), progress bar
5. On option click: highlight correct/wrong, show explanation (why_correct + why_wrong), show source attribution, show Next button
6. After last question: score card with percentage, "اختبار جديد" button
7. Re-enable buttons when quiz dismissed

**JS fallback injection:** If `document.querySelector('.qimah-tutor-btn')` is null after 2s but `.ld-focus-content` exists, inject buttons via JS. This is intentional dual-strategy: `the_content` is primary, JS is fallback for Focus Mode template variations.

- [ ] **Step 2: FTP deploy, test quiz flow end-to-end (will need microservice running)**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(tutor): quiz widget renderer with scoring, source attribution, and fallback states"
```

---

### Task 20: JavaScript - flashcard widget

**Files:**
- Modify: `qimah-tutor/assets/js/qimah-tutor.js`

- [ ] **Step 1: Add flashcard renderer to existing JS**

On flashcard button click (same fetch flow):
1. Render flashcard deck with CSS 3D flip transform
2. Type badge on each card (definition/contrast/formula/code/mistake/trap)
3. Front/back content with source attribution on back
4. Navigation arrows + counter ("3 / 10")
5. Shuffle button
6. Self-rating buttons after flip: "عرفتها" / "ما عرفتها" (client-side only, no persistence)

- [ ] **Step 2: FTP deploy, test flashcard flow**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(tutor): flashcard widget with flip animation, type badges, and self-rating"
```

---

### Task 21: CSS - widget styles + dark mode + RTL

**Files:**
- Create: `qimah-tutor/assets/css/qimah-tutor.css`

- [ ] **Step 1: Write styles**

- Buttons: Qimah green (`#1E6649`), hover (`#155039`), rounded, RTL-friendly
- Quiz card: clean card with shadow, question text (RTL), option grid (2x2), progress bar, score card
- Flashcard: 3D flip (`transform-style: preserve-3d`, `backface-visibility: hidden`), card shadow
- Type badges: small colored labels per card type
- Source attribution: small muted text, tooltip on hover for excerpt
- Dark mode: `[data-theme="dark"] .qimah-tutor-*` selectors
- Loading spinner
- Fallback/error states
- Mobile responsive (<768px: buttons stack, cards full-width)
- `direction: rtl` on text containers

- [ ] **Step 2: FTP deploy, verify light + dark mode**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(tutor): CSS with dark mode, RTL, responsive layout, and quiz/flashcard styles"
```

---

## Phase 6: VPS Deployment

### Task 22: VPS setup + systemd services

**Files:**
- Create: `qimah-tutor-api/systemd/qimah-tutor-api.service`
- Create: `qimah-tutor-api/systemd/qimah-tutor-indexer.timer`
- Create: `qimah-tutor-api/systemd/qimah-tutor-indexer.service`

- [ ] **Step 1: Provision VPS**

Pick a VPS with 4GB+ RAM (ChromaDB + Tesseract OCR need headroom). Install Python 3.11+, Tesseract with `eng+ara` language pack, Tailscale. Set up swap file immediately (`fallocate -l 2G /swapfile`). Connect to Tailscale network so WP can reach it.

- [ ] **Step 2: Deploy microservice**

```bash
# On VPS:
git clone <repo> /opt/qimah-tutor-api
cd /opt/qimah-tutor-api
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

- [ ] **Step 3: Configure environment**

Set env vars: `OPENAI_API_KEY`, `GOOGLE_SERVICE_ACCOUNT_JSON` path, `TUTOR_SHARED_SECRET`, `TESSERACT_CMD`.

- [ ] **Step 4: Write systemd service files**

`qimah-tutor-api.service`: ExecStart uvicorn on port 8100, restart on failure.
`qimah-tutor-indexer.service`: ExecStart python index runner.
`qimah-tutor-indexer.timer`: OnCalendar every 6 hours.

- [ ] **Step 5: Enable and start services**

```bash
sudo systemctl enable --now qimah-tutor-api.service
sudo systemctl enable --now qimah-tutor-indexer.timer
```

- [ ] **Step 6: Verify health endpoint from WP server**

```bash
# From WP server (or any Tailscale node):
curl http://<vps-tailscale-ip>:8100/health
```

- [ ] **Step 7: Commit systemd files**

```bash
git commit -m "feat(tutor-api): systemd service and timer for API and Drive indexer"
```

---

### Task 23: Initial index run + WP config

- [ ] **Step 1: Set up courses.yaml with real CS101/CS102 Drive folder IDs**

- [ ] **Step 2: Run initial index**

```bash
cd /opt/qimah-tutor-api && source venv/bin/activate
python -m app.indexer.index_runner
```

Verify chunk count and metadata quality.

- [ ] **Step 3: Configure WP settings**

In WP admin `Settings > Qimah Tutor`:
- Enable: On
- Microservice URL: `http://<vps-tailscale-ip>:8100`
- Shared Secret: generate and set (must match VPS env var)
- Enabled courses: CS101, CS102
- Language: Arabic

- [ ] **Step 4: End-to-end test**

Navigate to a CS101 topic in Focus Mode. Click "اختبرني". Verify:
- Quiz generates with source attribution
- Questions are relevant to the topic
- Fallback works on topics with no Drive materials
- Rate limiting: use browser console to send 21 sequential `fetch()` calls directly to `/wp-json/qimah/v1/tutor/generate` (bypass button disable). Verify 429 status on call 21. Check microservice logs for its own rate limit enforcement too.
- Dark mode styling works

- [ ] **Step 5: Commit any final config tweaks**

```bash
git commit -m "chore(tutor): initial deployment config and index run"
```
