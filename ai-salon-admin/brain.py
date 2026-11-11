"""
The AI administrator: Gemini (or OpenAI) with function calling over the booking backend.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Callable

import requests

from backends import BookingError

log = logging.getLogger("brain")

WEEKDAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]

TOOLS = [
    {"name": "salon_info", "description": "Адрес, телефон, часы работы и правила салона.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "list_services", "description": "Список услуг с ценами и длительностью.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "list_masters", "description": "Мастера салона; можно отфильтровать по услуге.",
     "parameters": {"type": "object", "properties": {"service_id": {"type": "integer"}}}},
    {"name": "free_slots", "description": "Свободное время на дату для услуги (и мастера, если выбран).",
     "parameters": {"type": "object", "properties": {
         "service_id": {"type": "integer"}, "date": {"type": "string", "description": "ГГГГ-ММ-ДД"},
         "master_id": {"type": "integer"}}, "required": ["service_id", "date"]}},
    {"name": "create_booking",
     "description": "Записать клиента. Вызывать ТОЛЬКО после того, как клиент подтвердил услугу, мастера, "
                    "дату, время, имя и телефон.",
     "parameters": {"type": "object", "properties": {
         "service_id": {"type": "integer"}, "master_id": {"type": "integer"},
         "start": {"type": "string", "description": "ГГГГ-ММ-ДД ЧЧ:ММ"},
         "client_name": {"type": "string"}, "client_phone": {"type": "string"}},
         "required": ["service_id", "master_id", "start", "client_name", "client_phone"]}},
    {"name": "my_bookings", "description": "Будущие записи этого клиента.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "cancel_booking", "description": "Отменить запись клиента после его подтверждения.",
     "parameters": {"type": "object", "properties": {"booking_id": {"type": "integer"}},
                    "required": ["booking_id"]}},
    {"name": "reschedule_booking", "description": "Перенести запись клиента на новое время после подтверждения.",
     "parameters": {"type": "object", "properties": {
         "booking_id": {"type": "integer"}, "new_start": {"type": "string", "description": "ГГГГ-ММ-ДД ЧЧ:ММ"}},
         "required": ["booking_id", "new_start"]}},
    {"name": "call_human", "description": "Передать вопрос живому администратору: жалобы, мед. противопоказания, "
                                          "скидки, всё, чего нет в данных, или если клиент просит человека.",
     "parameters": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}},
]


def system_prompt(salon_name: str) -> str:
    now = datetime.now()
    return f"""Ты — вежливый ИИ-администратор салона «{salon_name}». Отвечаешь клиентам в мессенджере.
Сегодня {now:%Y-%m-%d}, {WEEKDAYS[now.weekday()]}, сейчас {now:%H:%M}.

ПРАВИЛА
- Пиши по-русски, коротко и тепло, 1–3 предложения. Без канцелярита. Обращение на «вы».
- Услуги, цены, мастеров и время бери ТОЛЬКО из инструментов. Ничего не выдумывай.
- Запись: узнай услугу → (мастер, если важно) → дату → предложи 3–5 свободных времени →
  спроси имя и телефон → повтори всё одной строкой и спроси «Записываю?» → после «да» вызови create_booking.
