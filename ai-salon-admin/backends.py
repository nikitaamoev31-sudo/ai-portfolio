"""
Booking backends.

DemoBackend    — test salon from salon_demo.json, bookings kept in bookings.json.
YClientsBackend — real salon in YCLIENTS via its public booking API.

Both expose the same methods, so the AI brain does not care which one runs.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent


class BookingError(Exception):
    pass


# --------------------------------------------------------------------------- demo
class DemoBackend:
    def __init__(self, salon_file: Path = BASE_DIR / "salon_demo.json",
                 bookings_file: Path = BASE_DIR / "bookings.json"):
        self.salon = json.loads(Path(salon_file).read_text(encoding="utf-8"))
        self.bookings_file = Path(bookings_file)
        self._lock = threading.Lock()
        if not self.bookings_file.exists():
            self.bookings_file.write_text("[]", encoding="utf-8")

    # -- helpers
    def _bookings(self) -> list[dict]:
        return json.loads(self.bookings_file.read_text(encoding="utf-8"))

    def _save(self, data: list[dict]) -> None:
        self.bookings_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _service(self, service_id: int) -> dict:
        for s in self.salon["services"]:
            if s["id"] == int(service_id):
                return s
        raise BookingError(f"Услуга {service_id} не найдена")

    def _master(self, master_id: int) -> dict:
        for m in self.salon["masters"]:
            if m["id"] == int(master_id):
                return m
        raise BookingError(f"Мастер {master_id} не найден")

    @staticmethod
    def _parse(dt: str) -> datetime:
        try:
            return datetime.strptime(dt, "%Y-%m-%d %H:%M")
        except ValueError as e:
            raise BookingError("Время должно быть в формате ГГГГ-ММ-ДД ЧЧ:ММ") from e

    def _busy(self, master_id: int, start: datetime, end: datetime, ignore_id: int | None = None) -> bool:
        for b in self._bookings():
            if b["status"] != "active" or b["master_id"] != master_id or b["id"] == ignore_id:
                continue
            bs, be = self._parse(b["start"]), self._parse(b["end"])
            if start < be and bs < end:
                return True
        return False

    def _within_hours(self, start: datetime, end: datetime) -> bool:
        wh = self.salon["work_hours"]
        if start.weekday() in wh.get("days_off", []):
            return False
        open_t = datetime.combine(start.date(), datetime.strptime(wh["start"], "%H:%M").time())
        close_t = datetime.combine(start.date(), datetime.strptime(wh["end"], "%H:%M").time())
        return open_t <= start and end <= close_t

    # -- public API
    def salon_info(self) -> dict:
        s = self.salon
        return {"name": s["name"], "address": s["address"], "phone": s["phone"],
                "work_hours": s["work_hours"], "policies": s["policies"], "currency": s["currency"]}

    def list_services(self) -> list[dict]:
        cur = self.salon["currency"]
        return [{**s, "price": f"{s['price']} {cur}"} for s in self.salon["services"]]

    def list_masters(self, service_id: int | None = None) -> list[dict]:
        ms = self.salon["masters"]
        if service_id:
            ms = [m for m in ms if int(service_id) in m["service_ids"]]
        return [{"id": m["id"], "name": m["name"], "specialization": m["specialization"]} for m in ms]

    def free_slots(self, service_id: int, date: str, master_id: int | None = None,
                   now: datetime | None = None) -> list[dict]:
        now = now or datetime.now()
        svc = self._service(service_id)
        day = datetime.strptime(date, "%Y-%m-%d")
        wh = self.salon["work_hours"]
        if day.weekday() in wh.get("days_off", []):
            return []
        step = timedelta(minutes=self.salon["slot_step_min"])
        dur = timedelta(minutes=svc["duration_min"])
        masters = [self._master(master_id)] if master_id else \
            [m for m in self.salon["masters"] if svc["id"] in m["service_ids"]]
        result = []
        for m in masters:
            if svc["id"] not in m["service_ids"]:
                continue
            t = datetime.combine(day.date(), datetime.strptime(wh["start"], "%H:%M").time())
            times = []
            while self._within_hours(t, t + dur):
                if t > now and not self._busy(m["id"], t, t + dur):
                    times.append(t.strftime("%H:%M"))
                t += step
            if times:
                result.append({"master_id": m["id"], "master": m["name"], "times": times})
        return result

    def create_booking(self, service_id: int, master_id: int, start: str,
                       client_name: str, client_phone: str, client_chat_id: str = "") -> dict:
        with self._lock:
            svc, m = self._service(service_id), self._master(master_id)
            if svc["id"] not in m["service_ids"]:
                raise BookingError(f"{m['name']} не выполняет услугу «{svc['title']}»")
            s = self._parse(start)
            e = s + timedelta(minutes=svc["duration_min"])
            if s <= datetime.now():
                raise BookingError("Это время уже прошло")
            if not self._within_hours(s, e):
                raise BookingError("Салон в это время не работает")
            if self._busy(m["id"], s, e):
                raise BookingError("Это время уже занято")
            data = self._bookings()
            booking = {"id": max([b["id"] for b in data], default=0) + 1, "status": "active",
                       "service_id": svc["id"], "service": svc["title"],
                       "master_id": m["id"], "master": m["name"],
                       "start": s.strftime("%Y-%m-%d %H:%M"), "end": e.strftime("%Y-%m-%d %H:%M"),
                       "client_name": client_name, "client_phone": client_phone,
                       "client_chat_id": str(client_chat_id),
                       "price": f"{svc['price']} {self.salon['currency']}"}
            data.append(booking)
            self._save(data)
            return booking

    def client_bookings(self, client_chat_id: str) -> list[dict]:
        now = datetime.now()
        return [b for b in self._bookings() if b["client_chat_id"] == str(client_chat_id)
                and b["status"] == "active" and self._parse(b["start"]) > now]

    def _own(self, booking_id: int, client_chat_id: str) -> tuple[list[dict], dict]:
        data = self._bookings()
        for b in data:
            if b["id"] == int(booking_id) and b["client_chat_id"] == str(client_chat_id) and b["status"] == "active":
                return data, b
        raise BookingError("Запись не найдена")

    def cancel_booking(self, booking_id: int, client_chat_id: str) -> dict:
        with self._lock:
            data, b = self._own(booking_id, client_chat_id)
            b["status"] = "cancelled"
            self._save(data)
            return b

    def reschedule_booking(self, booking_id: int, client_chat_id: str, new_start: str) -> dict:
        with self._lock:
            data, b = self._own(booking_id, client_chat_id)
            svc = self._service(b["service_id"])
            s = self._parse(new_start)
            e = s + timedelta(minutes=svc["duration_min"])
            if s <= datetime.now() or not self._within_hours(s, e):
                raise BookingError("Неподходящее время")
            if self._busy(b["master_id"], s, e, ignore_id=b["id"]):
                raise BookingError("Это время уже занято")
            b["start"], b["end"] = s.strftime("%Y-%m-%d %H:%M"), e.strftime("%Y-%m-%d %H:%M")
            self._save(data)
            return b


# --------------------------------------------------------------------------- YCLIENTS
class YClientsBackend:
    """Public booking API of YCLIENTS (api.yclients.com/api/v1/book_*).

    Needs a partner token and the company id. Check endpoint behaviour with your own
    YCLIENTS account before going live — fields can differ between accounts.
    """
    API = "https://api.yclients.com/api/v1"

    def __init__(self, partner_token: str, company_id: str, user_token: str = ""):
        if not (partner_token and company_id):
            raise BookingError("YCLIENTS_PARTNER_TOKEN и YCLIENTS_COMPANY_ID обязательны")
        self.cid = company_id
        auth = f"Bearer {partner_token}" + (f", User {user_token}" if user_token else "")
        self.h = {"Authorization": auth, "Accept": "application/vnd.yclients.v2+json",
                  "Content-Type": "application/json"}
        self.mirror = BASE_DIR / "yclients_bookings.json"
        if not self.mirror.exists():
            self.mirror.write_text("[]", encoding="utf-8")

    def _get(self, path: str, params: dict | None = None):
        r = requests.get(f"{self.API}{path}", headers=self.h, params=params, timeout=20)
        js = r.json() if r.content else {}
        if r.status_code != 200 or js.get("success") is False:
            raise BookingError(f"YCLIENTS {r.status_code}: {str(js)[:200]}")
        return js.get("data", js)

    def salon_info(self) -> dict:
        d = self._get(f"/company/{self.cid}")
        return {"name": d.get("title"), "address": d.get("address"), "phone": d.get("phone"),
                "work_hours": d.get("schedule"), "policies": "", "currency": d.get("currency_short_title", "")}

    def list_services(self) -> list[dict]:
        d = self._get(f"/book_services/{self.cid}")
        return [{"id": s["id"], "title": s["title"],
                 "price": f"{s.get('price_min')}–{s.get('price_max')}",
                 "duration_min": (s.get("seance_length") or 0) // 60} for s in d.get("services", [])]

    def list_masters(self, service_id: int | None = None) -> list[dict]:
        params = {"service_ids[]": service_id} if service_id else None
        d = self._get(f"/book_staff/{self.cid}", params)
        return [{"id": m["id"], "name": m["name"], "specialization": m.get("specialization", "")}
                for m in d if m.get("bookable", True)]

    def free_slots(self, service_id: int, date: str, master_id: int | None = None, now=None) -> list[dict]:
        masters = [{"id": master_id, "name": ""}] if master_id else self.list_masters(service_id)
        out = []
        for m in masters:
            d = self._get(f"/book_times/{self.cid}/{m['id']}/{date}", {"service_ids[]": service_id})
            times = [t["time"] for t in d]
            if times:
                out.append({"master_id": m["id"], "master": m["name"], "times": times})
        return out

    def create_booking(self, service_id: int, master_id: int, start: str,
                       client_name: str, client_phone: str, client_chat_id: str = "") -> dict:
        dt = datetime.strptime(start, "%Y-%m-%d %H:%M")
        body = {"phone": client_phone, "fullname": client_name, "email": "",
                "comment": "Запись через ИИ-администратора",
                "appointments": [{"id": 1, "services": [int(service_id)], "staff_id": int(master_id),
                                  "datetime": dt.strftime("%Y-%m-%dT%H:%M:%S")}]}
        r = requests.post(f"{self.API}/book_record/{self.cid}", headers=self.h, json=body, timeout=20)
        js = r.json() if r.content else {}
        if r.status_code not in (200, 201) or js.get("success") is False:
            raise BookingError(f"YCLIENTS не принял запись: {str(js)[:200]}")
        rec = (js.get("data") or [{}])[0]
        booking = {"id": rec.get("record_id"), "record_hash": rec.get("record_hash"),
                   "status": "active", "service_id": service_id, "master_id": master_id,
                   "start": start, "client_name": client_name, "client_phone": client_phone,
                   "client_chat_id": str(client_chat_id)}
        data = json.loads(self.mirror.read_text(encoding="utf-8"))
        data.append(booking)
        self.mirror.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return booking

    def client_bookings(self, client_chat_id: str) -> list[dict]:
        data = json.loads(self.mirror.read_text(encoding="utf-8"))
        return [b for b in data if b["client_chat_id"] == str(client_chat_id) and b["status"] == "active"]

    def cancel_booking(self, booking_id: int, client_chat_id: str) -> dict:
        raise BookingError("Отмену в YCLIENTS делает администратор — передаю запрос человеку")

    def reschedule_booking(self, booking_id: int, client_chat_id: str, new_start: str) -> dict:
        raise BookingError("Перенос в YCLIENTS делает администратор — передаю запрос человеку")
