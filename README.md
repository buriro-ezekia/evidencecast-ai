# EvidenceCast AI

EvidenceCast AI is a human-reviewed research-to-media workflow that turns approved evidence into traceable storyboards, narration, infographics and short videos. Provider media generation is orchestrated through Genblaze, while source records, reviews, provider outcomes, fallback deliveries and provenance metadata are stored durably in Backblaze B2.

## Public links

- **Live application:** https://evidencecast-web-buriro-2026.onrender.com/
- **Public API:** https://evidencecast-api-buriro-2026.onrender.com/
- **Project website:** https://buriro-ezekia.github.io/evidencecast-ai/
- **Demonstration video:** https://www.youtube.com/watch?v=tCU5KRakVxE

The Render services use Free instances and may require around one minute to wake after inactivity.

## The problem

Research teams often need to turn technical findings into clear public-facing media. Conventional generative workflows can weaken the connection between the source evidence and the final claim, especially when prompts, edits, provider failures and regenerated assets are not retained.

EvidenceCast AI keeps human approval and provenance inside the media pipeline rather than treating them as optional documentation.

## What it does

1. Accepts PDF, Markdown and plain-text evidence sources.
2. Stores the original source and extracted text in Backblaze B2 under a SHA-256-addressed source root.
3. Creates evidence-card candidates with locked source excerpts and page references.
4. Requires a reviewer to approve, edit or reject every claim.
5. Builds a three-scene storyboard from approved cards only.
6. Creates editable narration that must be approved before text-to-speech submission.
7. Runs image scenes and narration segments as separate Genblaze pipelines.
8. Stores requests, progress, outcomes, failures, hashes and manifests in B2.
9. Supports scene-level regeneration with parent-child lineage.
10. Evaluates evidence consistency and assembles subtitles, thumbnails, infographics and captioned video deliveries.

## Core workflow

```text
Trusted evidence
      ↓
Evidence extraction and SHA-256 source identity
      ↓
Human-reviewed evidence cards
      ↓ approved claims only
Three-scene storyboard
      ↓
Reviewed narration
      ↓
Scene-level Genblaze media pipelines
      ↓
Evaluation, regeneration and lineage
      ↓
Backblaze B2 assets, logs and provenance
      ↓
Captioned delivery package
```

## Genblaze usage

Genblaze controls the provider-generation and provenance boundary. Each scene image and narration segment is isolated as its own pipeline so that EvidenceCast can retain one provider/model record per media item, classify failures, stop non-retryable requests, apply bounded retries to transient errors and regenerate one scene without rebuilding successful assets.

A provider result is accepted only when:

- Genblaze records a completed step;
- a non-empty asset is present;
- the asset has a SHA-256 value;
- the canonical provenance manifest has a B2 URI and canonical hash; and
- `Manifest.verify()` returns `True`.

Requests that fail this gate are stored as failures and cannot enter the successful provider-generated delivery path.

## Backblaze B2 usage

Backblaze B2 is the durable workflow ledger, not merely a final-file destination. It stores:

- original sources, extracted text and extraction metadata;
- evidence-card candidates, reviewer decisions and approved claims;
- storyboards, prompts, narration plans and narration reviews;
- provider requests, progress events, results and controlled failures;
- Genblaze provenance manifests and asset hashes;
- regeneration requests, retry attempts and parent-child lineage;
- SRT and WebVTT captions, images, audio, thumbnails and infographics;
- captioned MP4 deliveries; and
- final assembly manifests with B2 size and SHA-256 verification.

## Providers and models

| Modality | Provider or tool | Model | Current status |
|---|---|---|---|
| Image | GMI Cloud | `seedream-5.0-lite` | Authenticated request reached the provider boundary; HTTP 402 insufficient credits prevented an asset. |
| Audio | GMI Cloud | `minimax-tts-speech-2.6-turbo` | Correct request and voice mapping reached the provider boundary; HTTP 402 insufficient credits prevented an asset. |
| Image | OpenAI API | `gpt-image-1` | Integration implemented; separately funded live generation is not claimed. |
| Image | NVIDIA NIM | `stabilityai/stable-diffusion-3-5-large` | Hosted model was unavailable for the account during validation. |
| Audio | NVIDIA hosted NIM | `nvidia/magpie-tts-multilingual` | Synthesis returned HTTP 504 and later voice discovery timed out. |
| Reviewed fallback image | Pillow | No AI model | Completed and explicitly marked `provider_generated: false`. |
| Reviewed fallback audio | eSpeak NG | No AI model | Completed and explicitly marked `provider_generated: false`. |
| Composition | FFmpeg and FFprobe | No AI model | Used for timing, subtitles, thumbnail inputs and captioned MP4 assembly. |

No failed provider request is represented as a successful generated asset.

## Verified reviewed delivery

The current reviewed fallback package is:

```text
DEL-LOCAL-20260729T082428Z-aaa74869
```

Its manifest records:

```json
{
  "delivery_mode": "local_validation_fallback",
  "provider_generated": false,
  "image_generator": "pillow",
  "narration_generator": "espeak"
}
```

This delivery verifies the reviewed evidence-to-media workflow and durable B2 path without misrepresenting deterministic fallback assets as provider-generated media.

## Judge fixture mode

The public application includes three synthetic fixtures that contain no personal data:

- community acceptance of biolarviciding;
- climate financing and smallholder farmers; and
- teacher attendance supervision.

Each fixture provides three approved evidence cards, a three-scene approved-only storyboard and three approved narration segments. Provider keys are not required to explore these fixtures.

## Public hosting safety

The public Render Free frontend sets:

```text
EVIDENCECAST_DISABLE_HEAVY_ASSEMBLY=1
```

This preserves workflow restoration, fixture exploration and consistency evaluation while disabling new Pillow, eSpeak and FFmpeg assembly controls on the small hosted instance. Full assembly remains available locally or on an adequately provisioned private deployment.

## Quick start

### Prerequisites

- Python 3.12;
- Git;
- FFmpeg and FFprobe;
- eSpeak NG for the reviewed local delivery route; and
- optional Docker with Compose.

### Clone the final branch

```bash
git clone https://github.com/buriro-ezekia/evidencecast-ai.git
cd evidencecast-ai
git switch main
git pull origin main
```

### Create the environment

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

On Ubuntu or Codespaces:

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg espeak-ng
```

Fixture-only exploration requires no secret values. Keep:

```text
EVIDENCECAST_FIXTURE_MODE=1
EVIDENCECAST_API_URL=http://localhost:8000
EVIDENCECAST_DISABLE_HEAVY_ASSEMBLY=0
```

### Run locally

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

### Test

```bash
pytest -q
```

### Docker Compose

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

## Security

- Never commit populated `.env` files or provider credentials.
- Use a bucket-restricted B2 application key.
- Keep provider keys out of the public judge deployment.
- Health and readiness endpoints expose configuration booleans only, never secret values.
- Treat the synthetic fixtures as deployment tests rather than new research findings.

## Documentation

- [Developer setup](docs/setup.md)
- [Architecture](docs/architecture.md)
- [Deployment](docs/deployment.md)
- [Fixture mode](docs/fixture-mode.md)
- [Providers, models, Genblaze and B2](docs/submission/providers-and-models.md)
- [Local validation delivery](docs/local-validation-delivery.md)
- [Submission package](docs/submission/README.md)
- [Public verification checklist](docs/submission/public-verification-checklist.md)

Historical milestone runbooks remain under `docs/day-01-runbook.md` through `docs/day-05-runbook.md`.

## Licence

This project is released under the [MIT Licence](LICENSE).
