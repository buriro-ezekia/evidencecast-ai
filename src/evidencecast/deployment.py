# Provides frontend helpers for deployment health checks and fixture retrieval.
from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from .fixtures import build_fixture_workflow, list_fixture_reports


class DeploymentClientError(RuntimeError):
    """Raised when the deployed backend cannot satisfy a frontend request."""


def normalise_api_url(value: str | None = None) -> str:
    raw = (value if value is not None else os.getenv("EVIDENCECAST_API_URL", "http://localhost:8000")).strip()
    if not raw:
        raw = "http://localhost:8000"
    if "://" not in raw:
        raw = f"http://{raw}"
    return raw.rstrip("/") + "/"


def fetch_backend_json(path: str, *, timeout_seconds: float = 10.0) -> dict[str, Any]:
    base_url = normalise_api_url()
    url = urljoin(base_url, path.lstrip("/"))
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "EvidenceCast/1.0"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise DeploymentClientError(f"Backend returned HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise DeploymentClientError(f"Could not reach EvidenceCast backend at {url}: {exc}") from exc
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise DeploymentClientError("Backend returned invalid JSON.") from exc
    if not isinstance(value, dict):
        raise DeploymentClientError("Backend JSON response must be an object.")
    return value


def get_fixture_catalogue() -> tuple[list[dict[str, Any]], str]:
    """Return fixtures from the backend, falling back to bundled local fixtures."""

    try:
        payload = fetch_backend_json("/api/v1/fixtures")
        fixtures = payload.get("fixtures", [])
        if not isinstance(fixtures, list) or not fixtures:
            raise DeploymentClientError("Backend fixture catalogue is empty.")
        return fixtures, "backend"
    except DeploymentClientError:
        return list_fixture_reports(), "bundled fallback"


def get_fixture_workflow(fixture_id: str) -> tuple[dict[str, Any], str]:
    """Return one workflow from the backend, falling back to the bundled copy."""

    try:
        return fetch_backend_json(f"/api/v1/fixtures/{fixture_id}"), "backend"
    except DeploymentClientError:
        return build_fixture_workflow(fixture_id), "bundled fallback"
