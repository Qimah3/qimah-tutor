# Qimah Tutor - AI Quiz & Flashcard Generator for Focus Mode

> **Status:** Proposal (v2 - post review)
> **Date:** 2026-03-21
> **Scope:** New WordPress plugin (`qimah-tutor`) + Python microservice (`qimah-tutor-api`)

## 1. Problem

Students studying in LearnDash Focus Mode have no way to self-test on the material they're learning. Old exams and study materials exist in Google Drive but are disconnected from the learning flow. Students can't generate practice questions or flashcards on demand for the specific topic they're studying.

## 2. Solution

An AI-powered quiz and flashcard generator embedded in Focus Mode topic pages:

- **Knows where the student is** - current course, chapter (lesson), and topic
- **Has access to course materials** - old exams, handouts, PDFs from Google Drive, pre-indexed for fast retrieval
- **Generates quizzes** - interactive MCQ widgets grounded in actual course materials, with source attribution
- **Generates flashcards** - typed cards (definition, contrast, formula, code, mistake, trap) with balanced composition
- **Honest about confidence** - falls back gracefully when source material is insufficient

## 3. Requirements

| Requirement | Detail |
|-------------|--------|
| AI provider | Provider-agnostic (Claude, OpenAI, etc. swappable via config) |
| Processing | External Python microservice on dedicated VPS |
| Knowledge base | Pre-indexed Google Drive files (PDFs, images via Tesseract OCR, DOCX), folder-per-course structure |
| Context awareness | Current course ID, lesson ID, topic ID, topic title, cleaned content (up to 2000 chars) |
| Output types | MCQ quiz (typed questions, 4 options, explanation, source) + typed flashcards (6 subtypes) |
| Grounding | Every output must include source attribution; weak retrieval triggers fallback mode |
| Language | Three modes: Arabic, English, bilingual (Arabic explanation + English technical terms) |
| Access control | Free for all enrolled students, abuse guards (WP + microservice defense in depth) |
| No streaming | Single request-response (no SSE needed - generate full quiz/deck, return JSON) |

## 4. System Architecture

```
┌──────────────────────────────────────────────┐
│  BROWSER (Focus Mode)                        │
│                                              │
│  Topic content area                          │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │  [اختبرني]    [بطاقات تعلم]           │  │  <- Action buttons below content
│  └────────────────────────────────────────┘  │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │  Quiz / Flashcard widget renders here  │  │  <- Generated content appears inline
│  └───────────────────┬────────────────────┘  │
└──────────────────────┼───────────────────────┘
                       │ REST (JSON request/response)
                       v
┌──────────────────────────────────────────────┐
│  WORDPRESS (qimah.net)                       │
│                                              │
│  qimah-tutor plugin                          │
│  - Inject buttons + widget area (Focus Mode) │
│  - REST: /qimah/v1/tutor/generate            │
│  - Auth: nonce + enrollment check            │
│  - Context builder (rich topic extraction)   │
│  - Rate limiter (transients)                 │
│  - HMAC-signed proxy to microservice         │
└──────────────────┬───────────────────────────┘
                   │ Internal HTTP (Tailscale)
                   v
┌──────────────────────────────────────────────┐
│  DEDICATED VPS (qimah-tutor-api)            │
│                                              │
│  FastAPI application                         │
│  ├─ LLM Router (provider-agnostic)          │
│  ├─ RAG Pipeline (hybrid retrieval + rerank)│
│  ├─ Quiz Generator (typed questions)        │
│  ├─ Flashcard Generator (typed cards)       │
│  ├─ Output Validator (semantic + structural)│
│  ├─ Fallback Controller                     │
│  └─ Drive Indexer (cron)                    │
│                                              │
│  ChromaDB (vector store)                     │
│  - One collection per course                │
│  - Rich metadata per chunk                  │
└──────────────────────────────────────────────┘
```

### 4.1 Component Responsibilities

**WordPress Plugin (`qimah-tutor`)**

- Injects buttons + widget container into Focus Mode topic pages
- Builds rich context payload (see Section 5.6)
- REST endpoint `/wp-json/qimah/v1/tutor/generate` (POST, nonce-authenticated)
- Validates enrollment: student must be enrolled in the course
- Rate limiting: transient-based, configurable (default 20 generations/hour per user)
- Signs proxy requests with HMAC (shared secret + timestamp + body hash)
- JS frontend: button handlers, quiz widget renderer, flashcard widget renderer, loading/fallback states

**Python Microservice (`qimah-tutor-api`)**

- FastAPI app running behind Tailscale (no public endpoint)
- Validates HMAC signature + timestamp window on every request
- LLM Router: abstract class with `complete()` method, implementations for Claude and OpenAI
- RAG Pipeline: hybrid retrieval (vector + keyword), reranking, quality scoring
- Quiz/Flashcard Generator: typed output with grounding contract
- Output Validator: structural + semantic validation before returning
- Fallback Controller: graceful degradation when retrieval is weak
- Drive Indexer: scheduled job (systemd timer, every 6h) with quality metadata

