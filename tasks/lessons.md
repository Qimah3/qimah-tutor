# Project Lessons

Patterns and mistakes to avoid repeating.

---

## L001 — Always review code after each task for silent bugs

**What happened:** Task 4 (LLM Router) passed all tests but had two production bugs:
1. `ClaudeRouter.complete()` was NOT passing `temperature` to the Anthropic API
2. Neither router guarded against empty API responses (`response.content[0]` would crash with IndexError)

**Why it matters:** Tests only cover structure and routing. They don't catch missing parameters or unguarded index access because no real API calls are made in tests.

**Rule:** After every task, read the implementation file and ask:
- Are there any unguarded index accesses? (`[0]`, `[1]`, etc.)
- Are all parameters being passed through correctly?
- Can any return value be None/empty?

---

## L002 — Off-by-one in length validators

**What happened:** Task 2 (Pydantic models) used `< N` for "length > N" checks, allowing exactly-N-length strings through when they should fail.

**Rule:** Spec says "length > N" → use `<= N` to reject. Spec says "length >= N" → use `< N` to reject.

---

## L003 — Lazy client init for SDK clients in tests

**What happened:** LLM SDK clients (OpenAI, Anthropic) raise at construction time if API key is missing. Initializing them in `__init__` would break every unit test.

**Rule:** For any class that wraps an external API client, use lazy init: `self._client = None` in `__init__`, create in a `_get_client()` method. This way routing/config tests work without real API keys.

---

## L004 — FlashcardSource validators must mirror QuestionSource validators

**What happened:** Task 2 added `source_excerpt` length validator to `QuestionSource` but forgot to add the same validator to `FlashcardSource`.

**Rule:** When two models share the same field with the same semantic meaning, apply the same validators to both. Check symmetry during implementation.

---

## L005 — Wrap external process calls in orchestrators with try/except

**What happened:** Task 7 (index runner) called `extract_image()` directly. `extract_image()` calls Tesseract via subprocess. When Tesseract is not installed, this crashes the entire indexing job with `TesseractNotFoundError` — skipping all remaining files.

**Rule:** In any orchestrator that loops over files/items, wrap each extraction call in `try/except Exception` and log + continue. One bad file should never abort the whole job. This applies to: OCR calls, Drive API downloads, PDF parsing — anything that touches the filesystem or an external process.

---

## L006 — Verify test fixture files exist before writing integration tests

**What happened:** Task 7 integration test referenced a `test drive/` folder that didn't exist in the repo (not in git, not gitignored — simply never committed). The test would have failed with a confusing `FileNotFoundError` instead of the expected `ImportError`.

**Rule:** Before writing an integration test that reads files from disk, verify those fixture files actually exist with `ls` or `find`. If they don't exist, create synthetic ones immediately (using the same libraries the extractor uses: PyMuPDF for PDFs, python-docx for DOCX, PIL for images) so the test failure is always for the right reason.
