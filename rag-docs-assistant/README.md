# RAG Docs Assistant

ИИ-ассистент, который отвечает клиентам **по документам компании** (тарифы, FAQ, регламенты) и не выдумывает: если ответа в документах нет — честно говорит об этом. Работает в терминале, как REST API и как Telegram-бот.

## Как это работает (RAG — Retrieval-Augmented Generation)
```
документы (.md/.txt/.pdf)
   → нарезка на фрагменты по разделам        rag/loader.py
   → векторизация (TF-IDF или Gemini)        rag/embeddings.py
   → векторный индекс, косинусный поиск      rag/index.py
вопрос → поиск топ-4 фрагментов → промпт со строгими правилами → LLM → ответ + источники
                                              rag/pipeline.py, rag/llm.py
```

## Особенности
- **Два режима:** офлайн без ключей (TF-IDF + цитата из документа) и с **Gemini API** (семантические эмбеддинги + генерация ответа)
- Защита от галлюцинаций: ответ только по найденным фрагментам, порог релевантности, вопрос не по теме → «нет ответа»
- В ответе указаны источники (`файл#фрагмент`)
- Стемминг для русского языка без внешних NLP-библиотек
- FastAPI с валидацией запросов, Telegram-бот на long polling
- 7 тестов на pytest (нарезка текста, поиск, промпт, отказ от вопросов не по теме)

## Стек
Python · RAG · Gemini API (LLM + embeddings) · scikit-learn (TF-IDF) · NumPy · FastAPI · Pydantic · httpx · Telegram Bot API · pytest

## Запуск
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # ключ Gemini необязателен

python cli.py               # чат в терминале
uvicorn app:app --reload    # API: http://localhost:8000/docs
python bot.py               # Telegram-бот (нужен TELEGRAM_BOT_TOKEN)
pytest                      # тесты
```
Свои документы положите в папку `data/` и вызовите `POST /reindex`.

## Пример
```
> Сколько стоит тариф Бизнес?
Стоимость — 2 490 рублей в месяц. Безлимитные операции, до 5 пользователей...
Источники: tarify.md#2

> Какая погода в Москве?
В документах нет ответа на этот вопрос. Уточните у менеджера.
```
В `data/` — демо-документы вымышленной компании CloudDesk.

---
Разработано с использованием AI-ассистента (Claude Code).
