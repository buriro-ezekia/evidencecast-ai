# Smoke-tests deployed EvidenceCast health endpoints and all three fixture reports with startup retries.
from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any, Callable, TypeVar
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

EXPECTED_FIXTURES = {
    "biolarviciding-community-acceptance",
    "climate-finance-smallholders",
    "teacher-attendance-supervision",
}

T = TypeVar("T")


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


def _wait_for(
    label: str,
    check: Callable[[], T],
    startup_timeout: float,
    retry_interval: float,
) -> T:
    deadline = time.monotonic() + startup_timeout
    attempt = 0
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        attempt += 1
        try:
            result = check()
            if attempt > 1:
                print(f"PASS {label} after {attempt} attempts")
            return result
        except (AssertionError, RuntimeError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            remaining = max(0.0, deadline - time.monotonic())
            print(
                f"WAIT {label}: attempt {attempt} failed; retrying in {retry_interval:.1f}s "
                f"({remaining:.1f}s remaining)",
                file=sys.stderr,
            )
            time.sleep(min(retry_interval, remaining))

    raise RuntimeError(f"{label} did not become ready within {startup_timeout:.1f}s: {last_error}")


def run(
    api_url: str,
    web_url: str | None,
    timeout: float,
    startup_timeout: float,
    retry_interval: float,
) -> None:
    health = _wait_for(
        "backend health",
        lambda: _get_json(api_url, "/healthz", timeout),
        startup_timeout,
        retry_interval,
    )
    assert health.get("status") == "ok", health

    readiness = _wait_for(
        "backend readiness",
        lambda: _get_json(api_url, "/readyz", timeout),
        startup_timeout,
        retry_interval,
    )
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
        body = _wait_for(
            "frontend health",
            lambda: _get_text(web_url, "/_stcore/health", timeout).strip().lower(),
            startup_timeout,
            retry_interval,
        )
        assert "ok" in body, body
        print("PASS frontend health")

    print("PASS backend health")
    print("PASS backend readiness")
    print("PASS all three sample reports")


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test an EvidenceCast deployment.")
    parser.add_argument("--api-url", required=True, help="FastAPI service base URL")
    parser.add_argument("--web-url", help="Optional Streamlit service base URL")
    parser.add_argument("--timeout", type=float, default=20.0, help="Per-request timeout in seconds")
    parser.add_argument(
        "--startup-timeout",
        type=float,
        default=120.0,
        help="Maximum time to wait for each service to become ready",
    )
    parser.add_argument(
        "--retry-interval",
        type=float,
        default=3.0,
        help="Delay between startup health retries",
    )
    args = parser.parse_args()
    try:
        run(
            args.api_url,
            args.web_url,
            args.timeout,
            args.startup_timeout,
            args.retry_interval,
        )
    except (AssertionError, RuntimeError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
