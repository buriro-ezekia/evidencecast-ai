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

The first implementation generates one EvidenceCast concept image through Genblaze, persists the image and its canonical provenance manifest to a private Backblaze B2 bucket, and fails the run unless `Manifest.verify()` returns `True`.

### Providers and models

- Orchestration: Genblaze
- Preferred media provider: GMI Cloud
- Default GMI Cloud model: `seedream-5.0-lite`
- Optional fallback provider: OpenAI API
- Default OpenAI model: `gpt-image-1`
- Storage: private Backblaze B2 bucket through `genblaze-s3`
- Storage layout: Genblaze hierarchical key strategy

GMI Cloud remains the preferred provider because it aligns directly with the hackathon ecosystem. The OpenAI provider is available only as an operational fallback when GMI Cloud has no usable credit balance.

### Day 1 quick start

```bash
git clone https://github.com/buriro-ezekia/evidencecast-ai.git
cd evidencecast-ai
git switch feat/day-01-genblaze-b2

python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Enter the B2 and provider credentials in the local `.env` file, then run:

```bash
python scripts/day01_generate_image.py
```

A successful run prints the image location, image SHA-256, manifest location, canonical manifest hash and `Manifest verified: True`. It also creates a non-secret local summary at `artifacts/day01-result.json`.

A GMI Cloud HTTP 402 response means authentication succeeded but the organisation has insufficient credits. The optional OpenAI fallback requires separately funded OpenAI API billing:

```bash
python scripts/day01_generate_image.py --provider openai
```

See [`docs/day-01-runbook.md`](docs/day-01-runbook.md).

## Day 2 evidence workflow

The evidence workflow is implemented as a Streamlit interface. It accepts PDF, Markdown and plain-text sources, stores the original source and derived extraction artefacts in Backblaze B2, creates deterministic evidence-card candidates, and requires a human decision before a claim can move into media generation.

### Day 2 capabilities

- PDF and text upload;
- SHA-256-addressed source storage in B2;
- page-aware PDF text extraction;
- extracted-text and extraction-metadata persistence;
- transparent evidence-card candidate generation;
- editable claims with locked source excerpts;
- approve, reject and pending decisions;
- reviewer notes;
- reviewed evidence-card JSON stored in B2; and
- downloadable review JSON for inspection.

### Day 2 quick start

```bash
git fetch origin
git switch feat/day-02-evidence-workflow
pip install -r requirements.txt
pytest -q
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

In GitHub Codespaces, open forwarded port `8501` and keep its visibility private while using private research documents and credentials.

See [`docs/day-02-runbook.md`](docs/day-02-runbook.md).

## Day 3 storyboard and image generation

Day 3 adds a second Streamlit page that creates a structured three-scene storyboard from approved evidence cards only. It stores the storyboard and prompts in B2, then runs each scene through Genblaze while streaming durable progress events.

### Day 3 capabilities

- exactly three approved cards required for three scenes;
- deterministic storyboard IDs;
- structured storyboard JSON with card IDs, claims, narration, on-screen text, prompts, excerpts and page references;
- storyboard and scene-prompt persistence in B2;
- one Genblaze image pipeline per scene;
- immutable progress events and a current progress record in B2;
- per-scene request and result JSON;
- B2-linked image SHA-256 and provenance metadata;
- partial-failure preservation; and
- final completed or failed generation summary.

### Day 3 quick start

```bash
git fetch origin
git switch feat/day-03-storyboard-image-generation
git pull origin feat/day-03-storyboard-image-generation
pip install -r requirements.txt
pytest -q
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

On the main page, approve and save at least three cards. Then open **Storyboard and images** from the Streamlit sidebar. Storyboard creation works without provider credit; live image generation requires a configured provider with usable access or billing.

See [`docs/day-03-runbook.md`](docs/day-03-runbook.md).

## Security

Do not commit API keys, B2 application keys, bucket credentials or populated `.env` files. Use `.env.example` only as a template and store real credentials in a local `.env` file or deployment secret manager.

The existing B2 key should remain restricted to the EvidenceCast bucket. The application does not require account-wide B2 access.

## Delivery status

### Day 1

- [x] Devpost project created
- [x] GitHub repository created
- [x] Private B2 bucket created
- [x] Bucket-restricted B2 application key created
- [x] B2 Native API and S3-compatible credentials validated
- [x] Genblaze and image-provider dependencies defined
- [x] Image-generation and B2-persistence script implemented
- [x] GMI Cloud request submitted successfully to the provider boundary
- [x] Local Genblaze manifest smoke test verified
- [ ] GMI Cloud account funded or alternative funded provider configured
- [ ] Live image generation completed
- [ ] Generated image and manifest confirmed in B2
- [ ] `Manifest.verify()` confirmed as `True` from a live provider run

### Day 2

- [x] PDF and text upload implemented
- [x] Original source storage in B2 implemented
- [x] PDF and text extraction implemented
- [x] Evidence-card candidate generation implemented
- [x] Approve, reject and edit interface implemented
- [x] Reviewed evidence-card persistence implemented
- [x] Live Codespaces interface test completed
- [x] Source bundle and reviewed cards confirmed in B2
- [x] Automated tests passed

### Day 3

- [x] Approved-only storyboard builder implemented
- [x] Structured three-scene storyboard JSON implemented
- [x] Storyboard and prompt persistence implemented
- [x] Three-scene Genblaze orchestration implemented
- [x] Progress streaming and B2 progress records implemented
- [x] Partial-failure preservation implemented
- [x] Day 3 unit tests added
- [ ] Day 3 tests executed in Codespaces
- [ ] Storyboard and prompt records confirmed in B2
- [ ] Three live scene images generated
- [ ] Three verified manifests confirmed in B2

## Licence

A licence will be selected before the public hackathon submission.
