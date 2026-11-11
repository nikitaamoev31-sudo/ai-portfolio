#!/usr/bin/env python3
"""Автоматический демо-диалог: клиент пишет боту, бот отвечает (настоящий Gemini, тестовый салон)."""
import time
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).resolve().parent / ".env")
from backends import DemoBackend
from brain import Brain

MESSAGES = [
    "Здравствуйте! Сколько стоит маникюр с покрытием?",
    "Хочу записаться на маникюр завтра, что есть свободное?",
    "Давайте самое раннее время",
    "Ирина, +995 555 12 34 56",
    "Да, записывайте",
    "А можно перенести на час позже?",
    "Подскажите, вы делаете скидку именинникам?",
]

be = DemoBackend()
brain = Brain(be, notify_human=lambda c, t: print(f"      📩 [администратору] {t}"))
print(f"=== Демо: {be.salon_info()['name']} ===\n")
for m in MESSAGES:
    print(f"👩 Клиент: {m}")
    try:
        print(f"🤖 Бот: {brain.reply('demo-client', m)}\n")
    except Exception as e:
        print(f"❌ Ошибка: {e}\n"); break
    time.sleep(1)
print("=== Конец демо ===")