### 4.2 Communication

| Link | Protocol | Auth | Notes |
|------|----------|------|-------|
| Browser to WP | HTTPS REST | WP nonce cookie | Standard WP auth |
| WP to VPS | HTTP over Tailscale | HMAC-SHA256 (secret + timestamp + body hash) | Replay-protected |
| VPS to LLM | HTTPS | API key (env var) | Provider SDK handles this |
| VPS to Google Drive | HTTPS | Service account JSON | Read-only access to course folders |

### 4.3 Infrastructure

- **VPS**: New dedicated cheap VPS (NOT the Hetzner FMS box - separate host). Connected to Tailscale for WP access. 2GB+ RAM.
- **Process manager**: systemd service for FastAPI, systemd timer for Drive indexer
- **Vector DB**: ChromaDB embedded (file-based, no separate server process)
- **Python**: 3.11+ with venv

## 5. UI Design

### 5.1 Layout

No side panel. Two action buttons injected below the topic content, and a widget area that renders generated content inline:

```
┌──────────────────────────────────────────────────────────┐
│ <- Back    Topic: Stacks & Queues         [dark] [bkmk]  │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  [Video player / topic content as usual]                 │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │       [اختبرني]              [بطاقات تعلم]         │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │                                                    │  │
│  │   Quiz / Flashcard / Fallback widget renders here  │  │
│  │                                                    │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### 5.2 Quiz Widget

Student clicks "اختبرني" -> loading spinner -> quiz card appears:

- **Header**: Quiz title + question counter (1/5)
- **Question**: Arabic/English text with cognitive type label (recall / tracing / application)
- **Options**: 4 buttons in a 2x2 grid
- **On answer**: selected option highlights green (correct) or red (wrong) + correct answer highlights green + explanation text fades in below (explains why correct is correct AND why one wrong option is wrong)
- **Next button**: appears after answering, advances to next question
- **Progress bar**: fills as questions are answered
- **Score card**: after last question - percentage, "اختبار جديد" (New Quiz) button
- **Source attribution**: small text per question "Source: {source_file}, p.{page}" with excerpt tooltip

### 5.3 Flashcard Widget

Student clicks "بطاقات تعلم" -> loading spinner -> flashcard deck appears:

- **Card**: styled card with front/back, click or tap to flip (CSS 3D transform)
- **Type badge**: small label showing card type (definition / contrast / formula / code / mistake / trap)
- **Front**: question, term, or concept
- **Back**: answer, definition, or explanation + source attribution
- **Navigation**: left/right arrows or swipe to move between cards
- **Counter**: "3 / 10" showing position in deck
- **Shuffle button**: randomize order
- **Self-rating**: after flipping, "عرفتها" / "ما عرفتها" buttons (client-side only)

### 5.4 States

| State | What the student sees |
|-------|----------------------|
| Idle | Two buttons below topic content |
| Loading | Spinner on the clicked button, other button disabled |
| Quiz active | Quiz card widget with questions |
| Flashcard active | Flashcard deck with flip cards |
| Fallback: concept review | "Not enough exam material for this topic. Here's a concept review instead." + simplified quiz from topic content only |
| Fallback: insufficient | "Not enough material found for this topic yet." + retry button |
| Error | Inline error message with retry button |
| Rate limited | "حاول بعد X دقائق" with countdown |
| Not enrolled | Buttons hidden (never shown to non-enrolled users) |

### 5.5 Asset Loading

- JS/CSS only enqueued on `sfwd-topic` post type when Focus Mode is active
- JS: single file `qimah-tutor.js` (vanilla JS, no framework - matches CEP pattern)
- CSS: single file `qimah-tutor.css`
- Localized data via `wp_localize_script()`: nonce, REST URL, course context, user locale
- **Injection strategy**: Primary: `the_content` filter at priority 25. Fallback: JS-based injection after detecting `.ld-focus-content` selector. This guards against Focus Mode template variations.

### 5.6 Context Payload (Rich Extraction)

Instead of first 500 chars, build a structured context:

```json
{
  "course_id": 12345,
  "course_name": "CS101",
  "lesson_id": 456,
  "lesson_title": "Chapter 6: Methods",
  "topic_id": 789,
  "topic_title": "Method Parameters",
  "topic_content": {
    "text": "cleaned visible content, up to 2000 chars",
    "headings": ["Parameters", "Return Types", "Method Overloading"],
    "code_blocks": ["public static int add(int a, int b) { return a + b; }"],
    "has_video": true
  }
}
```

**Extraction rules:**
- Strip HTML boilerplate, shortcodes, LD chrome
- Preserve code blocks separately (critical for CS courses)
- Extract headings for topic structure
- Up to 2000 chars of cleaned text (not 500)
- Flag if topic has video (future: transcript indexing)

## 6. RAG Pipeline

### 6.1 Indexing Flow (Drive Indexer)

```
Google Drive API
    |
    v
