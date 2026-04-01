from typing import Literal
from pydantic import BaseModel, model_validator


class QuestionSource(BaseModel):
    source_file: str
    source_page: int
    source_type: Literal["old_exam", "lecture_note", "handout", "screenshot"]
    source_excerpt: str

    @model_validator(mode="after")
    def validate_excerpt_length(self):
        if len(self.source_excerpt) <= 10:
            raise ValueError("source_excerpt must be more than 10 characters")
        return self


class Explanation(BaseModel):
    why_correct: str
    why_wrong: str

    @model_validator(mode="after")
    def validate_lengths(self):
        if len(self.why_correct) <= 20:
            raise ValueError("why_correct must be more than 20 characters")
        if len(self.why_wrong) <= 20:
            raise ValueError("why_wrong must be more than 20 characters")
        return self


class QuizQuestion(BaseModel):
    q: str
    question_type: Literal["recall", "application", "analysis", "synthesis"]
    difficulty: Literal["easy", "medium", "hard"]
    options: list[str]
    correct: int
    explanation: Explanation
    source: QuestionSource

    @model_validator(mode="after")
    def validate_question(self):
        if len(self.q) <= 10:
            raise ValueError("q must be at least 10 characters")
        if len(self.options) != 4:
            raise ValueError("options must have exactly 4 items")
        if len(set(self.options)) != 4:
            raise ValueError("options must be unique (no duplicates)")
        if not (0 <= self.correct <= 3):
            raise ValueError(f"correct index {self.correct} out of bounds for 4 options")
        return self


class QuizResponse(BaseModel):
    type: Literal["quiz"]
    mode: Literal["grounded", "concept_review", "topic_only", "insufficient", "error"]
    grounding_summary: str
    title: str
    questions: list[QuizQuestion]
