from enum import StrEnum

class Role(StrEnum):          student = "student"; admin = "admin"
class AnswerType(StrEnum):    exact = "exact"; numeric = "numeric"; free = "free"
class DocType(StrEnum):       theory = "theory"; example = "example"; pitfall = "pitfall"; glossary = "glossary"; task_pattern = "task_pattern"
class TaskStatus(StrEnum):    approved = "approved"; auto = "auto"; rejected = "rejected"
class TaskSource(StrEnum):    manual = "manual"; generated = "generated"
class Mode(StrEnum):          topic = "topic"; general = "general"