"""Prompt builder — assembles LLM messages for quiz and flashcard generation."""


def _format_chunks(chunks: list[dict]) -> str:
    """Format retrieved chunks into a numbered reference block."""
    if not chunks:
        return ""
    lines = []
    for i, chunk in enumerate(chunks, 1):
        lines.append(
            f"[Source {i}] {chunk['source_file']} (p.{chunk['page_number']}, "
            f"{chunk['source_type']}, score={chunk['score']})\n{chunk['text']}"
        )
    return "\n\n".join(lines)


def _format_context(context: dict) -> str:
    """Format topic context into a readable block."""
    parts = []
    if context.get("text"):
        parts.append(f"Topic Content:\n{context['text']}")
    if context.get("headings"):
        parts.append("Headings:\n" + "\n".join(f"- {h}" for h in context["headings"]))
    if context.get("code_blocks"):
        parts.append(
            "Code Blocks:\n"
            + "\n---\n".join(f"```\n{cb}\n```" for cb in context["code_blocks"])
        )
    return "\n\n".join(parts)


_QUIZ_SYSTEM = """\
You are an expert quiz generator for university courses. You produce high-quality \
multiple-choice questions in valid JSON.

RULES:
1. Return ONLY valid JSON matching this schema exactly — no markdown, no commentary:
{{
  "type": "quiz",
  "mode": "{mode}",
  "grounding_summary": "{grounding_summary}",
  "title": "<short descriptive title>",
  "questions": [
    {{
      "q": "<question text>",
      "question_type": "<recall|application|analysis|synthesis>",
      "difficulty": "<easy|medium|hard>",
      "options": ["<option A>", "<option B>", "<option C>", "<option D>"],
      "correct": <0-3>,
      "explanation": {{
        "why_correct": "<explain why the correct answer is right, 20+ chars>",
        "why_wrong": "<explain why the other options are wrong, 20+ chars>"
      }},
      "source": {{
        "source_file": "<filename from the provided sources>",
        "source_page": <page number>,
        "source_type": "<old_exam|lecture_note|handout|screenshot|lesson_content>",
        "source_excerpt": "<exact quote from source, 10+ chars>"
      }}
    }}
  ]
}}
2. Generate exactly {count} questions.
3. Use diverse question_type values — include recall, application, analysis, and synthesis.
4. All 4 options must be unique and plausible.
5. The "correct" field is the 0-based index of the correct option.
6. source_excerpt must be a real quote from the provided source chunks.
7. Language: {language}. All text (questions, options, explanations) must be in {language}.
8. Difficulty: {difficulty}. If "mixed", vary across easy/medium/hard.\
"""

_FLASHCARD_SYSTEM = """\
You are an expert flashcard generator for university courses. You produce high-quality \
flashcards in valid JSON.

RULES:
1. Return ONLY valid JSON matching this schema exactly — no markdown, no commentary:
{{
  "type": "flashcard",
  "mode": "{mode}",
  "grounding_summary": "{grounding_summary}",
  "title": "<short descriptive title>",
  "cards": [
    {{
      "card_type": "<definition|contrast|formula|code|mistake|trap>",
      "front": "<question or prompt>",
      "back": "<answer or explanation>",
      "source": {{
        "source_file": "<filename from the provided sources>",
        "source_page": <page number>,
        "source_type": "<old_exam|lecture_note|handout|screenshot|lesson_content>",
        "source_excerpt": "<exact quote from source, 10+ chars>"
      }}
    }}
  ]
}}
2. Generate exactly {count} flashcards.
3. Use at least 3 different card_type values across all cards.
4. card_type meanings:
   - definition: define a term or concept
   - contrast: compare two related concepts
   - formula: mathematical formula or equation
   - code: code snippet explanation
   - mistake: common mistake or misconception
   - trap: tricky exam question pattern
5. source_excerpt must be a real quote from the provided source chunks.
6. Language: {language}. All text (front, back) must be in {language}.
7. Difficulty: {difficulty}. If "mixed", vary complexity across cards.\
"""

_TOPIC_ONLY_NOTE = """
NOTE: No source documents were found for this topic. Generate flashcards based \
solely on the topic content provided below. For the "source" field in each card, use:
  "source_file": "lesson_content"
  "source_page": 0
  "source_type": "lesson_content"
  "source_excerpt": "<quote from the topic content below>"
"""


def build_quiz_prompt(
    context: dict,
    chunks: list[dict],
    mode: str,
    config: dict,
) -> list[dict]:
    """Build OpenAI-style messages for quiz generation.

    Args:
        context: Topic context dict (text, headings, code_blocks).
        chunks: Retrieved source chunks from RAG service.
        mode: Generation mode (grounded, concept_review).
        config: Generation config section (language, difficulty, quiz_count, etc.).

    Returns:
        List of message dicts with role and content keys.
    """
    count = config.get("quiz_count", 5)
    language = config.get("language", "arabic")
    difficulty = config.get("difficulty", "mixed")
    grounding_summary = f"Based on {len(chunks)} source chunks" if chunks else "No sources"

    system_content = _QUIZ_SYSTEM.format(
        mode=mode,
        grounding_summary=grounding_summary,
        count=count,
        language=language,
        difficulty=difficulty,
    )

    # Build user message
    user_parts = [_format_context(context)]

    if chunks and mode in ("grounded", "concept_review"):
        user_parts.append(f"Source Material:\n{_format_chunks(chunks)}")

    user_parts.append(f"Grounding: {grounding_summary}")
    user_parts.append(
        f"Generate {count} quiz questions at {difficulty} difficulty in {language}."
    )

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": "\n\n".join(user_parts)},
    ]


def build_flashcard_prompt(
    context: dict,
    chunks: list[dict],
    mode: str,
    config: dict,
) -> list[dict]:
    """Build OpenAI-style messages for flashcard generation.

    Args:
        context: Topic context dict (text, headings, code_blocks).
        chunks: Retrieved source chunks from RAG service.
        mode: Generation mode (grounded, concept_review, topic_only).
        config: Generation config section (language, difficulty, flashcard_count, etc.).

    Returns:
        List of message dicts with role and content keys.
    """
    count = config.get("flashcard_count", 10)
    language = config.get("language", "arabic")
    difficulty = config.get("difficulty", "mixed")
    grounding_summary = f"Based on {len(chunks)} source chunks" if chunks else "No sources"

    system_content = _FLASHCARD_SYSTEM.format(
        mode=mode,
        grounding_summary=grounding_summary,
        count=count,
        language=language,
        difficulty=difficulty,
    )

    if mode == "topic_only":
        system_content += _TOPIC_ONLY_NOTE

    # Build user message
    user_parts = [_format_context(context)]

    if chunks and mode in ("grounded", "concept_review"):
        user_parts.append(f"Source Material:\n{_format_chunks(chunks)}")

    user_parts.append(f"Grounding: {grounding_summary}")
    user_parts.append(
        f"Generate {count} flashcards at {difficulty} difficulty in {language}."
        " Use at least 3 different card_type values."
    )

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": "\n\n".join(user_parts)},
    ]
