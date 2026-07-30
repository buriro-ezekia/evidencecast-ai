# Deployment and Setup

## Delivered services

EvidenceCast is deployed as two independent web services:

| Service | Technology | Default local port | Health endpoint |
|---|---|---:|---|
| `evidencecast-web` | Streamlit | 8501 | `/_stcore/health` |
| `evidencecast-api` | FastAPI/Uvicorn | 8000 | `/healthz` |

The repository contains:

- `Dockerfile.web`;
- `Dockerfile.api`;
- `docker-compose.yml`; and
- `render.yaml`.

## Required secrets

For fixture exploration, no provider secret is required. The frontend can also use bundled fixtures when the backend is temporarily unavailable.

For B2-backed workflows, configure:

```text
B2_KEY_ID
B2_APP_KEY
B2_BUCKET
B2_REGION
B2_ENDPOINT
```

For private local live-provider validation, configure only the provider keys you actually use:

```text
GMI_API_KEY
OPENAI_API_KEY
NVIDIA_API_KEY
GOOGLE_API_KEY
```

Do not place media-provider keys in the public judge deployment. This prevents public users from consuming provider credits. Never commit populated `.env` files or paste keys into issue comments, screenshots or fixture JSON.

## Local Python setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Install local media dependencies on Ubuntu or Codespaces:

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg espeak-ng
```

Start the backend:

```bash
EVIDENCECAST_FIXTURE_MODE=1 \
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Start the frontend in a second terminal:

```bash
EVIDENCECAST_API_URL=http://localhost:8000 \
EVIDENCECAST_FIXTURE_MODE=1 \
streamlit run app.py --server.address=0.0.0.0 --server.port=8501
```

## Docker Compose

Create a local `.env` only when B2 or provider-backed features are required. Fixture mode works without it.

Build and start both services, then wait until their Docker health checks pass:

```bash
docker compose build --no-cache
docker compose up -d --wait --wait-timeout 180
docker compose ps
```

Open:

```text
Frontend: http://localhost:8501
Backend API: http://localhost:8000
OpenAPI documentation: http://localhost:8000/docs
```

Health checks:

```bash
curl --fail http://localhost:8000/healthz
curl --fail http://localhost:8000/readyz
curl --fail http://localhost:8501/_stcore/health
```

Run the retry-aware smoke test:

```bash
python scripts/smoke_test_deployment.py \
  --api-url http://localhost:8000 \
  --web-url http://localhost:8501 \
  --startup-timeout 120
```

When the frontend does not become healthy, inspect its state and logs before restarting:

```bash
docker compose ps -a
docker compose logs web --tail=200
docker compose restart web
docker compose up -d --wait --wait-timeout 180
```

The Streamlit image sets `PYTHONPATH=/app:/app/src`, launches Streamlit through `python -m streamlit`, and has an extended startup health window. This avoids import-path failures and prevents an immediate smoke test from misclassifying a service that is still starting.

Stop the stack:

```bash
docker compose down
```

## Render Free Blueprint deployment

The root `render.yaml` creates two public Docker web services in the Frankfurt region:

- `evidencecast-api-buriro-2026`;
- `evidencecast-web-buriro-2026`.

Render Free web services cannot receive private-network traffic. The Streamlit service therefore calls the FastAPI service through this public HTTPS URL:

```text
https://evidencecast-api-buriro-2026.onrender.com
```

Backblaze B2 remains the durable system of record because Render Free filesystems are ephemeral.

Deployment steps:

1. Use branch `feat/day-08-submission-package`.
2. In Render, create a new Blueprint.
3. Connect the private `buriro-ezekia/evidencecast-ai` repository through the Render GitHub App.
4. Select the root `render.yaml`.
5. Enter only `B2_KEY_ID`, `B2_APP_KEY` and `B2_BUCKET` for the Streamlit service.
6. Do not add GMI, OpenAI, NVIDIA or Google keys to the public deployment.
7. Create the Blueprint and wait for both health checks to pass.
8. Open `https://evidencecast-web-buriro-2026.onrender.com`.
9. Open **Fixture mode for judges** and load each of the three samples.

The first request after 15 minutes of inactivity can take about one minute while a Free service wakes.

For the full owner runbook, see [`submission/render-free-deployment.md`](submission/render-free-deployment.md).

## Post-deployment smoke test

Set the deployed URLs. Replace them only when Render assigns different subdomains:

```bash
export EVIDENCECAST_API_PUBLIC_URL="https://evidencecast-api-buriro-2026.onrender.com"
export EVIDENCECAST_WEB_PUBLIC_URL="https://evidencecast-web-buriro-2026.onrender.com"
```

Run:

```bash
python scripts/smoke_test_deployment.py \
  --api-url "$EVIDENCECAST_API_PUBLIC_URL" \
  --web-url "$EVIDENCECAST_WEB_PUBLIC_URL" \
  --startup-timeout 240
```

The expected readiness response reports:

```json
{
  "status": "ready",
  "fixture_count": 3,
  "fixture_mode": true
}
```

Expected smoke-test checks:

```text
PASS fixture: biolarviciding-community-acceptance
PASS fixture: climate-finance-smallholders
PASS fixture: teacher-attendance-supervision
PASS frontend health
PASS backend health
PASS backend readiness
PASS all three sample reports
```

Configuration booleans may differ according to the deployed secrets. Secret values are never returned.

## Rollback

Render retains the two most recent previous deploys for Free web services. Roll back the frontend and backend together when an interface contract changes. Fixture API version `v1` is intentionally stable for the hackathon submission.
