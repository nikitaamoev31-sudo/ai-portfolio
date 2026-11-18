"""Build the database, run every query in queries/ and print the results.

    python analyze.py            # tables in the terminal
    python analyze.py --charts   # also save PNG charts to images/
"""
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "db" / "shop.db"


def build_db():
    subprocess.run([sys.executable, str(ROOT / "db" / "gen_data.py"), str(DB)], check=True)


def run_query(con, name):
    sql = (ROOT / "queries" / name).read_text()
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return cols, cur.fetchall()


def print_table(title, cols, rows, limit=12):
    print(f"\n### {title}")
    widths = [max(len(str(c)), *(len(str(r[i])) for r in rows[:limit])) for i, c in enumerate(cols)]
    print(" | ".join(str(c).ljust(w) for c, w in zip(cols, widths)))
    print("-+-".join("-" * w for w in widths))
    for r in rows[:limit]:
        print(" | ".join(str(v).ljust(w) for v, w in zip(r, widths)))
    if len(rows) > limit:
        print(f"... {len(rows) - limit} more rows")


def save_charts(con):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    (ROOT / "images").mkdir(exist_ok=True)
    _, rows = run_query(con, "01_monthly_revenue.sql")
    fig, ax = plt.subplots(figsize=(8, 3.5))
    ax.bar([r[0] for r in rows], [r[2] for r in rows], color="#4f7cff")
    ax.set_title("Net revenue by month (July 2026: site outage)")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig.savefig(ROOT / "images" / "monthly_revenue.png", dpi=120)

    _, rows = run_query(con, "05_channel_roas.sql")
    fig, ax = plt.subplots(figsize=(6, 3.2))
    colors = ["#2fbf71" if r[5] >= 1 else "#e5484d" for r in rows]
    ax.barh([r[0] for r in rows], [r[5] for r in rows], color=colors)
    ax.axvline(1, color="grey", linestyle="--")
    ax.set_title("ROAS by channel (below 1 = losing money)")
    fig.tight_layout()
    fig.savefig(ROOT / "images" / "channel_roas.png", dpi=120)
    print("\nCharts saved to images/")


def main():
    build_db()
    con = sqlite3.connect(DB)
    for path in sorted((ROOT / "queries").glob("*.sql")):
        cols, rows = run_query(con, path.name)
        print_table(path.stem, cols, rows)
    if "--charts" in sys.argv:
        save_charts(con)


if __name__ == "__main__":
    main()
