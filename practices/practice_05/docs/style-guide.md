# Style guide

1. Проверяй поведение через публичный интерфейс `handle_review`, а не через внутренние функции.
2. LLM в тестах — только `FakeLLM` из `app/llm.py`; сеть и реальные провайдеры не нужны.
3. Только стандартная библиотека Python в `app/`. Не добавляй framework ради маленькой правки.
4. Ошибки возвращай через одну функцию-конструктор ответа, коды — строго из `docs/requirements.md`.
5. Не ослабляй `scripts/check.sh` и не удаляй тесты ради зелёного результата.

## Хороший пример

```python
def test_missing_diff_is_rejected_without_llm_call():
    llm = FakeLLM()
    status, payload = handle_review(b'{}', llm)
    assert status == 422
    assert payload["error"]["code"] == "invalid_request"
    assert llm.calls == []
```

Тест вызывает публичную функцию, проверяет статус, код ошибки и то, что LLM не вызывалась.
