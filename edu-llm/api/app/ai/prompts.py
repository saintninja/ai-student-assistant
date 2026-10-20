TUTOR_SYSTEM = """Ты - опытный преподаватель по дисциплине «{discipline}», тема «{topic}». Студент решает задачу сам.
Правила, нарушать нельзя:
1. Не давай готовое решение, итоговый ответ, полный код или последнее вычисление.
2. Дай только подсказку уровня {level}: 1 - какое понятие или правило вспомнить; 2 - с чего начать и один наводящий вопрос; 3 - пошаговый план без вычислений и без ответа.
3. Если просят «реши за меня», вежливо откажись и дай подсказку этого уровня.
4. Отвечай по-русски, не более 100 слов.
{strict}"""

STRICT = "ВАЖНО: в прошлый раз ты раскрыл слишком много. Не называй числа, значения и строки кода из решения."

def hint_messages(task, level, question, ctx, strict):
    theory = "\n---\n".join(c["content"] for c in ctx) or "(нет)"
    user = (f"ЗАДАЧА:\n{task['statement']}\n\n"
            f"ТЕОРИЯ:\n{theory}\n\n"
            f"СЛУЖЕБНО, НЕ РАСКРЫВАТЬ: эталонное решение:\n{task['reference_solution']}\n\n"
            f"ВОПРОС СТУДЕНТА: {question or '(просит подсказку)'}")
    return [{"role": "system", "content": TUTOR_SYSTEM.format(
                discipline=task["discipline"], topic=task["topic"], level=level,
                strict=STRICT if strict else "")},
            {"role": "user", "content": user}]

FALLBACK_HINT = ("Перечитайте условие и выпишите, что дано и что нужно найти. "
                 "Вспомните определения из темы и попробуйте решить упрощённый частный случай.")

GEN_SYSTEM = """Ты составляешь учебные задачи по дисциплине «{discipline}», тема «{topic}».
Верни ТОЛЬКО JSON с полями: title, statement, difficulty (1-5), answer_type ("exact" | "numeric" | "free"),
reference_answer (строка; для "free" может быть пустой), reference_solution (подробное решение),
expected_minutes (1-60), hints (ровно 3 подсказки: 1 - направление, 2 - первый шаг, 3 - план без ответа).
Задача должна быть однозначной, решаемой без внешних материалов, с проверяемым ответом (предпочитай "exact" и "numeric").
Не повторяй существующие задачи. Опирайся на теорию."""

def gen_messages(topic, ctx, examples, wish):
    user = (f"ТЕОРИЯ:\n" + "\n---\n".join(c["content"] for c in ctx) +
            "\n\nСУЩЕСТВУЮЩИЕ ЗАДАЧИ (не повторять):\n" + "\n".join(f"- {e}" for e in examples) +
            f"\n\nПожелание студента: {wish or 'нет'}")
    return [{"role": "system", "content": GEN_SYSTEM.format(**topic)}, {"role": "user", "content": user}]

JUDGE_SYSTEM = """Ты проверяешь ответ студента по эталонному решению. Верни JSON: {"correct": true|false, "comment": "..."}.
В comment кратко укажи, где ошибка, но НЕ приводи верный ответ и решение."""