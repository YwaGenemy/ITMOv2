| ID | Связь компонентов | Как воспроизводим | Ожидаемый результат | Evidence |
|---|---|---|---|---|
| I-06 | API → Service → fake LLM | JSON `{"diff": "x"*20000}`, fake LLM считает вызовы | 200, fake.calls=1, валидный JSON по OUT-1 | План, не запускалось |
| I-07 | API → Service | JSON `{"diff": "x"*20001}`, fake LLM считает вызовы | 413, fake.calls=0, без вызова модели | План, не запускалось |
| I-08 | API → Service → fake LLM | JSON `{"diff": "token=sk_live_abc123"}`, fake LLM проверяет prompt | 200, в prompt fake видит `token=[REDACTED]`, fake.calls=1 | План, не запускалось |
