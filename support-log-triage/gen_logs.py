"""Генератор учебных логов онлайн-магазина за один день (детерминированный).

Пишет в logs/:
  access.log  — nginx combined + request_id и время ответа
  app.log     — логи приложения в JSON Lines (по одному событию на строку)
  auth.log    — попытки входа в личный кабинет

На фоне обычного трафика заложены инциденты, которые потом ищем:
  1. 14:02–14:09 — 5xx на POST /api/checkout: пул соединений к БД исчерпан
  2. 03:10–03:14 — подбор пароля к аккаунту с одного IP
  3. весь день   — медленный GET /api/orders/history у крупных аккаунтов
  4. 11:47:13    — платёж клиента ticket-заявителя упал по таймауту платёжного шлюза
"""
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)
DAY = datetime(2026, 11, 20)
OUT = Path(__file__).parent / "logs"

ENDPOINTS = [
    ("GET", "/api/products", 40, 120),
    ("GET", "/api/cart", 30, 90),
    ("POST", "/api/cart/items", 50, 150),
    ("POST", "/api/checkout", 180, 450),
    ("GET", "/api/orders/history", 80, 300),
    ("POST", "/api/login", 60, 160),
]
USERS = [f"u{n:04d}" for n in range(1, 301)]
BIG_ACCOUNTS = {"u0007", "u0042", "u0133"}  # у них тысячи заказов -> медленная история
IPS = [f"10.0.{random.randint(0, 9)}.{random.randint(2, 250)}" for _ in range(120)]
AGENT = "Mozilla/5.0"

_rid = 0


def next_rid():
    global _rid
    _rid += 1
    return f"req-{_rid:06d}"


def access_line(ts, ip, method, path, status, size, ms, rid):
    t = ts.strftime("%d/%b/%Y:%H:%M:%S +0400")
    return (f'{ip} - - [{t}] "{method} {path} HTTP/1.1" {status} {size} "-" "{AGENT}" '
            f'rt={ms / 1000:.3f} rid={rid}')


def app_line(ts, level, rid, user, msg, **extra):
    rec = {"ts": ts.strftime("%Y-%m-%dT%H:%M:%S"), "level": level, "request_id": rid,
           "user": user, "msg": msg}
    rec.update(extra)
    return json.dumps(rec, ensure_ascii=False)


def auth_line(ts, ip, user, ok):
    result = "success" if ok else "failure"
    return f"{ts.strftime('%Y-%m-%dT%H:%M:%S')} login {result} user={user} ip={ip}"


def main():
    OUT.mkdir(exist_ok=True)
    access, app, auth = [], [], []

    def request(ts, method, path, user, ip, status=200, ms=None, app_events=()):
        rid = next_rid()
        lo, hi = next((lo, hi) for m, p, lo, hi in ENDPOINTS if (m, p) == (method, path))
        ms = ms if ms is not None else random.randint(lo, hi)
        access.append((ts, access_line(ts, ip, method, path, status, random.randint(200, 4000), ms, rid)))
        app.append((ts, app_line(ts, "INFO", rid, user, f"{method} {path}", status=status, ms=ms)))
        for level, msg, extra in app_events:
            app.append((ts, app_line(ts, level, rid, user, msg, **extra)))
        return rid

    # фон: ~6000 запросов в рабочие часы и немного ночью
    for _ in range(6000):
        hour = random.choices(range(24), weights=[1] * 7 + [6] * 15 + [2] * 2)[0]
        ts = DAY + timedelta(hours=hour, seconds=random.randint(0, 3599))
        method, path, lo, hi = random.choice(ENDPOINTS)
        user, ip = random.choice(USERS), random.choice(IPS)
        if (method, path) == ("GET", "/api/orders/history") and user in BIG_ACCOUNTS:
            request(ts, method, path, user, ip, ms=random.randint(2400, 4200))
            continue
        if (method, path) == ("POST", "/api/login"):
            auth.append((ts, auth_line(ts, ip, user, random.random() > 0.03)))
        if (method, path) == ("POST", "/api/checkout") and 14 * 60 + 2 <= hour * 60 + ts.minute < 14 * 60 + 10:
            continue  # окно инцидента 1 заполняем отдельно
        request(ts, method, path, user, ip)

    # инцидент 1: исчерпан пул соединений к БД на checkout
    for i in range(48):
        ts = DAY + timedelta(hours=14, minutes=2, seconds=i * 9 + random.randint(0, 5))
        user, ip = random.choice(USERS), random.choice(IPS)
        request(ts, "POST", "/api/checkout", user, ip, status=503, ms=random.randint(5000, 5100),
                app_events=[("ERROR", "db pool exhausted", {"pool_size": 20, "waited_ms": 5000})])

    # инцидент 2: подбор пароля к u0088 с одного IP
    attacker = "185.220.101.47"
    for i in range(37):
        ts = DAY + timedelta(hours=3, minutes=10, seconds=i * 7)
        auth.append((ts, auth_line(ts, attacker, "u0088", False)))
        request(ts, "POST", "/api/login", "u0088", attacker, status=401)
    lock_ts = DAY + timedelta(hours=3, minutes=14, seconds=21)
    app.append((lock_ts, app_line(lock_ts, "WARN", "-", "u0088", "account locked", reason="too many failed logins")))

    # инцидент 4: тикет клиента u0215 — «деньги списались, а заказа нет»
    ts = DAY + timedelta(hours=11, minutes=47, seconds=13)
    request(ts, "POST", "/api/checkout", "u0215", "10.0.4.77", status=502, ms=30012, app_events=[
        ("ERROR", "payment gateway timeout", {"gateway": "payprovider", "order_id": "ORD-55871", "amount": 89.90}),
        ("WARN", "order rolled back, payment hold not released", {"order_id": "ORD-55871"}),
    ])

    for name, rows in (("access.log", access), ("app.log", app), ("auth.log", auth)):
        rows.sort(key=lambda r: r[0])
        (OUT / name).write_text("\n".join(line for _, line in rows) + "\n", encoding="utf-8")
    print(f"access={len(access)} app={len(app)} auth={len(auth)} lines -> {OUT}")


if __name__ == "__main__":
    main()
