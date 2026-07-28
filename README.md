# EvidenceCast AI

EvidenceCast AI converts approved research findings into traceable multimedia communication assets, including evidence cards, infographics, narration and short videos. Every generated asset is stored with provenance metadata in Backblaze B2 through Genblaze.

## Hackathon

This repository is being developed for the Backblaze Generative Media Hackathon: Build with Genblaze on B2.

## Core workflow

```text
Upload trusted evidence
        ↓
Approve evidence claims
        ↓
Generate a structured media plan
        ↓
Generate images, narration and video
        ↓
Validate claims and media quality
        ↓
Store assets and provenance in Backblaze B2
        ↓
Review, revise and publish
```

## Day 1 vertical slice

The first implementation generates one EvidenceCast concept image using the GMI Cloud provider through Genblaze, persists the image and its canonical provenance manifest to a private Backblaze B2 bucket, and fails the run unless `Manifest.verify()` returns `True`.

### Provider and model

- Orchestration: Genblaze
- Media provider: GMI Cloud
- Default image model: `seedream-5.0-lite`
- Storage: private Backblaze B2 bucket through `genblaze-s3`
- Storage layout: Genblaze hierarchical key strategy

### Quick start

```bash
git clone https://github.com/buriro-ezekia/evidencecast-ai.git
cd evidencecast-ai
git switch feat/day-01-genblaze-b2

python -m venv .venv
```

On Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Enter the B2 and GMI Cloud credentials in the local `.env` file, then run:

```bash
python scripts/day01_generate_image.py
```

A successful run prints the image location, image SHA-256, manifest location, canonical manifest hash and `Manifest verified: True`. It also creates a non-secret local summary at `artifacts/day01-result.json`.

See [`docs/day-01-runbook.md`](docs/day-01-runbook.md) for detailed execution and troubleshooting instructions.

## Security

Do not commit API keys, B2 application keys, bucket credentials or populated `.env` files. Use `.env.example` only as a template and store real credentials in a local `.env` file or deployment secret manager.

The existing B2 key should remain restricted to the EvidenceCast bucket. The application does not require account-wide B2 access.

## Day 1 status

- [x] Devpost project created
- [x] GitHub repository created
- [x] Private B2 bucket created
- [x] Bucket-restricted B2 application key created
- [x] Genblaze and GMI Cloud dependencies defined
- [x] Image-generation and B2-persistence script implemented
- [ ] Live image generation executed
- [ ] Generated image and manifest confirmed in B2
- [ ] `Manifest.verify()` confirmed as `True` from a live run

## Licence

A licence will be selected before the public hackathon submission.
