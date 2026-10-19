from pydantic import BaseModel, Field
from typing import Literal

class GeneratedTask(BaseModel):
    title: str
    statement: str
    difficulty: int = Field(ge=1, le=5)
    answer_type: Literal["exact", "numeric", "free"]
    reference_answer: str = ""
    reference_solution: str
    expected_minutes: int = Field(ge=1, le=60)
    hints: list[str] = Field(min_length=3, max_length=3)

class TaskRequest(BaseModel):
    mode: Literal["topic_existing", "topic_generate", "general"] = "topic_existing"
    topic_id: int | None = None
    discipline_id: int | None = None
    text: str | None = Field(None, max_length=2000)

class HintIn(BaseModel):
    question: str | None = Field(None, max_length=1000)

class SubmitIn(BaseModel):
    answer: str = Field(max_length=5000)