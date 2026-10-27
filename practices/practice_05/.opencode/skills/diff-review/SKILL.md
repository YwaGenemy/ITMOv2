---
name: diff-review
description: Use when asked to review a diff or a feature branch against the project contract; produces at most three evidence-backed risks in OUT-1 JSON and validates them with a script
---

# diff-review

Ревью одного diff в формате продукта (OUT-1): `summary`, не больше трёх `risks`
с `file`, `line`, `evidence`, `risk` и список `checks`. Каждое замечание должно опираться
на строку diff (QA-1). Скрипт проверяет это механически, смысл оценивает человек.

## Процедура

1. Сохрани diff в файл, например `git diff main...HEAD -- . > evidence/review.diff`.
   Если diff пустой — так и скажи и остановись.
2. Вызови MCP tool `inspect_diff` (сервер `diff-guard`) с текстом diff.
   - Ошибка `diff_too_large` или `not_a_diff` → остановись и сообщи код, не обрезай вход.
   - Есть `secrets` → работай только с `redacted_diff`, значения не цитируй.
     Сам факт секрета в diff — риск номер один.
3. Прочитай `docs/requirements.md`. Ищи нарушения контракта, а не стиль.
4. Запиши результат в `evidence/review.json`:
   ```json
   {"summary": "...", "risks": [{"file": "app/review.py", "line": 12,
     "evidence": "точная подстрока строки 12 новой версии", "risk": "что нарушено и почему"}],
    "checks": ["команда или сценарий, которые подтвердят риск"]}
   ```
   `line` — номер строки в новой версии файла. Нет доказанных рисков → `"risks": []`.
5. Запусти валидатор:
   `.venv/bin/python .opencode/skills/diff-review/scripts/validate_review.py evidence/review.diff evidence/review.json`
   Исправляй JSON, пока не будет `OK`. Не подгоняй evidence под строку, если риск от этого
   теряет смысл, — лучше удали риск.
6. Покажи человеку JSON и вывод валидатора. Решение по замечаниям принимает он.

## Чего не делать

- Не правь код в рамках ревью.
- Не добавляй четвёртый риск «на всякий случай».
- Не пиши риски без строки-доказательства («в проекте нет авторизации»).
