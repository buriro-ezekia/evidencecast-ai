# Deployment and Setup

## Delivered services

EvidenceCast is deployed as two independent public web services:

| Service | Technology | Local port | Health endpoint |
|---|---|---:|---|
| `evidencecast-web-buriro-2026` | Streamlit | 8501 | `/_stcore/health` |
| `evidencecast-api-buriro-2026` | FastAPI/Uvicorn | 8000 | `/healthz` |

The repository contains `Dockerfile.web`, `Dockerfile.api`, `docker-compose.yml` and `render.yaml`.

## Supported branch

The supported deployment and submission branch is:

```text
main
```

Clone and update it with:

```bash
git clone https://github.com/buriro-ezekia/evidencecast-ai.git
cd evidencecast-ai
git switch main
git pull origin main
```

Historical feature branches remain available only as development records.

## Required secrets

Fixture exploration requires no provider secret. The frontend can also use bundled fixtures while the backend is temporarily unavailable.

For B2-backed restoration and delivery access, configure:

```text
B2_KEY_ID
B2_APP_KEY
B2_BUCKET
B2_REGION
B2_ENDPOINT
```

For private live-provider validation, configure only the provider keys that are actually used:

```text
GMI_API_KEY
OPENAI_API_KEY
NVIDIA_API_KEY
```

Do not place media-provider keys in the public judge deployment. Never commit a populated `.env` file or expose keys in screenshots, logs or issue comments.

## Local Python setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

On Ubuntu or Codespaces:

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
EVIDENCECAST_DISABLE_HEAVY_ASSEMBLY=0 \
streamlit run app.py --server.address=0.0.0.0 --server.port=8501
```

## Docker Compose

Build and start both services, then wait until their health checks pass:

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

Run the smoke test:

```bash
python scripts/smoke_test_deployment.py \
  --api-url http://localhost:8000 \
  --web-url http://localhost:8501 \
  --startup-timeout 120
```

## Render Free deployment

The root `render.yaml` deploys both services from `main` in the Frankfurt region:

```text
https://evidencecast-web-buriro-2026.onrender.com
https://evidencecast-api-buriro-2026.onrender.com
```

Render Free web services cannot receive private-network traffic. The Streamlit service therefore calls the FastAPI service through its public HTTPS address.

Backblaze B2 remains the durable system of record because Render Free filesystems are ephemeral.

### Public safety mode

The public Streamlit service sets:

```text
EVIDENCECAST_DISABLE_HEAVY_ASSEMBLY=1
```

At container startup, `scripts/configure_public_ui.py` applies an idempotent runtime guard to the two media-assembly pages. Judges can still:

- load the synthetic fixtures;
- restore approved storyboard and narration records from B2;
- inspect evidence links, hashes and URIs; and
- run lightweight consistency evaluation.

New Pillow, eSpeak and FFmpeg assembly controls are disabled on the small hosted instance. This prevents a repeated resource-exhaustion failure while retaining the complete local workflow in the repository.

Use `EVIDENCECAST_DISABLE_HEAVY_ASSEMBLY=0` only on a local or adequately provisioned private instance.

### Blueprint steps

1. Connect `buriro-ezekia/evidencecast-ai` to Render.
2. Select the root `render.yaml` from `main`.
3. Enter only `B2_KEY_ID`, `B2_APP_KEY` and `B2_BUCKET` for the Streamlit service.
4. Do not add GMI, OpenAI or NVIDIA keys to the public deployment.
5. Synchronise the Blueprint and wait for both health checks to pass.
6. Confirm both services show branch `main`.

The first request after inactivity may take around one minute while a Free service wakes.

## Post-deployment smoke test

```bash
python scripts/smoke_test_deployment.py \
  --api-url https://evidencecast-api-buriro-2026.onrender.com \
  --web-url https://evidencecast-web-buriro-2026.onrender.com \
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

Configuration booleans may vary according to deployed secrets. Secret values must never be returned.

## Rollback

Render retains recent deploys for rollback. Roll back the frontend and backend together when an interface contract changes. Fixture API version `v1` is intentionally stable for the hackathon submission.
