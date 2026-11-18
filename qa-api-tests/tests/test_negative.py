"""Validation and error handling."""
import pytest

from conftest import API


@pytest.mark.parametrize("body, field", [
    ({"position": "QA"}, "company"),
    ({"company": "   ", "position": "QA"}, "company"),
    ({"company": "Acme"}, "position"),
    ({"company": "Acme", "position": "QA", "salaryUsd": -1}, "salaryUsd"),
    ({"company": "A" * 256, "position": "QA"}, "company"),
    ({"company": "Acme", "position": "QA", "notes": "x" * 2001}, "notes"),
])
def test_invalid_body_returns_400_with_field_error(api, body, field):
    r = api.post(API, json=body)
    assert r.status_code == 400
    assert field in r.json()["errors"]


def test_unknown_status_value_is_rejected(api):
    r = api.post(API, json={"company": "Acme", "position": "QA", "status": "HIRED"})
    assert r.status_code == 400


def test_patch_without_status_is_rejected(api, create):
    app = create()
    r = api.patch(f"{API}/{app['id']}/status", json={})
    assert r.status_code == 400


def test_malformed_json_returns_400(api):
    r = api.post(API, data="{not json")
    assert r.status_code == 400


@pytest.mark.parametrize("method", ["get", "delete"])
def test_unknown_id_returns_404_problem_detail(api, method):
    r = getattr(api, method)(f"{API}/999999999")
    assert r.status_code == 404
    assert r.json()["detail"] == "Job application 999999999 not found"


def test_unknown_status_filter_returns_400_not_500(api):
    assert api.get(API, params={"status": "nope"}).status_code == 400
