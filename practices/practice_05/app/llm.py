"""Адаптер LLM и тестовая подмена."""

import time
from typing import Protocol


class LLMClient(Protocol):
    def review(self, diff: str) -> dict: ...


DEFAULT_RESULT = {
    "summary": "Изменение небольшое, рисков с доказательствами не найдено.",
    "risks": [],
    "checks": ["Запустить sh scripts/check.sh"],
}


class FakeLLM:
    """Возвращает заданный ответ, умеет ждать и падать; запоминает вызовы."""

    def __init__(self, result: dict | None = None, delay_s: float = 0.0,
                 error: Exception | None = None):
        self.result = DEFAULT_RESULT if result is None else result
        self.delay_s = delay_s
        self.error = error
        self.calls: list[str] = []

    def review(self, diff: str) -> dict:
        self.calls.append(diff)
        if self.delay_s:
            time.sleep(self.delay_s)
        if self.error is not None:
            raise self.error
        return dict(self.result)
