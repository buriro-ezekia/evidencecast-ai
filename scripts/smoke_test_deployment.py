# Smoke-tests deployed EvidenceCast health endpoints and all three fixture reports.
from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

EXPECTED_FIXTURES = {
    "biolarviciding-community-acceptance",
    "climate-finance-smallholders",
    "teacher-attendance-supervision",
}


def _normalise_url(value: str) -> str:
    cleaned = value.strip()
    if "://" not in cleaned:
        cleaned = f"http://{cleaned}"
    return cleaned.rstrip("/") + "/"


def _get_json(base_url: str, path: str, timeout: float) -> dict[str, Any]:
    url = urljoin(_normalise_url(base_url), path.lstrip("/"))
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "EvidenceCastSmokeTest/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} from {url}: {exc.read().decode('utf-8', errors='replace')}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Could not reach {url}: {exc}") from exc
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected a JSON object from {url}.")
    return payload


def _get_text(base_url: str, path: str, timeout: float) -> str:
    url = urljoin(_normalise_url(base_url), path.lstrip("/"))
    request = Request(url, headers={"User-Agent": "EvidenceCastSmokeTest/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Could not reach {url}: {exc}") from exc


def run(api_url: str, web_url: str | None, timeout: float) -> None:
    health = _get_json(api_url, "/healthz", timeout)
    assert health.get("status") == "ok", health

    readiness = _get_json(api_url, "/readyz", timeout)
    assert readiness.get("status") == "ready", readiness
    assert readiness.get("fixture_count") == 3, readiness

    catalogue = _get_json(api_url, "/api/v1/fixtures", timeout)
    fixtures = catalogue.get("fixtures", [])
    found_ids = {item.get("fixture_id") for item in fixtures}
    assert found_ids == EXPECTED_FIXTURES, found_ids

    for fixture_id in sorted(EXPECTED_FIXTURES):
        workflow = _get_json(api_url, f"/api/v1/fixtures/{fixture_id}", timeout)
        assert len(workflow["review"]["cards"]) == 3
        assert workflow["storyboard"]["scene_count"] == 3
        assert workflow["narration"]["segment_count"] == 3
        assert all(card["status"] == "approved" for card in workflow["review"]["cards"])
        print(f"PASS fixture: {fixture_id}")

    if web_url:
        body = _get_text(web_url, "/_stcore/health", timeout).strip().lower()
        assert "ok" in body, body
        print("PASS frontend health")

    print("PASS backend health")
    print("PASS backend readiness")
    print("PASS all three sample reports")


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test an EvidenceCast deployment.")
    parser.add_argument("--api-url", required=True, help="FastAPI service base URL")
    parser.add_argument("--web-url", help="Optional Streamlit service base URL")
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()
    try:
        run(args.api_url, args.web_url, args.timeout)
    except (AssertionError, RuntimeError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
