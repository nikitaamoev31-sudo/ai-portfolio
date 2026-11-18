"""Every query is checked against facts planted in db/gen_data.py."""
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def con(tmp_path_factory):
    db = tmp_path_factory.mktemp("db") / "shop.db"
    subprocess.run([sys.executable, str(ROOT / "db" / "gen_data.py"), str(db)], check=True)
    connection = sqlite3.connect(db)
    yield connection
    connection.close()


def q(con, name):
    cur = con.execute((ROOT / "queries" / name).read_text())
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def test_data_is_deterministic(con):
    counts = [con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("customers", "orders", "order_items")]
    assert counts == [2712, 5322, 8577]


def test_monthly_revenue_shows_july_outage_and_recovery(con):
    rows = {r["month"]: r for r in q(con, "01_monthly_revenue.sql")}
    assert len(rows) == 12
    assert rows["2025-12"]["mom_growth_pct"] is None
    assert rows["2026-07"]["mom_growth_pct"] < -25
    assert rows["2026-08"]["mom_growth_pct"] > 100
    worst = min((r for m, r in rows.items() if m != "2025-12"), key=lambda r: r["mom_growth_pct"])
    assert worst["month"] == "2026-07"


def test_revenue_matches_raw_data(con):
    total = sum(r["net_revenue"] for r in q(con, "01_monthly_revenue.sql"))
    raw = con.execute("SELECT SUM(unit_price * qty) FROM order_items WHERE returned = 0").fetchone()[0]
    assert total == pytest.approx(raw, abs=0.1)


def test_cohort_retention_hides_future_months(con):
    rows = {r["cohort"]: r for r in q(con, "02_cohort_retention.sql")}
    assert rows["2026-11"]["m1_pct"] is None
    assert rows["2026-10"]["m2_pct"] is None and rows["2026-10"]["m1_pct"] is not None
    assert all(0 <= r["m1_pct"] <= 100 for r in rows.values() if r["m1_pct"] is not None)


def test_abc_classes_follow_cumulative_share(con):
    rows = q(con, "03_abc_analysis.sql")
    assert len(rows) == 60
    assert rows[0]["abc_class"] == "A" and rows[-1]["abc_class"] == "C"
    assert rows[-1]["cum_share_pct"] == pytest.approx(100.0)
    classes = [r["abc_class"] for r in rows]
    assert classes == sorted(classes)  # A..., then B..., then C...


def test_rfm_covers_every_buyer_once(con):
    buyers = con.execute("SELECT COUNT(DISTINCT customer_id) FROM orders").fetchone()[0]
    assert sum(r["customers"] for r in q(con, "04_rfm_segments.sql")) == buyers


def test_influencers_channel_loses_money(con):
    rows = {r["channel"]: r for r in q(con, "05_channel_roas.sql")}
    assert rows["influencers"]["roas"] < 1
    assert all(r["roas"] > 1 for ch, r in rows.items() if ch != "influencers")
    assert rows["influencers"]["cac"] == max(r["cac"] for r in rows.values())


def test_headphones_have_highest_return_rate(con):
    rows = q(con, "06_returns_by_category.sql")
    assert rows[0]["category"] == "Headphones"
    assert rows[0]["return_rate_pct"] > 15
    assert rows[1]["return_rate_pct"] < 10
