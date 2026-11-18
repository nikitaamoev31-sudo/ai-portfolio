"""Defects found during exploratory testing (see bug-reports.md).

Marked xfail(strict=True): CI stays green while the bug exists and turns red
as soon as it is fixed — a reminder to close the ticket and drop the marker.
"""
from datetime import date, timedelta

import pytest

from conftest import API, items


@pytest.mark.xfail(strict=True, reason="BUG-1: status and company filters cannot be combined")
def test_status_and_company_filters_combine(api, create, unique):
    create(company=unique, status="OFFER")
    create(company="Other-company", status="OFFER")
    r = api.get(API, params={"status": "OFFER", "company": unique, "size": 200})
    assert [a["company"] for a in items(r.json())] == [unique]


@pytest.mark.xfail(strict=True, reason="BUG-2: applied date in the future is accepted")
def test_future_applied_date_is_rejected(api):
    future = (date.today() + timedelta(days=30)).isoformat()
    r = api.post(API, json={"company": "Acme", "position": "QA", "appliedAt": future})
    if r.status_code == 201:
        api.delete(f"{API}/{r.json()['id']}")
    assert r.status_code == 400


@pytest.mark.xfail(strict=True, reason="BUG-3: PUT without status silently resets it to FOUND")
def test_put_without_status_keeps_current_status(api, create):
    app = create(status="INTERVIEW")
    r = api.put(f"{API}/{app['id']}", json={"company": "Acme", "position": "QA", "notes": "call on Friday"})
    assert r.json()["status"] == "INTERVIEW"