List files in course folder (PDFs, images, DOCX)
    |
    v
Check hash against stored hashes (skip unchanged)
    |
    v
Download new/changed files
    |
    v
Route by file type:
    PDF (text-based) -> PyMuPDF: extract text directly
    PDF (scanned)    -> PyMuPDF: extract embedded images -> Tesseract OCR
    Image (jpg/png)  -> Tesseract OCR (eng+ara)
    DOCX             -> python-docx: extract paragraphs
    |
    v
Chunking: ~500 tokens per chunk, 50 token overlap
    |
    v
Embed chunks (provider's embedding model)
    |
    v
Store in ChromaDB collection: course_{id}_chunks
    Metadata per chunk:
      source_file, page_number, file_type,
      source_type (old_exam | lecture_note | handout | screenshot),
      extraction_method (pymupdf | tesseract | python-docx),
      text_length, ocr_confidence (if applicable),
      indexed_at
```

**Extraction strategy (validated with real CS101 Drive content):**

| Source type | Method | Tested quality | Notes |
|-------------|--------|---------------|-------|
| Text-based PDFs (clean exports) | PyMuPDF | Perfect | Arabic + English headers, code, MCQs |
| Scanned PDFs (image-only pages) | PyMuPDF image extract -> Tesseract | Good | Code and MCQs readable, some Arabic UI noise |
| Moodle screenshots (mobile) | Tesseract `eng+ara` | Good | 500-650 chars, questions + options come through |
| Moodle screenshots (desktop) | Tesseract `eng+ara` | Good | 650+ chars, clean extraction |
| Photos of monitors | Tesseract `eng+ara` | Decent | Perspective/glare add noise but code still readable |
| Clean screenshots (practice Qs) | Tesseract `eng+ara` | Excellent | 1000+ chars, near-perfect |
| DOCX files | python-docx | Perfect | Full text with structure |

**Why Tesseract over Google Cloud Vision:**
- CS101/CS102 content is ~90% English (Java code, CS questions). Tesseract handles typed English/code well.
- Arabic content is mostly Moodle UI chrome (headers, nav) which is irrelevant for quiz generation.
- Zero ongoing cost - runs locally on VPS.

**Scanned PDF detection:** If PyMuPDF extracts <50 chars from a page but finds embedded images, treat as scanned.

**Source type classification:** Infer from filename patterns:
- `*major*`, `*midterm*`, `*final*`, `*quiz*`, `*exam*` -> `old_exam`
- `*lab*`, `*lecture*`, `*slide*`, `*note*` -> `lecture_note`
- `*handout*`, `*worksheet*` -> `handout`
- WhatsApp/phone photos -> `screenshot`
- Override via `courses.yaml` per-folder if needed

**OCR quality metadata:**
- Tesseract confidence score stored per chunk
- Text length stored (very short chunks = likely noisy)
- Low-quality chunks (confidence <60% OR text <100 chars from OCR) flagged in metadata

### 6.2 Course-to-Folder Mapping

A config file (`courses.yaml`) maps LearnDash course IDs to Google Drive folder IDs:

```yaml
courses:
  - course_id: 12345
    drive_folder_id: "1a2b3c4d5e..."
    name: "Data Structures"
    source_type_overrides:
      "exams/": "old_exam"
      "lectures/": "lecture_note"
  - course_id: 67890
    drive_folder_id: "6f7g8h9i0j..."
    name: "Operating Systems"
```

Maintained manually. When a new course launches, add a line.

### 6.3 Retrieval Strategy (Hybrid)

**Problem with naive top-5 cosine:** Bad OCR chunks can outrank good ones. Old exams and lecture notes shouldn't have equal weight. No keyword matching.

**Solution: Hybrid retrieval with reranking.**

```
Query (topic title + content keywords)
    |
    v
Stage 1: Retrieve 15 candidates from ChromaDB (vector similarity)
    |
    v
Stage 2: Keyword boost
    - Score bonus for chunks containing exact topic terms
    - Score bonus for code-related terms if topic has code blocks
    |
    v
Stage 3: Quality filter
    - Exclude chunks with ocr_confidence < 60%
    - Exclude chunks with text_length < 100 (from OCR sources)
    - Penalize screenshot source type (noisy)
    |
    v
Stage 4: Source type weighting
    - old_exam chunks get 1.5x relevance boost
    - lecture_note chunks get 1.2x boost
    - screenshot chunks get 0.8x penalty
    |
    v
Stage 5: Select top 5 by combined score
    |
    v
Stage 6: Assess retrieval quality
    - If best chunk distance > 1.3: weak retrieval -> trigger fallback
    - If fewer than 3 chunks pass quality filter: limited retrieval
    - Compute grounding_confidence: high (>3 good chunks), medium (1-3), low (0)
```

### 6.4 Grounding Contract

Every quiz question and flashcard MUST include:

```json
{
  "source_file": "midterm-2024.pdf",
  "source_page": 3,
  "source_type": "old_exam",
  "source_excerpt": "Which of the following statements about indexOf()...",
  "grounding_confidence": "high"
}
```

**Enforcement:**
- If retrieval quality is `low` (no good chunks found): DO NOT generate normal quiz. Trigger fallback.
- If retrieval quality is `medium` (1-3 chunks): generate with `grounding_confidence: "medium"` and warn student.
- If retrieval quality is `high` (3+ good chunks): generate normally.
- Post-generation validator checks that `source_excerpt` actually appears in the retrieved chunks.

### 6.5 Fallback Hierarchy

When generation can't be fully grounded:

```
1. Grounded quiz/flashcard (normal mode)
   - 3+ high-quality chunks found
   - Full source attribution

2. Concept review mode (partial grounding)
   - 1-2 chunks found OR chunks are low quality
   - Generate from current topic content + whatever chunks exist
   - Label as "concept review" not "exam practice"
   - Fewer questions (3 instead of 5)

3. Topic-only mode (no external grounding)
   - 0 relevant chunks found
   - Generate only from the topic's own content (headings, code blocks, text)
   - Label clearly: "Based on lesson content only - no exam materials available"
   - Flashcards only (no quiz - can't claim exam relevance)

4. Insufficient material
   - Topic content is also too sparse (<200 chars, no code blocks, no headings)
   - Return error: "Not enough material to generate reliable content for this topic"
   - Offer retry button
```

### 6.6 System Prompt Templates

**Quiz generation:**

```
You are a quiz generator for the Qimah learning platform.

Course: {course_name}
Current chapter: {lesson_title}
Current lesson: {topic_title}
Lesson content: {topic_content}
Topic headings: {headings}
Code blocks in lesson: {code_blocks}

Retrieval quality: {grounding_level} ({chunk_count} source chunks found)

GENERATION RULES:

1. Question types - generate a MIX of:
   - recall: definition or fact recall
   - understanding: explain why something works
   - tracing: "what is the output of this code?"
   - application: "which approach solves this problem?"
   - contrast: "what is the difference between X and Y?"

2. Difficulty: target {difficulty} level (easy/medium/hard)

3. Distractor rules:
   - All 4 options must be plausible
   - No joke options, no "all of the above", no "none of the above"
   - No duplicate options
   - Wrong options should reflect common student mistakes

4. Explanation rules:
   - Explain why the correct answer is correct
   - Explain why at least one wrong option is wrong
   - Reference source material when possible

5. Grounding rules:
   - Every question MUST be based on the provided source materials or lesson content
   - Include source_file, source_page, source_excerpt for each question
   - If a question comes from lesson content (not source chunks), set source_type to "lesson_content"
   - Do NOT fabricate questions that aren't supported by the materials

6. Language: {language_mode}
   - "arabic": Full Arabic, keep English technical terms (class, int, String, etc.)
   - "english": Full English
   - "bilingual": Arabic explanations with English technical terms preserved

Output format (strict JSON, no markdown wrapping):
{quiz_schema}

Available course materials:
{rag_chunks}
```

**Flashcard generation:**

```
You are a flashcard generator for the Qimah learning platform.

Course: {course_name}
Current chapter: {lesson_title}
Current lesson: {topic_title}
Lesson content: {topic_content}
Topic headings: {headings}
Code blocks in lesson: {code_blocks}

Retrieval quality: {grounding_level}

GENERATION RULES:

1. Card types - generate a BALANCED deck:
   - definition (~30%): "What is X?" / "X is..."
   - contrast (~20%): "Difference between X and Y"
   - formula (~20%): rules, syntax patterns, formulas
   - code (~20%): "What does this code do?" / "Write code that..."
   - mistake (~10%): "Common mistake: using == instead of .equals()"

2. Each card must include source attribution
3. Front should be a clear, specific question or prompt
4. Back should be concise but complete (2-4 sentences max)

Language: {language_mode}

Output format (strict JSON, no markdown wrapping):
{flashcard_schema}

Available course materials:
{rag_chunks}
```

## 7. Data Flow - Full Request Lifecycle

### 7.1 Quiz Generation

```
1. Student clicks "اختبرني" button
2. JS sends POST /wp-json/qimah/v1/tutor/generate
   Body: { type: "quiz", count: 5, difficulty: "medium", course_id, lesson_id, topic_id }
   Headers: X-WP-Nonce

3. WP plugin:
   a. Verify nonce + user logged in
   b. Verify user enrolled in course_id
   c. Check rate limit (transient: qimah_tutor_rate_{user_id})
   d. Build rich context payload (strip HTML, extract code blocks, headings)
   e. Sign request: HMAC-SHA256(secret, timestamp + SHA256(body))
   f. POST to microservice over Tailscale
      Headers: X-Tutor-Signature, X-Tutor-Timestamp, Content-Type: application/json
      Body: { type: "quiz", count: 5, difficulty: "medium", context: { ... }, user_id }
   g. Return JSON response to browser

4. Microservice:
   a. Validate HMAC signature + timestamp within 60s window
   b. Check per-user rate limit (from signed user_id in payload)
   c. Hybrid retrieval from ChromaDB (15 candidates -> filter -> rerank -> top 5)
   d. Assess retrieval quality -> determine grounding level
   e. If low grounding: check fallback hierarchy, may return concept-review or error
   f. Build prompt with quiz policy + RAG chunks + topic context
   g. LLM complete() call (timeout: 30s, max_tokens: 4096)
   h. Strip markdown fences if present
   i. Parse JSON, run output validators
   j. If validation fails: retry (max 2), then return error
   k. Return validated quiz JSON with grounding metadata

5. Browser:
   a. Receive response JSON
   b. Check response.mode: "grounded" | "concept_review" | "topic_only" | "error"
   c. Render appropriate widget with mode indicator
   d. Scoring is client-side only
```

### 7.2 Flashcard Generation

Same flow as quiz, but `type: "flashcard"` and returns typed card pairs with balanced composition.

## 8. Output Schemas

### 8.1 Quiz Schema

```json
{
  "type": "quiz",
  "mode": "grounded",
  "grounding_summary": "Based on 4 source documents including midterm-2024.pdf",
  "title": "Stacks & Queues",
  "questions": [
    {
      "q": "What is the output order in a Stack?",
      "question_type": "recall",
      "difficulty": "easy",
      "options": ["FIFO", "LIFO", "Random", "Priority"],
      "correct": 1,
      "explanation": {
        "why_correct": "Stack uses LIFO - Last In, First Out. The last element pushed is the first one popped.",
        "why_wrong": "FIFO is the order used by Queue, not Stack."
      },
      "source": {
        "source_file": "midterm-2024.pdf",
        "source_page": 3,
        "source_type": "old_exam",
        "source_excerpt": "Which of the following statements about Stack ordering..."
      }
    }
  ]
}
```

### 8.2 Flashcard Schema

```json
{
  "type": "flashcard",
  "mode": "grounded",
  "grounding_summary": "Based on 3 source documents",
  "title": "Stacks & Queues",
  "cards": [
    {
      "front": "What is a Stack?",
      "back": "A data structure that uses LIFO (Last In, First Out). The last element added is the first one removed.",
      "card_type": "definition",
      "source": {
        "source_file": "lecture-notes.pdf",
        "source_page": 12,
        "source_type": "lecture_note",
        "source_excerpt": "A Stack is a linear data structure..."
      }
    },
    {
      "front": "Common mistake: comparing Strings with ==",
      "back": "== compares references (memory addresses), not content. Use .equals() to compare String values. str1 == str2 returns false even if both contain \"Hello\" (unless from string pool).",
      "card_type": "mistake",
      "source": {
        "source_file": "midterm-2024.pdf",
        "source_page": 5,
        "source_type": "old_exam",
        "source_excerpt": "What will be the output: String str1 = new String(\"Hello\")..."
      }
    }
  ]
}
```

## 9. Output Validation

### 9.1 Structural Validators (run on every response)

| Check | Rule | On failure |
|-------|------|-----------|
| JSON parseable | Strip markdown fences, parse JSON | Retry (max 2) |
| Schema match | Pydantic model validation | Retry |
| `correct` in bounds | `0 <= correct < len(options)` | Retry |
| Options unique | No duplicate option text | Retry |
| Options count | Exactly 4 per question | Retry |
| Question non-empty | `len(q) > 10` | Retry |
| Explanation non-empty | Both `why_correct` and `why_wrong` present, each >20 chars | Retry |
| Source fields present | `source_file` and `source_excerpt` required | Retry |
| Card type valid | Must be one of: definition, contrast, formula, code, mistake, trap | Retry |
| Flashcard balance | Deck has at least 3 different card types | Retry |

### 9.2 Semantic Validators (best-effort, log violations)

| Check | Rule | On failure |
|-------|------|-----------|
| Source excerpt exists | `source_excerpt` text found in retrieved chunks | Log warning, don't block |
| Language consistency | All questions in same language mode | Log warning |
| No duplicate questions | No two questions with >80% text overlap | Remove duplicate, log |
| Explanation coherence | `why_correct` references the correct option | Log warning |

Semantic validators log but don't retry - they catch drift for monitoring. If violation rate exceeds 20% over a day, alert for prompt tuning.

## 10. Language Policy

### 10.1 Three Language Modes

| Mode | When | Behavior |
|------|------|----------|
| `arabic` | Site language is Arabic (default) | Full Arabic text. Keep established English CS terms: `class`, `int`, `String`, `void`, `while`, `for`, `if`, `return`, `boolean`, `indexOf()`, `compareTo()`, etc. |
| `english` | User toggled English or site is English | Full English |
| `bilingual` | Configurable per course | Arabic explanations wrapping English technical terms. Question text in Arabic, code in English. |

### 10.2 Rules

- CS terms stay in English regardless of mode - don't translate `Stack` to `مكدس` or `loop` to `حلقة`
- Code snippets always in English (Java/Python don't have Arabic syntax)
- If source material is English but mode is Arabic: question in Arabic, code/terms preserved
- Detect language from site locale passed in context payload, not from source content

## 11. WordPress Plugin Structure

```
qimah-tutor/
├── qimah-tutor.php                    # Plugin bootstrap, constants, version
├── includes/
│   ├── class-qimah-tutor-core.php     # Hook registration, asset loading
│   ├── class-qimah-tutor-inject.php   # Focus Mode injection (the_content + JS fallback)
│   ├── class-qimah-tutor-context.php  # Rich context extraction (strip HTML, code blocks, headings)
│   ├── class-qimah-tutor-rest.php     # REST endpoint + HMAC-signed proxy
│   └── class-qimah-tutor-settings.php # Admin settings page
├── assets/
│   ├── js/qimah-tutor.js             # Button handlers, quiz renderer, flashcard renderer, fallback UI
│   └── css/qimah-tutor.css           # Widget styles, RTL, dark mode support
└── languages/
    ├── qimah-tutor-ar.po
    └── qimah-tutor-ar.mo
```

### 11.1 Key Classes

**`Qimah_Tutor_Inject`** - Primary: hooks into `the_content` at priority 25. On `sfwd-topic` posts, appends action buttons and widget container. Fallback: if JS detects `.ld-focus-content` exists but buttons aren't in DOM (template bypassed `the_content`), injects via JS after `.ld-focus-content`.

**`Qimah_Tutor_Context`** - Given a topic ID, extracts rich context: strips HTML/shortcodes, preserves code blocks (`<code>`, `<pre>`), extracts headings, returns up to 2000 chars of cleaned content. Does NOT use `get_the_content()` raw - strips LD chrome and boilerplate.

**`Qimah_Tutor_Rest`** - Registers `POST /qimah/v1/tutor/generate`. Validates nonce, enrollment, rate limit. Signs request body with HMAC-SHA256 (shared secret + timestamp + SHA256(body)). cURL POST to microservice. Request body size cap: 10KB. Response timeout: 45s.

**`Qimah_Tutor_Settings`** - WP admin page under Settings. Fields: microservice URL, shared secret (write-only), rate limit, quiz/flashcard defaults, enable/disable toggle, enabled courses.

### 11.2 Dependencies

- Requires: LearnDash 4.0+ (Focus Mode), PHP 7.4+
- Optional: qimah-profile (for richer context if available)
- No dependency on CEP (standalone plugin, both inject into Focus Mode independently)

## 12. Microservice Structure

```
qimah-tutor-api/
├── app/
│   ├── main.py                  # FastAPI app, middleware, request size limits
│   ├── config.py                # Load config.yaml, env vars
│   ├── auth.py                  # HMAC validation, timestamp window, replay protection
│   ├── routers/
│   │   └── generate.py          # POST /api/generate (timeout: 30s)
│   ├── services/
│   │   ├── llm_router.py        # Abstract LLM interface + Claude/OpenAI implementations
│   │   ├── rag_service.py       # Hybrid retrieval, reranking, quality assessment
│   │   ├── quiz_service.py      # Quiz prompt building + typed question generation
│   │   ├── flashcard_service.py # Flashcard prompt building + typed card generation
│   │   ├── validator.py         # Structural + semantic output validation
│   │   ├── fallback.py          # Fallback hierarchy controller
│   │   └── prompt_builder.py    # System prompt assembly
│   ├── indexer/
│   │   ├── drive_client.py      # Google Drive API wrapper
│   │   ├── pdf_extractor.py     # PyMuPDF text extraction + scanned page detection
│   │   ├── ocr_extractor.py     # Tesseract OCR for images (eng+ara) + confidence scoring
│   │   ├── docx_extractor.py    # python-docx text extraction
│   │   ├── classifier.py        # Source type classification (exam/lecture/handout/screenshot)
│   │   ├── chunker.py           # Text chunking with overlap
│   │   └── index_runner.py      # Main indexing orchestrator
│   └── models/
│       ├── request.py           # Pydantic request models
│       ├── quiz.py              # Quiz JSON schema + validators
│       └── flashcard.py         # Flashcard JSON schema + validators
├── config.yaml                  # Provider, model, generation defaults
├── courses.yaml                 # Course ID <-> Drive folder mapping
├── requirements.txt
└── systemd/
    ├── qimah-tutor-api.service  # FastAPI service unit
    └── qimah-tutor-indexer.timer # Drive sync timer (every 6h)
```

### 12.1 LLM Router

```python
class LLMRouter(ABC):
    @abstractmethod
    async def complete(self, messages: list[dict], **kwargs) -> str: ...

class ClaudeRouter(LLMRouter):
    # Uses anthropic SDK, reads ANTHROPIC_API_KEY from env

class OpenAIRouter(LLMRouter):
    # Uses openai SDK, reads OPENAI_API_KEY from env

def get_router(config: dict) -> LLMRouter:
    # Factory based on config.yaml provider field
```

No `stream()` method needed - quiz/flashcard generation is a single complete() call.

### 12.2 Embedding Strategy

- Embedding model: same provider's embedding endpoint (e.g., `text-embedding-3-small` for OpenAI, or Voyage AI for Claude)
- Embedding dimension: 1536 (OpenAI) or 1024 (Voyage)
- Configurable in `config.yaml` independently of generation model
- ChromaDB handles storage and cosine similarity search natively

## 13. Security & Abuse Guards

### 13.1 WordPress Layer

| Guard | Implementation | Default |
|-------|---------------|---------|
| Rate limit | WP transient per user: `qimah_tutor_rate_{user_id}` | 20 generations/hour |
| Enrollment check | `sfwd_lms_has_access()` before generating | Required |
| Concurrent requests | JS disables buttons during generation | 1 concurrent |
| Request signing | HMAC-SHA256(secret, timestamp + SHA256(body)) | Always active |

### 13.2 Microservice Layer (Defense in Depth)

| Guard | Implementation | Default |
|-------|---------------|---------|
| HMAC validation | Verify signature matches secret + timestamp + body hash | Required |
| Timestamp window | Reject requests older than 60 seconds (replay protection) | 60s |
| Per-user rate limit | From signed `user_id` in payload, enforced server-side | 20/hour |
| Request body size | FastAPI middleware, reject >10KB | 10KB |
| Response timeout | LLM call timeout | 30s |
| Max token cap | `max_tokens` in LLM call | 4096 |
| Content validation | Structural + semantic validators on every output | Always active |
| JSON sanitizer | Strip markdown fences before parsing | Always active |
| Retry limit | Max 2 LLM retries if validation fails | 2 retries |

### 13.3 Cost Controls

| Control | Implementation |
|---------|---------------|
| Token counter | Log input/output tokens per request |
| Daily cost estimate | Sum tokens * price, log daily total |
| Budget alert | If daily estimate > $0.66 (=$20/30 days), log warning |
| Emergency kill | Config flag to disable generation (serve cached only) |

## 14. Caching Strategy

### 14.1 What to Cache

| Layer | What | TTL | Why |
|-------|------|-----|-----|
| Retrieval chunks | Top-5 chunks per (course_id, topic_id) | 24h | Same topic = same relevant materials. Saves embedding + search cost. |
| Generated output | Full quiz/flashcard JSON per (course_id, topic_id, type) | **2 hours** | Short window prevents repetition. Students who click twice quickly get cached result. |
| Variant rotation | Store up to 3 variants per topic, rotate on request | 24h per variant | Students see different quizzes on repeated clicks within a day. |

### 14.2 Cache Invalidation

- Drive indexer clears retrieval cache for affected courses when new files are indexed
- Admin can force-clear cache per course from settings page
- Variant pool regenerates naturally as old variants expire

### 14.3 Why Not Cache Generation Longer

Students quickly notice repeated quizzes. 2-hour TTL balances cost savings (back-to-back clicks) with freshness (come back later, get new questions). Variant rotation (up to 3 stored) provides further variety within the 24h window.

## 15. Admin Configuration

WordPress Settings page (`Settings > Qimah Tutor`):

| Setting | Type | Default |
|---------|------|---------|
| Enable Tutor | Toggle | Off |
| Microservice URL | Text | `http://<vps-tailscale-ip>:8100` |
| Shared Secret | Password (write-only) | - |
| Rate Limit (generations/hour) | Number | 20 |
| Default Quiz Size | Number | 5 |
| Default Flashcard Count | Number | 10 |
| Default Difficulty | Select (easy/medium/hard) | medium |
| Language Mode | Select (arabic/english/bilingual) | arabic |
| Enabled Courses | Multi-select | All |

Microservice config (`config.yaml`):

```yaml
llm:
  provider: openai          # claude | openai (start cheap)
  model: gpt-4o-mini        # ~$0.15/1M input, $0.60/1M output
  temperature: 0.4
  max_tokens: 4096
  timeout_seconds: 30

embedding:
  provider: openai
  model: text-embedding-3-small  # $0.02/1M tokens - negligible cost

rag:
  initial_candidates: 15    # retrieve 15, filter+rerank to top 5
  final_top_k: 5
  chunk_size: 500
  chunk_overlap: 50
  min_grounding_chunks: 3   # below this = partial grounding mode
  weak_threshold: 1.3       # best chunk distance above this = weak retrieval
  ocr_confidence_min: 60    # exclude chunks below this
  ocr_text_length_min: 100  # exclude short OCR chunks

  source_weights:
    old_exam: 1.5
    lecture_note: 1.2
    handout: 1.0
    screenshot: 0.8

generation:
  quiz_default_count: 5
  flashcard_default_count: 10
  max_retries: 2
  cache_retrieval_ttl_hours: 24
  cache_generation_ttl_hours: 2
  max_variants_per_topic: 3

security:
  hmac_timestamp_window_seconds: 60
  max_request_body_bytes: 10240
  per_user_rate_limit: 20   # per hour

indexer:
  interval_hours: 6
  pdf_max_pages: 200
  ocr_languages: "eng+ara"
  scanned_pdf_threshold: 50
```

## 16. Cost Model

### 16.1 Budget: $20/month

**Assumptions (pilot: CS101 + CS102, ~50 active students):**

| Parameter | Estimate |
|-----------|----------|
| Active students (pilot) | ~50 |
| Generations per student per day | ~2 |
| Daily generations | ~100 |
| Cache hit rate | ~30% (same topic revisits) |
| Net LLM calls per day | ~70 |
| Avg input tokens per call | ~2,000 (system prompt + RAG chunks + context) |
| Avg output tokens per call | ~1,500 (5-question quiz with explanations) |
| Daily input tokens | ~140K |
| Daily output tokens | ~105K |
| Monthly input tokens | ~4.2M |
| Monthly output tokens | ~3.15M |

**Monthly cost estimate (gpt-4o-mini):**

| Component | Calculation | Cost |
|-----------|------------|------|
| LLM input | 4.2M tokens * $0.15/1M | $0.63 |
| LLM output | 3.15M tokens * $0.60/1M | $1.89 |
| Embeddings (queries) | ~3K queries * ~500 tokens * $0.02/1M | $0.03 |
| Embeddings (indexing) | One-time, ~200 files * ~5 chunks * 500 tokens | <$0.01 |
| **Total** | | **~$2.55/mo** |

Well within $20 budget. Even at 5x the usage estimate, costs stay under $13/month. Headroom exists for upgrading to a better model if quality requires it.

### 16.2 Cost Monitoring

- Log input/output token count per request
- Daily summary: total tokens, total estimated cost, cache hit rate
- Alert if daily cost > $0.66 (monthly pace > $20)
- Emergency: config flag to serve cached results only (zero LLM cost)

## 17. Dark Mode Support

The widget must respect Qimah's existing dark mode system:

- Read `data-theme="dark"` attribute on `<html>` element
- Listen for `qimah:theme-changed` jQuery event (fired by CEP's dark mode toggle)
- Use CSS custom properties or `[data-theme="dark"] .qimah-tutor-*` selectors
- Colors should match Qimah palette: primary `#1E6649`, backgrounds from existing dark mode vars

## 18. Future Considerations (Out of Scope for v1)

- **Full chatbot** - conversational AI panel (the original spec - can be added as v2)
- **Persistent scores** - save quiz results to WP, track improvement over time
- **LearnDash quiz integration** - generate actual LD quizzes that appear in gradebook
- **Multimedia indexing** - index video transcripts from Bunny CDN, Google Slides
- **Instructor dashboard** - see quiz generation patterns, common confusion points, question quality metrics
- **Spaced repetition** - flashcard scheduling based on self-rating history
- **Difficulty selection by student** - easy/medium/hard toggle in UI (v1 uses admin default)
- **University OS integration** - connect with the separate PSU course advisor bot
- **Second-pass QA** - lightweight LLM call to verify answer correctness and grounding (cost vs quality tradeoff)

## 19. Pipeline Validation (Tested 2026-03-21)

Tested against real CS101 Drive content (3 PDFs, 8 images, 1 DOCX):

**Text Extraction:**
- PyMuPDF: perfect on text-based PDFs (4,035 chars, Arabic+English)
- Tesseract: good on scanned PDFs (extracted embedded images), screenshots, and photos
- python-docx: perfect on Word files
- Scanned PDF detection: <50 chars from PyMuPDF + embedded images = route to OCR

**RAG Retrieval (ChromaDB + all-MiniLM-L6-v2):**
- 12 files -> 27 segments -> 63 chunks -> embedded + stored in ChromaDB
- 8/8 test queries returned the correct chunk as #1 result
- Distance scores: 0.44 to 1.09 (all HIGH or MED relevance)
- Production will use `text-embedding-3-small` (better than test model)

**Remaining untested (low risk):**
- LLM structured JSON output - well-proven for gpt-4o-mini/Claude with schema guidance. Note: gpt-4o-mini occasionally wraps JSON in markdown fences - microservice must strip before parsing.

## 20. Resolved Questions

**Round 1:**
1. **Google Drive service account** - Yes, already exists. Reuse it.
2. **VPS** - New dedicated cheap VPS (not Hetzner FMS). Needs: 2GB+ RAM, Python 3.11+, Tailscale.
3. **Course folder mapping** - Manual maintenance via `courses.yaml`.
4. **LLM budget** - $20/month ceiling. gpt-4o-mini estimated at ~$2.55/mo for pilot. Large headroom.
5. **Launch scope** - Pilot with CS101 + CS102.

**Round 2:**
1. **Pilot courses** - CS101 and CS102.
2. **VPS provider** - No preference. Pick cheapest with 2GB+ RAM.
3. **OCR** - Tesseract sufficient. Google Cloud Vision dropped. DOCX support added.
