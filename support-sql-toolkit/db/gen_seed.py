"""Генерирует db/seed.sql: фоновые данные + специально заложенные инциденты.

Данные детерминированы (random.seed), поэтому тесты всегда видят один и тот же результат.
Запуск: python db/gen_seed.py > db/seed.sql
"""
import random
from datetime import datetime, timedelta

random.seed(42)
NOW = datetime(2026, 11, 10, 18, 0)  # «текущее время» учебной базы, см. helpdesk.report_now()

out = ["SET search_path TO helpdesk;", ""]


def q(v):
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, datetime):
        return f"'{v:%Y-%m-%d %H:%M:%S}'"
    return "'" + str(v).replace("'", "''") + "'"


def insert(table, cols, rows):
    out.append(f"INSERT INTO {table} ({', '.join(cols)}) VALUES")
    out.append(",\n".join("  (" + ", ".join(q(v) for v in r) + ")" for r in rows) + ";")
    out.append("")


out.append("CREATE OR REPLACE FUNCTION report_now() RETURNS timestamp LANGUAGE sql IMMUTABLE AS "
           f"$$ SELECT {q(NOW)}::timestamp $$;  -- в проде заменить на now()")
out.append("")

insert("plans", ["code", "name", "price_monthly", "max_staff"], [
    ("start", "Старт", 990, 3), ("pro", "Профи", 2490, 10), ("business", "Бизнес", 5990, 50)])

insert("sla_policies", ["priority", "first_response_mins", "resolution_hours"], [
    ("low", 480, 72), ("normal", 120, 24), ("high", 30, 8), ("urgent", 15, 4)])

insert("agents", ["full_name", "line"], [
    ("Анна Смирнова", "L1"), ("Игорь Ким", "L1"), ("Мария Орлова", "L1"), ("Денис Волков", "L2")])

companies = [
    "Салон «Лаванда»", "Студия йоги «Прана»", "Барбершоп «Борода»", "Клиника «Дента Плюс»",
    "Фитнес «Атлант»", "Студия маникюра «Nail Lab»", "Автосервис «Гараж 24»", "Массаж «Релакс»",
    "Школа танцев «Ритм»", "Ветклиника «Хвост»", "Психолог Елена Миронова", "Тату-студия «Ink»",
    "Салон «Шарм»", "Косметология «Glow»", "Репетитор Олег Павлов", "Фотостудия «Кадр»",
    "Спа «Лотос»", "Груминг «Пушистик»", "Детский центр «Умка»", "Стоматология «Улыбка»",
]
countries = ["Россия"] * 12 + ["Казахстан"] * 3 + ["Беларусь"] * 2 + ["Грузия"] * 2 + ["Армения"]
customers = []
for i, c in enumerate(companies, start=1):
    customers.append((c, f"owner{i}@client{i}.example", countries[i - 1],
                      NOW - timedelta(days=random.randint(60, 600))))
insert("customers", ["company", "email", "country", "created_at"], customers)

# --- подписки ---------------------------------------------------------------
plan_of = {}
subs = []
for cid in range(1, 21):
    plan = random.choice([1, 1, 2, 2, 2, 3])
    plan_of[cid] = plan
    status, paid_until = "active", (NOW + timedelta(days=random.randint(3, 28))).date()
    if cid == 5:          # ИНЦИДЕНТ: оплата прошла, а подписка осталась past_due
        plan, status, paid_until = 2, "past_due", datetime(2026, 11, 7).date()
        plan_of[cid] = plan
    if cid in (9, 11):    # лимиты сотрудников: тариф «Старт»
        plan = plan_of[cid] = 1
    if cid == 18:
        status, paid_until = "cancelled", datetime(2026, 10, 1).date()
    if cid == 20:
        status, paid_until = "trial", None
    subs.append((cid, plan, status, NOW - timedelta(days=random.randint(30, 300)), paid_until))
out.append("INSERT INTO subscriptions (customer_id, plan_id, status, started_at, paid_until) VALUES")
out.append(",\n".join(
    f"  ({c}, {p}, {q(s)}, {q(st)}, {q(str(pu)) if pu else 'NULL'})" for c, p, s, st, pu in subs) + ";")
out.append("")

# --- оплаты -----------------------------------------------------------------
prices = {1: 990, 2: 2490, 3: 5990}
pays = []
txn = 100000
for cid in range(1, 21):
    if cid == 20:
        continue
    for m in range(4):
        txn += 1
        when = NOW - timedelta(days=30 * m + random.randint(1, 5), hours=random.randint(0, 10))
        status = "failed" if random.random() < 0.07 else "succeeded"
        if cid == 18 and when >= datetime(2026, 10, 1):
            continue  # подписка отменена — оплат после отмены нет
        pays.append((cid, prices[plan_of[cid]], status, f"pay_{txn}", when))
# ИНЦИДЕНТ: двойное списание у «Бороды» (cid 3) — два успешных платежа за 40 секунд
pays.append((3, prices[plan_of[3]], "succeeded", "pay_990001", datetime(2026, 11, 9, 11, 15, 2)))
pays.append((3, prices[plan_of[3]], "succeeded", "pay_990002", datetime(2026, 11, 9, 11, 15, 42)))
# ИНЦИДЕНТ: оплата cid 5 прошла, а подписка не продлилась
pays.append((5, 2490, "succeeded", "pay_990003", datetime(2026, 11, 8, 9, 30, 0)))
insert("payments", ["customer_id", "amount", "status", "provider_txn_id", "created_at"], pays)

