"""Каждый тест проверяет, что разбор находит именно заложенный инцидент и не даёт ложных срабатываний."""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import triage  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def logs():
    subprocess.run([sys.executable, str(ROOT / "gen_logs.py")], check=True, capture_output=True)


@pytest.fixture(scope="session")
def access(logs):
    return triage.read_access()


@pytest.fixture(scope="session")
def app(logs):
    return triage.read_app()


def test_all_access_lines_parsed(access):
    raw = (ROOT / "logs" / "access.log").read_text(encoding="utf-8").splitlines()
    assert len(access) == len(raw) == 6078


def test_checkout_incident_is_one_burst(access):
    bursts = triage.error_bursts(access)
    assert len(bursts) == 1
    b = bursts[0]
    assert (b["endpoint"], b["errors"], b["from"], b["to"]) == ("POST /api/checkout", 48, "14:02:00", "14:09:08")
    assert b["statuses"] == {503: 48}


def test_single_error_is_not_an_incident(access):
    # одиночный 502 клиента u0215 — это тикет, а не массовый сбой
    assert all(b["errors"] >= 5 for b in triage.error_bursts(access))
    assert any(r["status"] == 502 for r in access)


def test_incident_root_cause_in_app_log(app):
    msgs = {e["msg"] for e in app if e["level"] == "ERROR" and "14:02" <= e["ts"][11:16] <= "14:09"}
    assert msgs == {"db pool exhausted"}


def test_slow_history_only_for_big_accounts(access, app):
    slow = triage.slow_for_users(access, app)
    assert {s["user"] for s in slow} == {"u0007", "u0042", "u0133"}
    assert all(s["endpoint"] == "GET /api/orders/history" for s in slow)
    assert all(s["endpoint_p95_ms"] < 1000 for s in slow)  # в среднем по сервису всё нормально


def test_bruteforce_detects_only_attacker():
    found = triage.bruteforce(triage.read_auth())
    assert [(f["ip"], f["failures"], f["users"]) for f in found] == [("185.220.101.47", 37, ["u0088"])]


def test_ticket_u0215_payment_hold(app):
    events = triage.user_activity(app, "u0215")
    assert [e["msg"] for e in events if e["level"] != "INFO"] == [
        "payment gateway timeout", "order rolled back, payment hold not released"]
    assert {e.get("order_id") for e in events if e["level"] != "INFO"} == {"ORD-55871"}


def test_trace_links_nginx_and_app(access, app):
    t = triage.trace(access, app, "req-006078")
    assert [r["status"] for r in t["access"]] == [502]
    assert t["access"][0]["ms"] == 30012
    assert len(t["app"]) == 3


def test_playbook_runs_and_agrees():
    out = subprocess.run(["bash", str(ROOT / "playbook.sh")], check=True, capture_output=True, text=True).stdout
    assert "48 POST /api/checkout 503" in out
    assert "48 db pool exhausted" in out
    assert "37 ip=185.220.101.47" in out
