# Day 3 Runbook: Storyboard JSON, Three Scene Images and Progress Streaming

## Objective

Complete a review-gated media-planning workflow that:

1. uses approved evidence cards only;
2. creates exactly three traceable storyboard scenes;
3. saves storyboard JSON and scene prompts to Backblaze B2;
4. generates one image for each scene through Genblaze;
5. stores every request, progress event, scene result and final summary in B2; and
6. refuses to claim success unless each generated image has a SHA-256 value, a persisted provenance manifest and `Manifest.verify() == True`.

## Branch

```bash
git fetch origin
git switch feat/day-03-storyboard-image-generation
git pull origin feat/day-03-storyboard-image-generation
```

Install and test:

```bash
pip install -r requirements.txt
pytest -q
```

The Day 3 test suite exercises approved-only storyboard construction, deterministic storyboard IDs, three-scene progress streaming, intermediate persistence and partial-failure handling without making paid provider calls.

## Start the application

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

Open the privately forwarded Codespaces port. Streamlit exposes the main evidence page and a second page named **Storyboard and images**.

## Prepare approved evidence

On the main EvidenceCast page:

1. upload and process a selectable-text PDF, Markdown file or plain-text document;
2. approve at least three evidence cards;
3. reject or leave other cards pending as appropriate;
4. add reviewer notes where useful; and
5. click **Save reviewed evidence cards to B2**.

Day 3 deliberately refuses to build a three-scene storyboard from fewer than three approved cards. Pending and rejected cards are excluded.

## Create the storyboard

Open **Storyboard and images** from the Streamlit sidebar, then click:

```text
Create storyboard and save intermediates to B2
```

The application creates a deterministic storyboard containing:

- storyboard and source identifiers;
- approved evidence-card identifiers;
- three scene titles;
- evidence claims;
- narration;
- concise on-screen text;
- evidence-safe image prompts;
- source excerpts and page references; and
- suggested scene duration.

The following records are stored immediately:

```text
{source-root}/storyboards/{storyboard-id}/storyboard.json
{source-root}/storyboards/{storyboard-id}/scene-prompts.json
```

Storyboard creation does not require a paid image provider.

## Generate three images

Select either `gmicloud` or `openai`. The corresponding local environment variable must exist:

```dotenv
GMI_API_KEY=...
# or
OPENAI_API_KEY=...
```

Then click:

```text
Generate three scene images with Genblaze
```

The UI streams progress for every durable stage:

```text
Generation request saved
Scene 1 request saved and submitted
Scene 1 image and manifest stored
Scene 2 request saved and submitted
Scene 2 image and manifest stored
Scene 3 request saved and submitted
Scene 3 image and manifest stored
Generation summary stored
```

## B2 object layout

EvidenceCast-managed intermediate records use:

```text
evidencecast/
└── sources/
    └── {sha-prefix}/
        └── {source-sha256}/
            └── storyboards/
                └── {storyboard-id}/
                    ├── storyboard.json
                    ├── scene-prompts.json
                    └── runs/
                        └── {generation-id}/
                            ├── generation-request.json
                            ├── generation-summary.json
                            ├── progress/
                            │   ├── current.json
                            │   └── events/
                            │       ├── 001.json
                            │       └── ...
                            └── scenes/
                                ├── scene-01/
                                │   ├── request.json
                                │   └── result.json
                                ├── scene-02/
                                │   ├── request.json
                                │   └── result.json
                                └── scene-03/
                                    ├── request.json
                                    └── result.json
```

Genblaze separately persists the generated image bytes and canonical provenance manifest through its hierarchical B2 sink. Each EvidenceCast scene-result record links to the resulting asset URL, asset SHA-256, manifest URI, canonical manifest hash and verification result.

## Provider failure behaviour

A provider failure does not erase prior work. EvidenceCast stores:

- the generation request;
- all progress events emitted before failure;
- every completed scene result;
- the failed scene result; and
- a final `failed` generation summary.

This allows a later retry without falsely claiming that all three images were generated.

A GMI Cloud HTTP 402 response means the key authenticated but the organisation has insufficient credits. Storyboard and request artefacts remain valid, while live scene generation remains incomplete.

## Completion criteria

### Implemented and testable without paid generation

- [x] Approved-only three-scene storyboard construction.
- [x] Structured storyboard JSON.
- [x] Scene prompt JSON.
- [x] B2 persistence for storyboard and prompts.
- [x] Streamed progress event model.
- [x] Immutable progress events plus current-state record in B2.
- [x] Per-scene request and result records.
- [x] Partial-failure summary.
- [x] Unit tests without external provider calls.

### Live provider validation

- [ ] At least three approved evidence cards saved.
- [ ] Storyboard and scene prompts confirmed in B2.
- [ ] Three scene images generated.
- [ ] Three image SHA-256 values present.
- [ ] Three provenance manifests persisted.
- [ ] `Manifest.verify()` returned `True` for every scene.
- [ ] Final generation summary reports `completed`.
