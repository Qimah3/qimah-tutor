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

---

## L007 — Remove unused imports before committing

**What happened:** Task 8 (Drive client) initially had `import io` and `import json` left over from early drafting. The L001 post-implementation review caught them. No test failure — just dead code that would accumulate over time.

**Rule:** After implementing, scan imports for any that are unused. Remove them before committing. If your editor doesn't flag unused imports, do a quick mental check: for each import, search the file for its usage.

---

## L008 — Normalise heterogeneous extractor returns behind a helper

**What happened:** Task 13 (index endpoint) needed to call three extractors with different return shapes: `extract_pdf` returns `list[dict]`, `extract_docx` returns `dict`, `extract_image` returns `dict`. Inlining the routing + normalisation in the endpoint handler would have made the loop body ~40 lines of branching.

**Why it matters:** When you mix extraction routing with HTTP/auth/chunking/upsert logic, the endpoint becomes hard to read and easy to break when adding a new file type.

**Rule:** When multiple functions return structurally different results that feed into the same downstream pipeline, create a thin `_extract(path, ext) -> list[dict]` helper that normalises them. Keep the main loop clean: download → extract → chunk → upsert. Each step is one line.

---

## L009 — download_file returning False vs raising: handle both

**What happened:** Task 13's `DriveClient.download_file()` catches exceptions internally and returns `False` (never raises). But the endpoint's per-item error handling uses `try/except`. If you only check the exception path, a silent `False` return would be treated as success.

**Why it matters:** External client methods that swallow exceptions and return a status bool are a common pattern. If the caller only has try/except, the "soft failure" case silently proceeds with a missing/empty file.

**Rule:** When calling a method that can fail both by raising *and* by returning a falsy status, check both: wrap in try/except AND check the return value. Pattern: `ok = client.do_thing(); if not ok: raise RuntimeError("...")` inside the try block.
