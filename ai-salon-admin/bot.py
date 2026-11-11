#!/usr/bin/env python3
"""
AI salon administrator.

    python bot.py            # Telegram bot (TELEGRAM_BOT_TOKEN in .env)
    python bot.py --cli      # chat in the terminal, for testing and demos
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

from backends import DemoBackend, YClientsBackend  # noqa: E402
from brain import Brain  # noqa: E402

log = logging.getLogger("bot")


def make_backend():
    if os.getenv("BACKEND", "demo").lower() == "yclients":
        return YClientsBackend(os.getenv("YCLIENTS_PARTNER_TOKEN", ""), os.getenv("YCLIENTS_COMPANY_ID", ""),
                               os.getenv("YCLIENTS_USER_TOKEN", ""))
    return DemoBackend()


# --------------------------------------------------------------------------- telegram
class Telegram:
    def __init__(self, token: str):
        self.api = f"https://api.telegram.org/bot{token}"

    def send(self, chat_id, text: str) -> None:
        try:
            requests.post(f"{self.api}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=20)
        except requests.RequestException as e:
            log.warning("send failed: %s", e)

    def typing(self, chat_id) -> None:
        try:
            requests.post(f"{self.api}/sendChatAction", json={"chat_id": chat_id, "action": "typing"}, timeout=10)
        except requests.RequestException:
            pass

    def updates(self, offset: int) -> list[dict]:
        r = requests.get(f"{self.api}/getUpdates", params={"offset": offset, "timeout": 30}, timeout=40)
        return r.json().get("result", [])


def reminder_loop(tg: Telegram, backend, hours: float = 24) -> None:
    """Demo backend only: reminds clients about their visit ~24h before."""
    sent_file = BASE_DIR / "reminders_sent.json"
    sent = set(json.loads(sent_file.read_text())) if sent_file.exists() else set()
    while True:
        try:
            now = datetime.now()
            for b in backend._bookings():
                if b["status"] != "active" or b["id"] in sent or not b["client_chat_id"]:
                    continue
                start = datetime.strptime(b["start"], "%Y-%m-%d %H:%M")
                if now < start <= now + timedelta(hours=hours):
                    tg.send(b["client_chat_id"],
                            f"Напоминаем: {b['service']} у мастера {b['master']} — {start:%d.%m в %H:%M}. "
                            f"Если планы изменились, просто напишите сюда.")
                    sent.add(b["id"])
                    sent_file.write_text(json.dumps(sorted(sent)))
        except Exception as e:  # noqa: BLE001
            log.warning("reminder loop: %s", e)
        time.sleep(300)


def run_telegram() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        sys.exit("Укажите TELEGRAM_BOT_TOKEN в .env")
    tg = Telegram(token)
    admin = os.getenv("ADMIN_CHAT_ID", "")
    backend = make_backend()
    brain = Brain(backend, notify_human=lambda chat, text: admin and tg.send(admin, text))
    if isinstance(backend, DemoBackend):
        threading.Thread(target=reminder_loop, args=(tg, backend), daemon=True).start()
    log.info("Бот запущен. Салон: %s", backend.salon_info().get("name"))
    offset = 0
    while True:
        try:
            for u in tg.updates(offset):
                offset = u["update_id"] + 1
                msg = u.get("message") or {}
                chat_id, text = msg.get("chat", {}).get("id"), msg.get("text")
                if not chat_id or not text:
                    continue
                if text == "/start":
                    tg.send(chat_id, f"Здравствуйте! Я администратор салона «{backend.salon_info()['name']}». "
                                     "Помогу записаться, перенести или отменить визит и отвечу на вопросы.")
                    continue
                if text == "/id":
                    tg.send(chat_id, f"Ваш chat_id: {chat_id}")
                    continue
                tg.typing(chat_id)
                try:
                    answer = brain.reply(str(chat_id), text)
                except Exception as e:  # noqa: BLE001
                    log.exception("reply failed")
                    answer = "Извините, у меня техническая заминка. Администратор скоро ответит вам."
                    if admin:
                        tg.send(admin, f"⚠️ Ошибка бота в чате {chat_id}: {e}")
                tg.send(chat_id, answer)
        except requests.RequestException as e:
            log.warning("network: %s — retry in 5s", e)
            time.sleep(5)


def run_cli() -> None:
    backend = make_backend()
    brain = Brain(backend, notify_human=lambda chat, text: print(f"   [→ администратору] {text}"))
    print(f"Демо: {backend.salon_info()['name']}. Пишите как клиент, «выход» — завершить.\n")
    while True:
        try:
            text = input("Клиент: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text.lower() in ("выход", "exit", "quit"):
            break
        if text:
            print(f"Бот: {brain.reply('cli-user', text)}\n")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--cli", action="store_true", help="chat in the terminal instead of Telegram")
    p.add_argument("-v", "--verbose", action="store_true")
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO if a.verbose or not a.cli else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    run_cli() if a.cli else run_telegram()


if __name__ == "__main__":
    main()
