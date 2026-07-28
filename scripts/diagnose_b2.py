# Diagnoses Backblaze B2 credentials, bucket restrictions, S3 permissions and region settings without revealing secrets.
from __future__ import annotations

import base64
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

AUTHORIZE_URL = "https://api.backblazeb2.com/b2api/v4/b2_authorize_account"
REQUIRED_S3_CAPABILITIES = {
    "listBuckets",
    "listAllBucketNames",
    "readFiles",
    "writeFiles",
}


def require_value(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def authorise_account(key_id: str, application_key: str) -> dict[str, Any]:
    credentials = f"{key_id}:{application_key}".encode("utf-8")
    basic_auth = base64.b64encode(credentials).decode("ascii")
    request = Request(
        AUTHORIZE_URL,
        headers={
            "Authorization": f"Basic {basic_auth}",
            "Accept": "application/json",
            "User-Agent": "evidencecast-ai-b2-diagnostic/1.0",
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        response_text = exc.read().decode("utf-8", errors="replace")
        if exc.code == 401:
            raise RuntimeError(
                "Backblaze rejected B2_KEY_ID/B2_APP_KEY. The pair is invalid, expired, "
                "revoked, copied incorrectly, or does not belong together. Create a new "
                "application key and replace both values in .env."
            ) from exc
        raise RuntimeError(
            f"Backblaze authorisation failed with HTTP {exc.code}: {response_text}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(f"Could not contact Backblaze: {exc.reason}") from exc


def region_from_s3_url(s3_url: str) -> str | None:
    match = re.search(r"https://s3\.([a-z0-9-]+)\.backblazeb2\.com", s3_url)
    return match.group(1) if match else None


def main() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    load_dotenv(dotenv_path=repository_root / ".env", override=True)

    key_id = require_value("B2_KEY_ID")
    application_key = require_value("B2_APP_KEY")
    configured_bucket = require_value("B2_BUCKET")
    configured_region = os.getenv("B2_REGION", "").strip()

    response = authorise_account(key_id, application_key)
    storage_api = response.get("apiInfo", {}).get("storageApi")
    if not isinstance(storage_api, dict):
        raise RuntimeError(
            "The key authenticated, but the response did not grant access to the B2 "
            "Storage API. Create a standard B2 application key for the bucket."
        )

    allowed = storage_api.get("allowed") or {}
    capabilities = set(allowed.get("capabilities") or [])
    buckets = allowed.get("buckets") or []
    allowed_bucket_names = {
        str(bucket.get("name"))
        for bucket in buckets
        if isinstance(bucket, dict) and bucket.get("name")
    }
    name_prefix = allowed.get("namePrefix") or ""
    s3_api_url = str(storage_api.get("s3ApiUrl") or "")
    detected_region = region_from_s3_url(s3_api_url)

    problems: list[str] = []
    missing_capabilities = sorted(REQUIRED_S3_CAPABILITIES - capabilities)
    if missing_capabilities:
        problems.append(
            "Missing S3-compatible capabilities: " + ", ".join(missing_capabilities)
        )

    if allowed_bucket_names and configured_bucket not in allowed_bucket_names:
        problems.append(
            f"The key is restricted to {sorted(allowed_bucket_names)}, but B2_BUCKET is "
            f"{configured_bucket!r}."
        )

    if name_prefix:
        problems.append(
            f"The key has file-name prefix restriction {name_prefix!r}. Leave the prefix "
            "empty for the current Genblaze hierarchical object layout."
        )

    if configured_region and detected_region and configured_region != detected_region:
        problems.append(
            f"B2_REGION is {configured_region!r}, but Backblaze reports "
            f"{detected_region!r}."
        )

    print("Backblaze native authentication: successful")
    print(f"Configured bucket:             {configured_bucket}")
    print(
        "Allowed bucket names:          "
        + (", ".join(sorted(allowed_bucket_names)) if allowed_bucket_names else "not disclosed")
    )
    print(f"S3 API endpoint:               {s3_api_url or 'not returned'}")
    print(f"Configured region:             {configured_region or 'not set'}")
    print(f"Detected region:               {detected_region or 'not detected'}")
    print(f"File-name prefix:              {name_prefix or 'none'}")
    print("Required S3 capabilities:")
    for capability in sorted(REQUIRED_S3_CAPABILITIES):
        status = "present" if capability in capabilities else "MISSING"
        print(f"  - {capability}: {status}")

    if problems:
        print("\nConfiguration problems detected:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print(
            "\nCreate a replacement bucket-restricted application key with Read and "
            "Write access, Allow List All Bucket Names enabled, and no file-name prefix. "
            "Then replace both B2_KEY_ID and B2_APP_KEY in .env.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print("\nB2 credential and capability diagnostics passed.")


if __name__ == "__main__":
    main()
