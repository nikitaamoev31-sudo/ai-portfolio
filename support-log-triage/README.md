# Support Log Triage — разбор инцидентов по логам (L2 support)

> Портфолио для роли **инженера технической поддержки L1/L2**: как по жалобе клиента найти причину в логах nginx и приложения, отличить единичную проблему от массового сбоя, ответить клиенту и эскалировать в разработку.

[![CI](https://github.com/nikitaamoev31-sudo/ai-portfolio/actions/workflows/ci.yml/badge.svg)](https://github.com/nikitaamoev31-sudo/ai-portfolio/actions/workflows/ci.yml)

**EN:** Log-based incident triage for L2 support: nginx access logs + JSON application logs + auth logs, investigated with standard Linux tools (`grep`, `awk`, `jq`, `sort | uniq -c`) and a small Python CLI. Three customer tickets solved end to end: logs → root cause → reply to the customer → Jira escalation.

## Задача
Учебный день логов интернет-магазина (6 078 запросов): `access.log` (nginx), `app.log` (JSON Lines с `request_id`), `auth.log` (входы в личный кабинет). В логах заложены ситуации, с которыми приходят в поддержку:

| Тикет клиента | Что нашли в логах | Разбор |
|---|---|---|
| «Не могу оформить заказ, ошибка» (6 клиентов) | 48 × 503 на `POST /api/checkout` за 14:02–14:09, причина — `db pool exhausted` | [кейс 1](cases/01-checkout-503.md) |
| «Деньги списались, а заказа нет» | таймаут платёжного шлюза 30 с → заказ откатился, холд на карте не снят (баг) | [кейс 2](cases/02-payment-hold.md) |
| «Аккаунт заблокирован, я ничего не делал» | 37 неудачных входов за 4 минуты с одного IP → автоблокировка | [кейс 3](cases/03-account-locked.md) |
| (без тикета, нашли сами) | история заказов отвечает 2,6–4 с у трёх крупных клиентов, хотя p95 по сервису 292 мс | `python triage.py slow` |

## Что сделано
- [playbook.sh](playbook.sh): 6 проверок стандартными командами Linux. Так ищут прямо на сервере, где нет Python.
- [triage.py](triage.py): CLI на Python без внешних зависимостей. Ищет всплески 5xx (отличает инцидент от единичной ошибки), медленные ответы по клиентам, подбор пароля, все проблемы одного клиента, трассировку запроса по `request_id` через nginx и приложение.
- [cases/](cases): 3 разбора в формате «жалоба → расследование → ответ клиенту → эскалация в Jira».
- [gen_logs.py](gen_logs.py): детерминированный генератор логов: фоновый трафик плюс заложенные инциденты.
- 9 автотестов (pytest). Каждый проверяет, что разбор находит именно заложенный инцидент без ложных срабатываний. Отдельный тест сверяет, что `playbook.sh` и Python дают одинаковые цифры.

## Запуск
```bash
python gen_logs.py          # создать logs/
python triage.py errors     # или: slow | bruteforce | user u0215 | trace req-006078
```
Linux-плейбук: `bash playbook.sh` (нужен `jq`). Тесты: `pip install -r requirements.txt && pytest -q`.

## Пример: массовый сбой или проблема одного клиента?
```text
$ python triage.py errors
  endpoint=POST /api/checkout  errors=48  from=14:02:00  to=14:09:08  statuses={503: 48}  avg_ms=5051

$ bash playbook.sh   # шаг 2: 5xx по минутам
      1 11:47        <- одиночный 502: это тикет одного клиента (кейс 2)
      7 14:02
      7 14:03
      ...
      1 14:09        <- окно инцидента для всех (кейс 1)
```

## Почему это про меня
Почти два года в B2B-поддержке Сбера я доводил обращения корпоративных клиентов до результата. Здесь тот же подход, только на уровне L2: не пересылать жалобу в разработку как есть, а прийти с фактами — время, масштаб, `request_id`, строка ошибки и понятный ответ клиенту.
