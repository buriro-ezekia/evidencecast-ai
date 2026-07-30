# Developer Setup

## Prerequisites

- Python 3.12;
- Git;
- FFmpeg and FFprobe;
- eSpeak NG for local narration validation;
- Docker with Compose for container testing; and
- optional bucket-restricted B2 and media-provider credentials.

## Clone and select the deployment branch

```bash
git clone https://github.com/buriro-ezekia/evidencecast-ai.git
cd evidencecast-ai
git switch feat/day-06-deployment-fixtures-docs
```

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
```

Add B2 credentials to use durable uploads and final delivery. Add provider keys only for live image or narration generation.

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

The deployment tests cover all three fixture reports and the FastAPI endpoints.

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

## Further documentation

- Architecture: `docs/architecture.md`
- Deployment: `docs/deployment.md`
- Fixture mode: `docs/fixture-mode.md`
- Models and providers: `docs/models.md`
- Final media: `docs/day-05-runbook.md`
