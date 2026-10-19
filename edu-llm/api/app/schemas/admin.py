from typing import Literal
from pydantic import BaseModel, Field

class StudentIn(BaseModel):
    ins: str
    full_name: str
    group_name: str | None = None

class TaskIn(BaseModel):
    discipline: str
    topic: str
    title: str
    statement: str
    difficulty: int = Field(ge=1, le=5)
    answer_type: Literal["exact", "numeric", "free"]
    reference_answer: str = ""
    reference_solution: str
    expected_minutes: int = 10
    hints: list[str] = []

class KBIn(BaseModel):
    discipline: str
    topic: str
    doc_type: Literal["theory", "example", "pitfall", "task_pattern", "glossary"]
    title: str
    source: str = ""
    text: str