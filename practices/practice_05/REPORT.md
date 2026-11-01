# Практика 5: две команды, одна фича

Проект тот же, что в практике 4: AI-помощник ревьюера (POST /api/reviews). Фича: веб-страница,
куда вставляешь diff и видишь замечания или понятную ошибку. Две "команды" это две отдельные
сессии агента OpenCode (модель gpt-6.1-sol-fast), одна делала UI, другая логику.
Логика заодно закрывает следующую историю из бэклога, US-4: таймаут модели и ошибка модели.

## Запуск и демо

```
make check                               # все тесты, 120 passed
.venv/bin/python -m app.server 8000      # страница на http://127.0.0.1:8000
.venv/bin/python -m app.server 8000 --llm slow   # модель зависает, через 10 с ошибка 504
.venv/bin/python -m app.server 8000 --llm fail   # модель падает, ошибка 502
```

## Другой SDD-фреймворк: GitHub spec-kit

На практике был OpenSpec, тут взял spec-kit (specify-cli 1.2.4). Подключил через
`specify init --here --integration opencode`, он добавил команды /speckit.* в .opencode/commands
и шаблоны в .specify/.

Порядок работы:

1. /speckit.constitution: общие правила проекта (.specify/memory/constitution.md)
2. /speckit.specify: команда 1 пишет спеку UI, команда 2 спеку логики, в разных сессиях
3. общая сверка: расхождения, решения D1-D6, общий контракт
4. /speckit.plan, /speckit.tasks, /speckit.implement: отдельно для логики и для UI

Логи всех запусков по порядку лежат в evidence/ (01-constitution ... 10-ui-implement).

### Сравнение с OpenSpec

| | OpenSpec | spec-kit |
|---|---|---|
| Этапы | propose сразу делает proposal, спеки и задачи | отдельные команды specify, plan, tasks, implement |
| Правила проекта | rules в openspec/config.yaml | конституция .specify/memory/constitution.md |
| Где лежит | changes/, после приёмки archive и sync в общие specs | specs/NNN-имя/ на каждую фичу, архива нет |
| Объём | спека и задачи, design по желанию | сразу spec, plan, research, data-model, contracts, quickstart, tasks, чек-лист |
| Под что | доработки в существующем проекте | больше под новые фичи с нуля |

По ощущениям spec-kit тяжелее: на маленькую фичу он сгенерил кучу файлов. Зато каждый шаг
отдельный, и между ними можно остановиться и прочитать. В OpenSpec удобнее, что после приёмки
изменение уходит в архив, а общая спека обновляется. В spec-kit такого нет, спеки фич
просто копятся в specs/.

## Две спеки и общий контракт

- спека UI: specs/001-reviewer-web-ui/spec.md
- спека логики: specs/002-review-api-deadline/spec.md
- общий контракт: specs/contract.md
- версии до сверки: evidence/specs-before/, после: evidence/specs-after/

Что не сходилось до сверки и как решили:

| | Вопрос | Решение |
|---|---|---|
| D1 | кто отдаёт страницу по GET / | тот же сервер, файл app/static/index.html; маршрут делает логика, содержимое UI |
| D2 | кто проверяет длину diff | только сервер, UI ничего не обрезает |
| D3 | гарантирует ли сервер не больше 3 рисков | пока нет (это US-1), поэтому UI сам проверяет ответ и показывает "Некорректный ответ сервиса" |
| D4 | какие ошибки бывают | 422, 413, 504, 502 со своими текстами; всё остальное "Сервис недоступен" |
| D5 | сколько ждёт браузер | 15 секунд, сервер 10 |
| D6 | что показывать в ошибке | текст и request_id |

## Реализация и проверки

- логика: app/review.py (таймаут через поток и очередь), app/server.py (GET /, режимы --llm)
- UI: app/static/index.html, один файл, чистый JS без фреймворков
- тесты: tests/test_review_deadline.py, tests/test_server.py (настоящий HTTP),
  tests/test_web_ui.py + tests/web_ui.test.cjs (JS страницы гоняется через Node)
- make check: 120 passed
- руками: GET / отдаёт страницу, нормальный diff даёт 200, пустой запрос 422, slow даёт 504
  примерно за 10 с, fail даёт 502

## Рефлексия

reflection.md
