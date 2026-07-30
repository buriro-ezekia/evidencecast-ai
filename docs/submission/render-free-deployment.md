# Render Free Deployment Runbook

This runbook deploys EvidenceCast AI as two public Render Free web services while keeping durable workflow artefacts in Backblaze B2.

## Deployment design

- `evidencecast-api-buriro-2026`: FastAPI service exposed publicly over HTTPS.
- `evidencecast-web-buriro-2026`: Streamlit service exposed publicly over HTTPS.
- Both services deploy from `main`.
- The Streamlit service calls the FastAPI service through its public HTTPS URL.
- Both services use Render Free instances and may take about one minute to wake after inactivity.
- The public deployment does not configure media-provider secrets.
- Backblaze B2 remains the durable system of record because Render Free filesystems are ephemeral.
- Resource-intensive Pillow, eSpeak and FFmpeg controls are disabled on the public frontend.

## Before synchronising the Blueprint

1. Confirm the public repository contains no populated `.env` file, API key, B2 application key or presigned B2 URL.
2. Confirm the default and deployment branch is `main`.
3. Confirm Render has access to `buriro-ezekia/evidencecast-ai`.
4. Confirm the root `render.yaml` defines both services and references `main`.

## Create or synchronise the Blueprint

1. Open the Render Dashboard.
2. Choose **New + → Blueprint**, or open the existing `evidencecast-ai-buriro-2026` Blueprint.
3. Select `buriro-ezekia/evidencecast-ai`.
4. Select branch `main` when creating a new Blueprint.
5. Confirm Render finds the root `render.yaml`.
6. Approve or manually synchronise both Free web services.
7. Enter only the bucket-restricted B2 values requested for `evidencecast-web-buriro-2026`:

```text
B2_KEY_ID
B2_APP_KEY
B2_BUCKET=evidencecast-ai-buriro-2026
```

The region, endpoint, fixture mode, API URL and heavy-assembly safety flag are defined in `render.yaml`.

Do not add GMI, OpenAI or NVIDIA provider keys to the public service.

## Public safety mode

The Streamlit service sets:

```text
EVIDENCECAST_DISABLE_HEAVY_ASSEMBLY=1
```

At startup, `scripts/configure_public_ui.py` disables new local media assembly and uploaded-asset FFmpeg assembly controls. The application still supports fixture exploration, B2 restoration, evidence inspection and lightweight consistency evaluation.

This guard prevents a repeated resource-exhaustion failure on the small hosted instance without removing the complete local workflow from the repository.

## Public URLs

```text
https://evidencecast-web-buriro-2026.onrender.com
https://evidencecast-api-buriro-2026.onrender.com
```

## Validate the API

```bash
export EVIDENCECAST_API_PUBLIC_URL="https://evidencecast-api-buriro-2026.onrender.com"

curl --fail --show-error "$EVIDENCECAST_API_PUBLIC_URL/healthz"
curl --fail --show-error "$EVIDENCECAST_API_PUBLIC_URL/readyz"
curl --fail --show-error "$EVIDENCECAST_API_PUBLIC_URL/api/v1/capabilities"
```

A Free service may need about one minute to wake before the first successful response.

## Validate both public services

```bash
export EVIDENCECAST_WEB_PUBLIC_URL="https://evidencecast-web-buriro-2026.onrender.com"
export EVIDENCECAST_API_PUBLIC_URL="https://evidencecast-api-buriro-2026.onrender.com"

python scripts/smoke_test_deployment.py \
  --api-url "$EVIDENCECAST_API_PUBLIC_URL" \
  --web-url "$EVIDENCECAST_WEB_PUBLIC_URL" \
  --startup-timeout 240
```

Expected checks:

```text
PASS fixture: biolarviciding-community-acceptance
PASS fixture: climate-finance-smallholders
PASS fixture: teacher-attendance-supervision
PASS frontend health
PASS backend health
PASS backend readiness
PASS all three sample reports
```

Retain the exact output against the final submitted commit.

## Private-browser verification

Open a private or incognito browser window with no GitHub, Render or application session.

1. Open the public Streamlit URL.
2. Confirm the landing page loads after any cold start.
3. Open **Fixture mode for judges**.
4. Load all three fixture reports.
5. Confirm no credentials or environment values appear.
6. Confirm heavy media assembly controls are disabled with a clear explanation.
7. Open the public API `/healthz`, `/readyz` and `/docs` URLs.
8. Open the public repository and confirm the final README and setup instructions use `main`.
9. Play the complete demonstration video without signing in.

Record the exact result in issue #16 before completing the Devpost form.

## Free-tier operational note

Render Free web services sleep after inactivity, have ephemeral filesystems and cannot receive private-network traffic. EvidenceCast therefore uses the API's public HTTPS URL, B2 for durable storage and a public-hosting guard for resource-intensive media assembly.
