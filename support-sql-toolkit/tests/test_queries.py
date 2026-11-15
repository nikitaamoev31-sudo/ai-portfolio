"""Каждый тест проверяет, что запрос находит заложенный в seed инцидент — и только его."""


def test_double_charge_found(run_query):
    rows = run_query("01_double_charges.sql")
    assert len(rows) == 1
    r = rows[0]
    assert r["customer_id"] == 3
    assert (r["first_txn"], r["duplicate_txn"]) == ("pay_990001", "pay_990002")
    assert r["seconds_between"] == 40


def test_paid_but_subscription_not_renewed(run_query):
    rows = run_query("02_paid_but_blocked.sql")
    assert [(r["customer_id"], r["subscription_status"], r["provider_txn_id"]) for r in rows] == [
        (5, "past_due", "pay_990003")
    ]


def test_bruteforce_lockout(run_query):
    rows = run_query("03_login_lockouts.sql")
    assert len(rows) == 1
    r = rows[0]
    assert r["customer_id"] == 7
    assert r["wrong_password_attempts"] == 6
    assert r["distinct_ips"] == 2


def test_api_500_spike_after_release(run_query):
    rows = run_query("04_api_errors_by_window.sql")
    assert len(rows) == 1
    r = rows[0]
    assert r["endpoint"] == "/v1/bookings"
    assert str(r["window_start"]) == "2026-11-10 14:00:00"
    assert r["errors_5xx"] >= 60
    assert r["affected_customers"] > 10


def test_staff_limit_bug_vs_expected_limit(run_query):
    rows = run_query("05_staff_limit.sql")
    states = {r["customer_id"]: r["state"] for r in rows}
    assert states[11] == "over_limit"      # лимит не сработал — баг
    assert states[9] == "at_limit"         # клиент из тикета упёрся в лимит тарифа
    assert list(states.values()).count("over_limit") == 1


def test_sla_breaches_include_unanswered_urgent(run_query):
    rows = run_query("06_sla_breaches.sql")
    ids = [r["ticket_id"] for r in rows]
    unanswered = [r for r in rows if r["status"] != "resolved" and r["agent"] is None]
    assert {r["subject"] for r in unanswered} == {
        "Записи с сайта не создаются, ошибка 500",
        "Виджет записи выдаёт ошибку",
    }
    assert rows[0]["status"] != "resolved"  # открытые нарушения — в начале отчёта
    assert len(ids) == len(set(ids))


def test_agent_kpi_covers_all_agents(run_query):
    rows = run_query("07_agent_kpi.sql")
    assert {r["full_name"] for r in rows} == {"Анна Смирнова", "Игорь Ким", "Мария Орлова", "Денис Волков"}
    for r in rows:
        assert 0 <= r["sla_met_pct"] <= 100
        assert 1 <= r["avg_csat"] <= 5
    assert [r["sla_met_pct"] for r in rows] == sorted((r["sla_met_pct"] for r in rows), reverse=True)


def test_open_queue_unassigned_urgent_first(run_query):
    rows = run_query("08_open_queue.sql")
    assert len(rows) == 6
    assert rows[0]["agent"] == "— не назначен —"
    assert rows[0]["priority"] == "urgent"
    assert rows[0]["mins_to_first_response_sla"] < 0
