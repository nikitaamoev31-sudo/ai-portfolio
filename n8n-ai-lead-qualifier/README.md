# AI Lead Qualifier — n8n workflow

Автоматическая обработка заявок с сайта: **ИИ оценивает каждого лида, горячих сразу отправляет в Telegram отделу продаж** вместе с черновиком ответа клиенту. Менеджер не тратит время на «пустые» заявки и отвечает горячим за минуты.

## Схема
```
Webhook (POST /webhook/lead)
  → Config            ключи и настройки в одном месте
  → Normalize lead    очистка данных, валидация, сборка промпта (JS)
  → Gemini            оценка 1–10, ниша, суть запроса, черновик ответа (JSON-режим, 3 ретрая)
  → Parse AI response разбор JSON, защита от битого ответа модели (JS)
  → Hot lead?         score ≥ порога
       ├─ да  → Telegram: уведомление менеджеру 🔥
       └─ нет ─┐
  → Respond           JSON-ответ сайту: {status, score, hot, segment, summary}
```

## Стек
n8n · Webhook · Code (JavaScript) · HTTP Request · Gemini API (structured JSON output) · Telegram Bot API · IF-ветвление · retry on fail

## Установка
1. В n8n: **Workflows → Import from File** → `ai-lead-qualifier.workflow.json`.
2. Откройте ноду **Config** и вставьте: `geminiApiKey` (бесплатно на aistudio.google.com), `telegramBotToken` (@BotFather), `telegramChatId`, при желании — порог `hotThreshold` и описание своей компании.
3. Включите воркфлоу (Active).

## Проверка
```bash
curl -X POST http://localhost:5678/webhook/lead \
  -H "Content-Type: application/json" \
  -d '{"name":"Анна","email":"anna@shop.ru","company":"Shop.ru","budget":"5000$","message":"Нужен чат-бот для интернет-магазина"}'
```
Ответ:
```json
{"status":"ok","score":9,"hot":true,"segment":"e-commerce","summary":"Нужен чат-бот для интернет-магазина"}
```
и сообщение в Telegram:
```
🔥 Горячий лид (9/10)
Анна — Shop.ru
anna@shop.ru
Бюджет: 5000$

Нужен чат-бот для интернет-магазина

Черновик ответа:
Здравствуйте, Анна! ...
```
Заявка без email и текста отклоняется с ошибкой.

## Как развивать
Добавить запись лида в Google Sheets / CRM (HubSpot, amoCRM), автоответ клиенту по email, дедупликацию по email.

---
Протестировано на n8n 2.x. Разработано с использованием AI-ассистента (Claude Code).
