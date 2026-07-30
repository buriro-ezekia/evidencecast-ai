# Developer Setup

## Prerequisites

- Python 3.12;
- Git;
- FFmpeg and FFprobe;
- eSpeak NG for the reviewed local delivery route;
- Docker with Compose for container testing; and
- optional bucket-restricted B2 and media-provider credentials.

## Clone the final project

```bash
git clone https://github.com/buriro-ezekia/evidencecast-ai.git
cd evidencecast-ai
git switch main
git pull origin main
```

Historical feature branches remain available for development history, but the supported submission and deployment branch is `main`.

## Python environment

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

## Configuration

```bash
cp .env.example .env
```

Fixture-only exploration requires no secret values. Keep:

```text
EVIDENCECAST_FIXTURE_MODE=1
EVIDENCECAST_API_URL=http://localhost:8000
EVIDENCECAST_DISABLE_HEAVY_ASSEMBLY=0
```

Add B2 credentials only when durable uploads, workflow restoration or final delivery access is required. Add provider keys only for private live image or narration generation.

Never commit the populated `.env` file.

## Run the two services

Terminal 1:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Terminal 2:

```bash
streamlit run app.py --server.address=0.0.0.0 --server.port=8501
```

Open:

```text
http://localhost:8501
http://localhost:8000/docs
```

## Test

```bash
pytest -q
```

The test suite covers evidence extraction, human review, storyboard and narration traceability, fixture reports, deployment endpoints, evaluation, regeneration, local media utilities and the public-hosting safety guard.

## Container test

```bash
docker compose build
docker compose up
```

Then run:

```bash
python scripts/smoke_test_deployment.py \
  --api-url http://localhost:8000 \
  --web-url http://localhost:8501
```

## Public-hosting mode

Small public instances should set:

```text
EVIDENCECAST_DISABLE_HEAVY_ASSEMBLY=1
```

The Streamlit container applies a runtime UI guard before startup. This keeps fixture exploration, B2 workflow restoration and consistency evaluation available while disabling new Pillow, eSpeak and FFmpeg assembly controls.

Use `EVIDENCECAST_DISABLE_HEAVY_ASSEMBLY=0` only for local development or an adequately provisioned private deployment.

## Further documentation

- Architecture: `docs/architecture.md`
- Deployment: `docs/deployment.md`
- Fixture mode: `docs/fixture-mode.md`
- Models and providers: `docs/models.md`
- Final media: `docs/day-05-runbook.md`
- Local reviewed delivery: `docs/local-validation-delivery.md`
- Submission verification: `docs/submission/public-verification-checklist.md`
