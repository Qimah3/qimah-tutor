from typing import Literal
from pydantic import BaseModel, model_validator


VALID_CARD_TYPES = {"definition", "contrast", "formula", "code", "mistake", "trap"}


class FlashcardSource(BaseModel):
    source_file: str
    source_page: int
    source_type: Literal["old_exam", "lecture_note", "handout", "screenshot"]
    source_excerpt: str


class Flashcard(BaseModel):
    card_type: Literal["definition", "contrast", "formula", "code", "mistake", "trap"]
    front: str
    back: str
    source: FlashcardSource


class FlashcardResponse(BaseModel):
    type: Literal["flashcard"]
    mode: Literal["grounded", "concept_review", "topic_only", "insufficient", "error"]
    grounding_summary: str
    title: str
    cards: list[Flashcard]

    @model_validator(mode="after")
    def validate_card_diversity(self):
        types = {card.card_type for card in self.cards}
        if len(types) < 3:
            raise ValueError(
                f"FlashcardResponse must have at least 3 different card types, got: {types}"
            )
        return self
