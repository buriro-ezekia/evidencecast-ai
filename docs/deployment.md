# Deployment and Setup

## Delivered services

EvidenceCast is deployed as two independent web services:

| Service | Technology | Default port | Health endpoint |
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

For live provider generation, configure one or both of:

```text
GMI_API_KEY
OPENAI_API_KEY
```

Never commit populated `.env` files or paste keys into issue comments, screenshots or fixture JSON.

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

## Render Blueprint deployment

The root `render.yaml` creates two Docker web services in the Frankfurt region:

- `evidencecast-api`;
- `evidencecast-web`.

The frontend receives the backend private `hostport` through `EVIDENCECAST_API_URL`. The frontend client automatically adds the `http://` scheme when Render supplies a bare private host and port.

Deployment steps:

1. Push `feat/day-06-deployment-fixtures-docs` or merge it into the deployment branch.
2. In Render, create a new Blueprint.
3. Connect the `buriro-ezekia/evidencecast-ai` repository.
4. Select the root `render.yaml`.
5. Enter the requested B2 values for the frontend service.
6. Create the Blueprint and wait for both health checks to pass.
7. Open the `evidencecast-web` public URL.
8. Open **Fixture mode for judges** and load each of the three samples.

Provider keys can be added later from the service environment settings. They are not required for fixture exploration.

## Post-deployment smoke test

Set the deployed URLs:

```bash
export EVIDENCECAST_API_PUBLIC_URL="https://your-api-service.onrender.com"
export EVIDENCECAST_WEB_PUBLIC_URL="https://your-web-service.onrender.com"
```

Run:

```bash
python scripts/smoke_test_deployment.py \
  --api-url "$EVIDENCECAST_API_PUBLIC_URL" \
  --web-url "$EVIDENCECAST_WEB_PUBLIC_URL" \
  --startup-timeout 180
```

The expected readiness response reports:

```json
{
  "status": "ready",
  "fixture_count": 3,
  "fixture_mode": true
}
```

Configuration booleans may differ according to the deployed secrets. Secret values are never returned.

## Rollback

Render retains previous successful deploys. Roll back the frontend and backend together when an interface contract changes. Fixture API version `v1` is intentionally stable for the hackathon submission.