# --- сотрудники клиентов ------------------------------------------------------
first = ["Алина", "Ольга", "Сергей", "Ирина", "Павел", "Наталья", "Артём", "Юлия", "Максим", "Ксения"]
last = ["Иванова", "Петрова", "Соколов", "Кузнецова", "Попов", "Лебедева", "Новиков", "Морозова"]
staff = []
for cid in range(1, 21):
    n = {9: 3, 11: 5}.get(cid, random.randint(1, {1: 3, 2: 8, 3: 20}[plan_of[cid]]))
    for _ in range(n):
        staff.append((cid, f"{random.choice(first)} {random.choice(last)}", True))
insert("staff", ["customer_id", "full_name", "is_active"], staff)

# --- входы ------------------------------------------------------------------
logins = []
for _ in range(300):
    cid = random.randint(1, 20)
    ok = random.random() > 0.06
    logins.append((cid, ok, None if ok else "wrong_password",
                   f"185.{random.randint(1, 250)}.{random.randint(1, 250)}.{random.randint(1, 250)}",
                   NOW - timedelta(days=random.randint(0, 14), minutes=random.randint(0, 1440))))
# ИНЦИДЕНТ: подбор пароля у «Гараж 24» (cid 7) — 6 неудачных попыток за 4 минуты, затем блокировка
t0 = datetime(2026, 11, 10, 9, 41, 0)
for k in range(6):
    logins.append((7, False, "wrong_password", "91.204.17.88", t0 + timedelta(seconds=40 * k)))
logins.append((7, False, "locked", "91.204.17.88", t0 + timedelta(seconds=250)))
logins.append((7, False, "locked", "78.40.12.5", datetime(2026, 11, 10, 10, 5)))  # сам владелец не может войти
insert("login_events", ["customer_id", "success", "reason", "ip", "created_at"], logins)

# --- запросы к API -----------------------------------------------------------
endpoints = ["/v1/bookings", "/v1/clients", "/v1/services", "/v1/staff"]
api = []
for _ in range(1500):
    when = NOW - timedelta(minutes=random.randint(0, 60 * 24 * 3))
    code = random.choices([200, 201, 400, 401, 404, 500], [70, 10, 6, 3, 9, 2])[0]
    api.append((random.randint(1, 20), random.choice(endpoints), code, random.randint(40, 400), when))
# ИНЦИДЕНТ: всплеск 500 на /v1/bookings 10.11 с 14:00 до 14:30 после релиза
for _ in range(60):
    when = datetime(2026, 11, 10, 14, 0) + timedelta(seconds=random.randint(0, 1799))
    api.append((random.randint(1, 20), "/v1/bookings", 500, random.randint(2500, 9000), when))
insert("api_requests", ["customer_id", "endpoint", "status_code", "latency_ms", "created_at"], api)

# --- тикеты -----------------------------------------------------------------
sla = {"low": 480, "normal": 120, "high": 30, "urgent": 15}
subjects = {
    "billing": ["Не прошла оплата", "Нужны закрывающие документы", "Как сменить тариф"],
    "login": ["Не приходит письмо для сброса пароля", "Не могу войти"],
    "integration": ["Не работает виджет на сайте", "Ошибка в API", "Не приходят вебхуки"],
    "booking": ["Клиенты не видят свободное время", "Дублируются записи"],
    "other": ["Как выгрузить клиентов в Excel", "Вопрос по настройке уведомлений"],
}
tickets = []
for _ in range(120):
    cat = random.choice(list(subjects))
    pr = random.choices(["low", "normal", "high", "urgent"], [25, 50, 20, 5])[0]
    created = NOW - timedelta(days=random.randint(1, 30), minutes=random.randint(0, 1440))
    breach = random.random() < 0.15
    fr = created + timedelta(minutes=sla[pr] * (random.uniform(1.2, 3) if breach else random.uniform(0.1, 0.9)))
    resolved = fr + timedelta(hours=random.uniform(0.5, 30))
    tickets.append((random.randint(1, 20), random.randint(1, 4), random.choice(subjects[cat]), cat, pr,
                    "resolved", created, fr, resolved, random.choices([5, 4, 3, 2, 1], [55, 25, 10, 6, 4])[0]))
# Открытые тикеты по заложенным инцидентам
tickets += [
    (3, 1, "Списали деньги два раза!", "billing", "high", "open",
     datetime(2026, 11, 9, 12, 2), None, None, None),
    (5, 2, "Оплатил, а доступ заблокирован", "billing", "urgent", "open",
     datetime(2026, 11, 10, 8, 50), datetime(2026, 11, 10, 9, 20), None, None),
    (7, 3, "Не могу войти в аккаунт", "login", "high", "open",
     datetime(2026, 11, 10, 10, 7), datetime(2026, 11, 10, 10, 15), None, None),
    (9, 1, "Не могу добавить четвёртого мастера", "other", "normal", "pending",
     datetime(2026, 11, 10, 11, 0), datetime(2026, 11, 10, 11, 40), None, None),
    (12, None, "Записи с сайта не создаются, ошибка 500", "integration", "urgent", "open",
     datetime(2026, 11, 10, 14, 12), None, None, None),
    (16, None, "Виджет записи выдаёт ошибку", "integration", "high", "open",
     datetime(2026, 11, 10, 14, 20), None, None, None),
]
insert("tickets", ["customer_id", "agent_id", "subject", "category", "priority", "status",
                   "created_at", "first_response_at", "resolved_at", "csat"], tickets)

print("\n".join(out))
