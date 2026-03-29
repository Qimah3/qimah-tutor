# Qimah Tutor

AI-powered quiz and flashcard generator embedded in LearnDash Focus Mode. Students click a button on any topic page and get practice questions or flashcards grounded in real course materials (old exams, handouts, PDFs).

## How It Works

```
Browser (Focus Mode)          WordPress (qimah.net)           VPS (Tailscale)
┌──────────────────┐      ┌──────────────────────┐      ┌──────────────────────┐
│ [اختبرني]        │─REST─│ qimah-tutor plugin   │─HMAC─│ qimah-tutor-api      │
│ [بطاقات تعلم]    │      │ - Auth + enrollment  │      │ - FastAPI + RAG      │
│                  │      │ - Rate limiting      │      │ - ChromaDB vectors   │
│ Quiz/Flashcard   │◄JSON─│ - HMAC proxy         │◄JSON─│ - LLM generation     │
│ widget renders   │      │                      │      │ - Output validation  │
└──────────────────┘      └──────────────────────┘      └──────────────────────┘
```

1. Student clicks **اختبرني** (Quiz Me) or **بطاقات تعلم** (Flashcards) on a topic page
2. WordPress plugin sends course context + topic content to the microservice (HMAC-signed, over Tailscale)
3. Microservice retrieves relevant chunks from pre-indexed course materials (hybrid vector + keyword search)
4. LLM generates typed questions/cards grounded in retrieved sources
5. Output is validated (structural + semantic) and returned as JSON
6. Frontend renders interactive quiz or flashcard widget inline

## Components

### WordPress Plugin (`qimah-tutor/`)

- Injects action buttons into Focus Mode topic pages
- REST endpoint: `POST /wp-json/qimah/v1/tutor/generate`
- Enrollment verification (student must own the course)
- Transient-based rate limiting (20 generations/hour per user)
- HMAC-SHA256 signed proxy to microservice
- Vanilla JS frontend (quiz renderer, flashcard renderer, loading/fallback states)

### Python Microservice (`qimah-tutor-api/`)

- **FastAPI** app behind Tailscale (no public endpoint)
- **RAG Pipeline**: hybrid retrieval (vector + BM25 keyword), reranking, quality scoring
- **LLM Router**: provider-agnostic (Claude / OpenAI swappable via config)
- **Quiz Generator**: typed MCQ questions (conceptual, applied, trap, code trace, compare) with source attribution
- **Flashcard Generator**: typed cards (definition, contrast, formula, code, mistake, trap) with balanced composition
- **Output Validator**: structural + semantic checks before returning
- **Fallback Controller**: graceful degradation when retrieval confidence is low
- **Drive Indexer**: scheduled job (systemd timer, every 6h) indexes Google Drive folders per course into ChromaDB

## Tech Stack

| Layer | Stack |
|-------|-------|
| WP Plugin | PHP 7.4+, vanilla JS |
| Microservice | Python 3.11+, FastAPI, uvicorn |
| Vector Store | ChromaDB (embedded, `all-MiniLM-L6-v2`) |
| Document Processing | PyMuPDF (PDF), Tesseract (OCR), python-docx |
| LLM | OpenAI / Anthropic SDK (configurable) |
| Infra | Dedicated VPS, Tailscale mesh, systemd |

## Knowledge Base

Course materials are pre-indexed from Google Drive:

- **One folder per course** (mapped in `courses.yaml`)
- **Supported formats**: PDF, images (JPG/PNG via Tesseract OCR), DOCX
- **Source classification**: old exams, handouts, slides, notes (filename-based + manual overrides)
- **Rich metadata per chunk**: course, source type, page number, chapter mapping, quality indicators

## Language Modes

- **Arabic** - full Arabic output
- **English** - full English output
- **Bilingual** - Arabic explanations with English technical terms (default for CS courses)

## Configuration

- `config.yaml` - LLM provider, RAG parameters, rate limits, security settings
- `courses.yaml` - course-to-Drive-folder mapping with chapter structure

## Design Docs

- **Spec**: `docs/superpowers/specs/2026-03-20-qimah-tutor-design.md` (in plugins repo)
- **Plan**: `docs/superpowers/plans/2026-03-21-qimah-tutor.md` (in plugins repo)

## Status

**Pre-development** - spec and implementation plan complete, not yet built.
