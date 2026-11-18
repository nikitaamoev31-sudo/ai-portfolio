import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8080").rstrip("/")
API = f"{BASE_URL}/api/applications"


@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers["Content-Type"] = "application/json"
    try:
        s.get(f"{API}/stats", timeout=5).raise_for_status()
    except requests.RequestException as e:
        pytest.exit(f"API is not reachable at {BASE_URL}: {e}", returncode=2)
    return s


@pytest.fixture
def unique():
    """Unique company name so tests never depend on each other's data."""
    return f"QA-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def create(api):
    created = []

    def _create(**overrides):
        body = {"company": "Acme", "position": "Support Engineer"} | overrides
        r = api.post(API, json=body)
        assert r.status_code == 201, r.text
        created.append(r.json()["id"])
        return r.json()

    yield _create
    for id_ in created:
        api.delete(f"{API}/{id_}")


def items(page_json):
    return page_json["content"]


def total(page_json):
    if "page" in page_json:  # Spring Data 3.3+ DTO page format
        return page_json["page"]["totalElements"]
    return page_json["totalElements"]
