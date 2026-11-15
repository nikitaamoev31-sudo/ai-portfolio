import os
from pathlib import Path

import psycopg
import pytest

ROOT = Path(__file__).resolve().parent.parent
DSN = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/helpdesk")


@pytest.fixture(scope="session")
def db():
    """Пересоздаёт схему helpdesk из db/schema.sql + db/seed.sql и отдаёт соединение."""
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))
        conn.execute((ROOT / "db" / "seed.sql").read_text(encoding="utf-8"))
        yield conn


@pytest.fixture
def run_query(db):
    """Выполняет файл из queries/ и возвращает строки как список dict."""
    def _run(name):
        sql = (ROOT / "queries" / name).read_text(encoding="utf-8")
        cur = db.execute(sql)
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    return _run
