"""Happy paths: create, read, update, change status, delete."""
from datetime import date

from conftest import API, items, total


def test_create_returns_201_with_defaults(create):
    app = create(company="Acme", position="QA Engineer")
    assert isinstance(app["id"], int)
    assert app["status"] == "FOUND"            # default status
    assert app["appliedAt"] is None
    assert app["createdAt"] and app["updatedAt"]


def test_get_by_id_returns_same_record(api, create):
    app = create(salaryUsd=1200, notes="remote")
    r = api.get(f"{API}/{app['id']}")
    assert r.status_code == 200
    assert r.json()["salaryUsd"] == 1200 and r.json()["notes"] == "remote"


def test_put_replaces_fields(api, create):
    app = create()
    body = {"company": "Acme", "position": "Senior QA", "status": "INTERVIEW", "salaryUsd": 1500}
    r = api.put(f"{API}/{app['id']}", json=body)
    assert r.status_code == 200
    assert r.json()["position"] == "Senior QA" and r.json()["status"] == "INTERVIEW"


def test_patch_to_applied_sets_today_as_applied_date(api, create):
    app = create()
    r = api.patch(f"{API}/{app['id']}/status", json={"status": "APPLIED"})
    assert r.status_code == 200
    assert r.json()["status"] == "APPLIED"
    assert r.json()["appliedAt"] == date.today().isoformat()


def test_patch_keeps_existing_applied_date(api, create):
    app = create(appliedAt="2026-01-10")
    r = api.patch(f"{API}/{app['id']}/status", json={"status": "APPLIED"})
    assert r.json()["appliedAt"] == "2026-01-10"


def test_delete_returns_204_and_record_is_gone(api):
    app_id = api.post(API, json={"company": "Temp", "position": "X"}).json()["id"]
    assert api.delete(f"{API}/{app_id}").status_code == 204
    assert api.get(f"{API}/{app_id}").status_code == 404


def test_filter_by_status(api, create, unique):
    create(company=unique, status="OFFER")
    r = api.get(API, params={"status": "OFFER", "size": 200})
    assert r.status_code == 200
    assert all(a["status"] == "OFFER" for a in items(r.json()))
    assert any(a["company"] == unique for a in items(r.json()))


def test_filter_by_company_is_case_insensitive(api, create, unique):
    create(company=unique)
    r = api.get(API, params={"company": unique.lower()})
    assert [a["company"] for a in items(r.json())] == [unique]


def test_pagination(api, create, unique):
    for i in range(3):
        create(company=unique, position=f"Role {i}")
    r = api.get(API, params={"company": unique, "size": 2, "page": 0})
    assert len(items(r.json())) == 2 and total(r.json()) == 3
    r = api.get(API, params={"company": unique, "size": 2, "page": 1})
    assert len(items(r.json())) == 1


def test_stats_count_new_records(api, create):
    before = api.get(f"{API}/stats").json()
    create(status="INTERVIEW")
    create(status="APPLIED")
    after = api.get(f"{API}/stats").json()
    assert after["total"] == before["total"] + 2
    assert after["byStatus"]["INTERVIEW"] == before["byStatus"]["INTERVIEW"] + 1
    assert set(after["byStatus"]) == {"FOUND", "APPLIED", "TEST_TASK", "INTERVIEW", "OFFER", "REJECTED"}
    assert 0 <= after["responseRate"] <= 100
