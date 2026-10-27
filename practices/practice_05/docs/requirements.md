# Требования: AI-помощник ревьюера

Источник: [Context Pack практики 1](../../practice_01/context.md) и user stories из
[product_management.md](../../practice_01/product_management.md). Здесь только то, что
нужно для практики 4. Менять контракт без поручения человека нельзя.

## Контракт API

`POST /api/reviews`, тело — JSON `{"diff": "..."}`.

Точка входа для тестов: `app.review.handle_review(body: bytes, llm, *, deadline_s=10.0)`.
Функция возвращает пару `(status: int, payload: dict)`; HTTP-сервер только транслирует её.

Успех `200`: `{"summary": str, "risks": [...], "checks": [str], "request_id": str}`.
Каждый risk содержит `file` (str), `line` (int >= 1), `evidence` (str), `risk` (str).

Ошибка: `{"error": {"code": "<code>"}, "request_id": "<id>"}`.

| Код | HTTP | Когда |
|---|---:|---|
| `invalid_request` | 422 | тело не JSON, не объект, нет поля `diff`, `diff` не строка или пустая строка |
| `diff_too_large` | 413 | `diff` длиннее 20 000 Unicode code points (после JSON-декодирования) |
| `llm_timeout` | 504 | LLM не ответила за `deadline_s` секунд |
| `llm_failed` | 502 | адаптер LLM бросил исключение |

`request_id` генерирует сервис (uuid4 hex), он есть и в успехе, и в ошибке.

## Фича A — входная валидация (US-3)

- 422 `invalid_request` для всех случаев из таблицы.
- 413 `diff_too_large` для 20 001 символа; ровно 20 000 символов проходят.
- Вход не обрезается. При любом отказе LLM не вызывается ни разу.

## Фича B — ошибка зависимости (US-4)

- Вызов LLM ограничен `deadline_s` (по умолчанию 10 секунд), повторов нет.
- По истечении deadline — 504 `llm_timeout`, ответ не ждёт завершения LLM.
- Исключение адаптера — 502 `llm_failed`; текст исключения не попадает в ответ.
- Сценарии фичи A сохраняются.

## Наблюдаемость (OBS-1)

Логи содержат только `request_id`, `duration_ms`, `status`. Diff и ответ LLM не логируются.

## Вне практики 4

Очистка секретов (US-2) и проверка схемы ответа модели (US-1, `invalid_llm_output`) —
следующие истории бэклога.