- Отмена и перенос — только записей этого клиента (my_bookings) и после его подтверждения.
- Слова «сегодня», «завтра», «в пятницу» переводи в дату сам.
- Если инструмент вернул ошибку — объясни простыми словами и предложи вариант.
- Медицинские вопросы, жалобы, скидки, всё непонятное — вызывай call_human и скажи, что администратор скоро ответит.
- Не обсуждай темы, не связанные с салоном.
"""


class Brain:
    def __init__(self, backend, notify_human: Callable[[str, str], None] | None = None):
        self.backend = backend
        self.notify_human = notify_human or (lambda chat_id, text: log.info("HUMAN: %s", text))
        self.provider = os.getenv("LLM_PROVIDER", "gemini").lower()
        self.model = os.getenv("LLM_MODEL") or ("gemini-flash-latest" if self.provider == "gemini" else "gpt-4.1-mini")
        self.key = os.getenv("GEMINI_API_KEY" if self.provider == "gemini" else "OPENAI_API_KEY", "")
        self.histories: dict[str, list] = {}
        self.max_turns = 20
        self.llm_call = self._gemini if self.provider == "gemini" else self._openai  # replaceable in tests

    # ------------------------------------------------------------------ tools
    def run_tool(self, name: str, args: dict, chat_id: str) -> dict:
        b = self.backend
        try:
            if name == "salon_info":
                return {"result": b.salon_info()}
            if name == "list_services":
                return {"result": b.list_services()}
            if name == "list_masters":
                return {"result": b.list_masters(args.get("service_id"))}
            if name == "free_slots":
                return {"result": b.free_slots(args["service_id"], args["date"], args.get("master_id"))}
            if name == "create_booking":
                bk = b.create_booking(args["service_id"], args["master_id"], args["start"],
                                      args["client_name"], args["client_phone"], chat_id)
                self.notify_human(chat_id, f"✅ Новая запись: {bk.get('service', '')} у {bk.get('master', '')}, "
                                           f"{bk['start']}, {bk['client_name']} {bk['client_phone']}")
                return {"result": bk}
            if name == "my_bookings":
                return {"result": b.client_bookings(chat_id)}
            if name == "cancel_booking":
                bk = b.cancel_booking(args["booking_id"], chat_id)
                self.notify_human(chat_id, f"❌ Отмена записи #{bk['id']}: {bk['start']}, {bk['client_name']}")
                return {"result": bk}
            if name == "reschedule_booking":
                bk = b.reschedule_booking(args["booking_id"], chat_id, args["new_start"])
                self.notify_human(chat_id, f"🔁 Перенос записи #{bk['id']} на {bk['start']}, {bk['client_name']}")
                return {"result": bk}
            if name == "call_human":
                self.notify_human(chat_id, f"🙋 Нужен администратор (чат {chat_id}): {args.get('reason')}")
                return {"result": "Администратор получил уведомление"}
            return {"error": f"Неизвестный инструмент {name}"}
        except BookingError as e:
            if name in ("cancel_booking", "reschedule_booking"):
                self.notify_human(chat_id, f"🙋 Клиент {chat_id} просит {name}: {args}. Причина: {e}")
            return {"error": str(e)}
        except Exception as e:  # noqa: BLE001
            log.exception("tool %s failed", name)
            return {"error": f"Техническая ошибка: {e}"}

    # ------------------------------------------------------------------ dialogue
    def reply(self, chat_id: str, text: str) -> str:
        chat_id = str(chat_id)
        hist = self.histories.setdefault(chat_id, [])
        hist.append({"role": "user", "text": text})
        salon = self.backend.salon_info().get("name", "")
        for _ in range(8):  # max tool rounds per message
            msg = self.llm_call(system_prompt(salon), hist)
            calls = msg.get("calls") or []
            hist.append({"role": "model", "text": msg.get("text", ""), "calls": calls, "raw": msg.get("raw")})
            if not calls:
                if len(hist) > self.max_turns:  # trim, but always start on a user message
                    del hist[:-self.max_turns]
                    while hist and hist[0]["role"] != "user":
                        hist.pop(0)
                return msg.get("text", "").strip() or "Извините, не расслышала. Повторите, пожалуйста?"
            results = []
            for c in calls:
                res = self.run_tool(c["name"], c.get("args") or {}, chat_id)
                log.info("tool %s(%s) -> %s", c["name"], c.get("args"), str(res)[:200])
                results.append({"name": c["name"], "id": c.get("id"), "response": res})
            hist.append({"role": "tool", "results": results})
        return "Секунду, уточню у администратора."

    # ------------------------------------------------------------------ providers
    def _gemini(self, system: str, hist: list) -> dict:
        contents = []
        for h in hist:
            if h["role"] == "user":
                contents.append({"role": "user", "parts": [{"text": h["text"]}]})
            elif h["role"] == "model" and h.get("raw"):
                # echo Gemini's own parts back (keeps thought signatures required by newer models)
                contents.append({"role": "model", "parts": h["raw"]})
            elif h["role"] == "model":
                parts = ([{"text": h["text"]}] if h.get("text") else []) + \
                        [{"functionCall": {"name": c["name"], "args": c.get("args") or {}}} for c in h.get("calls", [])]
                contents.append({"role": "model", "parts": parts or [{"text": ""}]})
            else:
                contents.append({"role": "user", "parts": [
                    {"functionResponse": {"name": r["name"], "response": r["response"]}} for r in h["results"]]})
        body = {"systemInstruction": {"parts": [{"text": system}]}, "contents": contents,
                "tools": [{"functionDeclarations": TOOLS}], "generationConfig": {"temperature": 0.3}}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        r = requests.post(url, headers={"x-goog-api-key": self.key}, json=body, timeout=60)
        if r.status_code != 200:
            raise RuntimeError(f"Gemini HTTP {r.status_code}: {r.text[:300]}")
        parts = r.json()["candidates"][0]["content"].get("parts", [])
        return {"raw": parts,
                "text": "".join(p.get("text", "") for p in parts if not p.get("thought")),
                "calls": [{"name": p["functionCall"]["name"], "args": p["functionCall"].get("args", {})}
                          for p in parts if "functionCall" in p]}

    def _openai(self, system: str, hist: list) -> dict:
        msgs = [{"role": "system", "content": system}]
        for h in hist:
            if h["role"] == "user":
                msgs.append({"role": "user", "content": h["text"]})
            elif h["role"] == "model":
                m = {"role": "assistant", "content": h.get("text") or None}
                if h.get("calls"):
                    m["tool_calls"] = [{"id": c["id"], "type": "function",
                                        "function": {"name": c["name"], "arguments": json.dumps(c.get("args") or {})}}
                                       for c in h["calls"]]
                msgs.append(m)
            else:
                for res in h["results"]:
                    msgs.append({"role": "tool", "tool_call_id": res["id"],
                                 "content": json.dumps(res["response"], ensure_ascii=False)})
        r = requests.post("https://api.openai.com/v1/chat/completions", timeout=60,
                          headers={"Authorization": f"Bearer {self.key}"},
                          json={"model": self.model, "messages": msgs, "temperature": 0.3,
                                "tools": [{"type": "function", "function": t} for t in TOOLS]})
        if r.status_code != 200:
            raise RuntimeError(f"OpenAI HTTP {r.status_code}: {r.text[:300]}")
        m = r.json()["choices"][0]["message"]
        return {"text": m.get("content") or "",
                "calls": [{"id": c["id"], "name": c["function"]["name"],
                           "args": json.loads(c["function"]["arguments"] or "{}")} for c in m.get("tool_calls") or []]}
