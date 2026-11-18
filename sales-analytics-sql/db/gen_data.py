"""Generate a deterministic synthetic dataset of an online store (12 months).

Planted facts the analysis must find (checked by tests):
- "Headphones" has the highest return rate (~20%).
- The "influencers" ad channel has ROAS < 1 (loses money).
- July 2026 revenue dips (site outage week), August recovers.
"""
import random
import sqlite3
import sys
from datetime import date
from pathlib import Path

random.seed(42)
DB = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("shop.db")

CATEGORIES = {  # category: (price range, return probability)
    "Smartphones": ((250, 900), 0.05),
    "Headphones": ((30, 250), 0.20),
    "Laptops": ((600, 1800), 0.04),
    "Accessories": ((5, 60), 0.03),
    "Smart home": ((20, 200), 0.06),
}
CHANNELS = {  # channel: (monthly spend, share of new customers)
    "search": (6000, 0.40),
    "social": (4000, 0.30),
    "email": (500, 0.20),
    "influencers": (14000, 0.10),
}
START = date(2025, 12, 1)
MONTHS = [(START.year + (START.month - 1 + i) // 12, (START.month - 1 + i) % 12 + 1) for i in range(12)]


def main():
    DB.unlink(missing_ok=True)
    con = sqlite3.connect(DB)
    con.executescript(Path(__file__).with_name("schema.sql").read_text())

    products = []
    pid = 1
    for cat, ((lo, hi), _) in CATEGORIES.items():
        for n in range(1, 13):
            products.append((pid, f"{cat} #{n}", cat, round(random.uniform(lo, hi), 2)))
            pid += 1
    con.executemany("INSERT INTO products VALUES (?,?,?,?)", products)
    weights = [1 / p[3] ** 0.5 for p in products]  # cheaper items sell more often

    customers, orders, items = [], [], []
    oid = iid = 0
    for m_idx, (y, m) in enumerate(MONTHS):
        new = 160 + m_idx * 12
        chans = random.choices(list(CHANNELS), weights=[c[1] for c in CHANNELS.values()], k=new)
        for ch in chans:
            day = date(y, m, random.randint(1, 28))
            customers.append((len(customers) + 1, day.isoformat(), ch))
        for cid, signup, ch in customers:
            signup_d = date.fromisoformat(signup)
            if (signup_d.year, signup_d.month) > (y, m):
                continue
            first_month = (signup_d.year, signup_d.month) == (y, m)
            p_buy = 1.0 if first_month else 0.22
            if (y, m) == (2026, 7):
                p_buy *= 0.6  # outage week: fewer orders
            if random.random() > p_buy:
                continue
            day = signup_d if first_month else date(y, m, random.randint(1, 28))
            oid += 1
            orders.append((oid, cid, day.isoformat()))
            for prod in random.choices(products, weights=weights, k=random.choice([1, 1, 1, 2, 3])):
                iid += 1
                returned = int(random.random() < CATEGORIES[prod[2]][1])
                items.append((iid, oid, prod[0], 1, prod[3], returned))

    spend = [(f"{y}-{m:02d}", ch, round(v[0] * random.uniform(0.9, 1.1), 2))
             for (y, m) in MONTHS for ch, v in CHANNELS.items()]
    con.executemany("INSERT INTO customers VALUES (?,?,?)", customers)
    con.executemany("INSERT INTO orders VALUES (?,?,?)", orders)
    con.executemany("INSERT INTO order_items VALUES (?,?,?,?,?,?)", items)
    con.executemany("INSERT INTO ad_spend VALUES (?,?,?)", spend)
    con.commit()
    print(f"{DB.name}: {len(customers)} customers, {len(orders)} orders, {len(items)} items")


if __name__ == "__main__":
    main()
