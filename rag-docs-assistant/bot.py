"""Telegram-бот (long polling): python bot.py"""
import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

from rag.pipeline import RAGPipeline  # noqa: E402

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
API = f"https://api.telegram.org/bot{TOKEN}"


def send(chat_id: int, text: str) -> None:
    httpx.post(f"{API}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=30)


def main() -> None:
    rag = RAGPipeline(os.getenv("DOCS_DIR", "data"))
    offset = 0
    print("Бот запущен")
    while True:
        try:
            r = httpx.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 30}, timeout=40)
            for upd in r.json().get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message") or {}
                text, chat = msg.get("text"), msg.get("chat", {}).get("id")
                if not text or not chat:
                    continue
                if text == "/start":
                    send(chat, "Здравствуйте! Задайте вопрос о наших услугах.")
                    continue
                send(chat, rag.ask(text).text)
        except httpx.HTTPError as e:
            print("Сетевая ошибка, повтор через 5 с:", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
