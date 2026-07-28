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
- Default GMI Cloud image model: `seedream-5.0-lite`
- Optional image fallback provider: OpenAI API
- Default OpenAI image model: `gpt-image-1`
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

A successful run prints the image location, image SHA-256, manifest location, canonical manifest hash and `Manifest verified: True`.

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

See [`docs/day-02-runbook.md`](docs/day-02-runbook.md).

## Day 3 storyboard and image generation

Day 3 creates a structured three-scene storyboard from approved evidence cards only. It stores the storyboard and prompts in B2, then runs each scene through Genblaze while streaming durable progress events.

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

See [`docs/day-03-runbook.md`](docs/day-03-runbook.md).

## Day 4 narration and audio generation

Day 4 turns the approved-only storyboard into editable spoken narration. Every narration segment must be reviewed and approved before the application can submit three audio-generation jobs through Genblaze.

### Day 4 capabilities

- deterministic three-segment narration plan;
- storyboard and evidence-card traceability for every segment;
- editable spoken narration with locked evidence claims;
- pending, approved and rejected review decisions;
- explicit all-approved gate before TTS;
- narration plan and review persistence in B2;
- three GMI Cloud audio pipelines through Genblaze;
- default audio model `minimax-tts-speech-2.6-turbo`;
- immutable audio progress events and current-state record in B2;
- per-segment request and result JSON;
- audio SHA-256 and canonical provenance verification enforcement;
- partial-failure preservation; and
- final completed or failed audio summary.

### Day 4 quick start

```bash
git fetch origin
git switch feat/day-04-narration-audio
git pull origin feat/day-04-narration-audio
pip install -r requirements.txt
pytest -q
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

Open **Narration and audio** from the Streamlit sidebar after creating the Day 3 storyboard. When the Streamlit session has expired, the page can restore a previously downloaded approved-only storyboard JSON.

See [`docs/day-04-runbook.md`](docs/day-04-runbook.md).

## Security

Do not commit API keys, B2 application keys, bucket credentials or populated `.env` files. Use `.env.example` only as a template and store real credentials in a local `.env` file or deployment secret manager.

The B2 key should remain restricted to the EvidenceCast bucket. The application does not require account-wide B2 access.

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
- [x] Day 3 automated tests passed
- [x] Storyboard and prompt records confirmed in B2
- [x] Controlled GMI credit failure persisted correctly
- [ ] Three live scene images generated
- [ ] Three verified image manifests confirmed in B2

### Day 4

- [x] Three-segment narration-plan builder implemented
- [x] Human narration review interface implemented
- [x] All-approved audio gate implemented
- [x] Narration plan and review persistence implemented
- [x] Three-segment Genblaze audio orchestration implemented
- [x] Audio progress and failure persistence implemented
- [x] Day 4 automated tests added
- [ ] Day 4 tests executed in Codespaces
- [ ] Three narration segments approved and confirmed in B2
- [ ] Three live audio clips generated
- [ ] Three verified audio manifests confirmed in B2

## Licence

A licence will be selected before the public hackathon submission.
