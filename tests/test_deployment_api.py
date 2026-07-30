# Tests the deployment backend health and provider-independent fixture endpoints.
from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from evidencecast.deployment import normalise_api_url


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Create the ASGI test client inside each test lifecycle."""

    with TestClient(app) as test_client:
        yield test_client


def test_health_and_readiness_endpoints(client: TestClient) -> None:
    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["fixture_mode"] is True

    readiness = client.get("/readyz")
    assert readiness.status_code == 200
    assert readiness.json()["status"] == "ready"
    assert readiness.json()["fixture_count"] == 3


def test_fixture_catalogue_and_detail_endpoints(client: TestClient) -> None:
    catalogue = client.get("/api/v1/fixtures")
    assert catalogue.status_code == 200
    payload = catalogue.json()
    assert payload["count"] == 3

    for item in payload["fixtures"]:
        detail = client.get(f"/api/v1/fixtures/{item['fixture_id']}")
        assert detail.status_code == 200
        workflow = detail.json()
        assert workflow["storyboard"]["scene_count"] == 3
        assert workflow["narration"]["segment_count"] == 3
        assert all(card["status"] == "approved" for card in workflow["review"]["cards"])


def test_unknown_fixture_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/fixtures/does-not-exist")
    assert response.status_code == 404
    assert "Unknown fixture" in response.json()["detail"]


def test_render_hostport_is_normalised_to_http_url() -> None:
    assert normalise_api_url("evidencecast-api:10000") == "http://evidencecast-api:10000/"
    assert normalise_api_url("https://example.test/api") == "https://example.test/api/"
