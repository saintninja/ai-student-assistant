import re

TASK_RE = re.compile(r"\bT-(\d{6})\b", re.I)
TOUCH = ("active_seconds = active_seconds + LEAST(EXTRACT(EPOCH FROM now() - last_activity_at)::int, 300), "
         "last_activity_at = now()")
SERVABLE = "k.status IN ('approved','auto')"
TASK_SQL = """SELECT k.*, t.title AS topic, d.title AS discipline
FROM tasks k JOIN topics t ON t.id=k.topic_id JOIN disciplines d ON d.id=t.discipline_id """

def extract_task_code(text: str | None) -> str | None:
    m = TASK_RE.search(text or "")
    return f"T-{m.group(1)}" if m else None

def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())

def public(t) -> dict: 
    return {k: t[k] for k in ("code", "title", "statement", "difficulty", "answer_type", "topic", "discipline")}

def leaks(text: str, task) -> bool:
    t = norm(text)
    ans = norm(task["reference_answer"] or "")
    if ans and re.search(rf"(?<![\w.,]){re.escape(ans)}(?![\w.,])", t):
        return True
    return any(len(l := norm(line)) >= 25 and l in t
               for line in (task["reference_solution"] or "").splitlines())
