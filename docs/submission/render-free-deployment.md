# Render Free Deployment Runbook

This runbook deploys EvidenceCast AI as two public Render Free web services while keeping durable workflow artefacts in Backblaze B2.

## Deployment design

- `evidencecast-api-buriro-2026`: FastAPI service exposed publicly over HTTPS.
- `evidencecast-web-buriro-2026`: Streamlit service exposed publicly over HTTPS.
- The Streamlit service calls the FastAPI service through its public HTTPS URL.
- Both services use Render Free instances and may take about one minute to wake after 15 minutes of inactivity.
- The public deployment does not configure media-provider secrets. This prevents public users from consuming GMI, NVIDIA, OpenAI or Google credits.
- B2 remains the durable system of record because Render Free filesystems are ephemeral.

## Before creating the Blueprint

1. Confirm the repository contains no populated `.env` file, API key, B2 application key or presigned B2 URL.
2. Confirm the deployment branch is `feat/day-08-submission-package`.
3. In Render, connect the GitHub account that can read `buriro-ezekia/evidencecast-ai`.
4. Ensure the Render GitHub App has access to this private repository.

## Create the Blueprint

1. Open the Render Dashboard.
2. Choose **New +** and then **Blueprint**.
3. Select `buriro-ezekia/evidencecast-ai`.
4. Select branch `feat/day-08-submission-package`.
5. Confirm Render finds the root `render.yaml`.
6. Approve creation of both Free web services.
7. Enter only the bucket-restricted B2 values requested for `evidencecast-web-buriro-2026`:

```text
B2_KEY_ID
B2_APP_KEY
B2_BUCKET=evidencecast-ai-buriro-2026
```

The region and S3 endpoint are already defined in `render.yaml`.

Do not add GMI, OpenAI, NVIDIA or Google provider keys to the public service.

## Expected public URLs

The Blueprint uses unique service names so the expected URLs are:

```text
https://evidencecast-web-buriro-2026.onrender.com
https://evidencecast-api-buriro-2026.onrender.com
```

Record the actual URLs shown by Render. Use the dashboard values if Render assigns a different subdomain.

## Validate the API

Replace the URL below only when Render assigned a different one:

```bash
# Validates the public EvidenceCast FastAPI service.
export EVIDENCECAST_API_PUBLIC_URL="https://evidencecast-api-buriro-2026.onrender.com"

curl --fail --show-error "$EVIDENCECAST_API_PUBLIC_URL/healthz"
curl --fail --show-error "$EVIDENCECAST_API_PUBLIC_URL/readyz"
curl --fail --show-error "$EVIDENCECAST_API_PUBLIC_URL/api/v1/capabilities"
```

A Free service may need about one minute to wake before the first successful response.

## Validate both public services

```bash
# Runs the retry-aware public deployment smoke test.
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

## Private-browser verification

Open a private or incognito browser window with no GitHub, Render or application session.

1. Open the public Streamlit URL.
2. Confirm the landing page loads after any cold start.
3. Open **Fixture mode for judges**.
4. Load all three fixture reports.
5. Confirm no credentials or environment values appear.
6. Open the public API `/healthz`, `/readyz` and `/docs` URLs.
7. Confirm the repository is public or that `b2genblaze` has collaborator access.
8. Play the completed demonstration media and check captions, audio and framing.

Record the exact result in issue #16 before completing the Devpost form.

## Free-tier operational note

Render Free web services sleep after inactivity, have ephemeral filesystems and cannot receive private-network traffic. EvidenceCast therefore uses the API's public HTTPS URL and Backblaze B2 for durable storage. Judges should be warned that the first page load can take about one minute after a cold start.
