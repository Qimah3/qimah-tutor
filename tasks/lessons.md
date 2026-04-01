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
