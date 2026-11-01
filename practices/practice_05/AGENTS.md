# AGENTS.md: AI-помощник ревьюера (практика 5)

Учебный сервис `POST /api/reviews`: принимает diff одного PR и возвращает проверяемые замечания.

## Где что лежит

- Контракт и фичи: `docs/requirements.md` — единственный источник требований.
- Правила кода: `docs/style-guide.md`. Прочитай его перед изменением кода.
- Код: `app/review.py` (логика), `app/llm.py` (адаптер и `FakeLLM`), `app/server.py` (HTTP).
- Пример теста: `tests/test_example.py`.
- Собственный MCP: `mcp_server/diff_guard.py`, tool `inspect_diff`.
- Спеки фич: `specs/`, работа по spec-kit через команды `/speckit.*`.
- Общий контракт UI и логики: `specs/contract.md`, если файл есть.

## Проверка

- Единственная команда проверки: `sh scripts/check.sh` (compileall + pytest).
- После каждой правки hook `.opencode/plugins/check-after-edit.js` сам запускает её
  и дописывает результат к выводу инструмента. FAIL нужно исправить, а не обойти.

## Как работать

- Новое поведение — через skill `test-driven-development`: сначала падающий тест, потом код.
- Перед отправкой diff в любую модель или в отчёт проверь его tool `inspect_diff`
  (MCP `diff-guard`): размер и секреты. Секреты не цитируй.
- Ревью diff по контракту OUT-1 — skill `diff-review`.

## Нельзя без поручения человека

- Менять `docs/requirements.md`, `scripts/check.sh`, `.opencode/` и `opencode.json`.
- Добавлять зависимости в `app/`.
- Делать `git commit`, `git push`, менять ветки.
