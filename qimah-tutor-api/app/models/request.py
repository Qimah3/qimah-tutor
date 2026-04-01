from typing import Literal
from pydantic import BaseModel


class TopicContext(BaseModel):
    text: str
    headings: list[str]
    code_blocks: list[str]
    has_video: bool


class GenerateRequest(BaseModel):
    type: Literal["quiz", "flashcard"]
    count: int
    difficulty: Literal["easy", "medium", "hard", "mixed"]
    course_id: int
    topic_id: int
    user_id: int
    context: TopicContext
