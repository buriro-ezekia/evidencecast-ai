# Day 4 Runbook: Narration Review and Audio Generation

## Objective

Convert the approved-only three-scene storyboard into a traceable narration package, require explicit human approval for every spoken segment, then generate three audio clips through Genblaze and preserve every intermediate record in Backblaze B2.

## Branch

```bash
git fetch origin
git switch feat/day-04-narration-audio
git pull origin feat/day-04-narration-audio
pip install -r requirements.txt
pytest -q
```

## Start Streamlit

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

Open the privately forwarded port and use the **Narration and audio** page in the Streamlit sidebar.

## Workflow

### 1. Create the narration plan

The page uses the active Day 3 storyboard. When a Streamlit session has expired, a previously downloaded storyboard JSON can be loaded into the page without recreating the evidence source.

Click:

```text
Create narration plan and save it to B2
```

The plan contains exactly three segments, each linked to:

- its storyboard scene;
- its evidence-card identifiers;
- the locked source claim;
- an editable spoken version;
- an optional reviewer note;
- a target duration; and
- a review decision.

The plan is stored at:

```text
{storyboard-root}/narration/{narration-id}/narration-plan.json
```

### 2. Review narration

Edit the **Editable spoken narration** field so formulas and technical terms sound natural when spoken, while preserving the meaning supported by the locked claim.

Set every segment to `approved`, then click:

```text
Save reviewed narration to B2
```

The review is stored at:

```text
{storyboard-root}/narration/{narration-id}/narration-review.json
```

Audio generation is blocked unless all three segments are approved. A review can be `completed` even when a segment is rejected, but the audio gate separately requires three approvals.

### 3. Generate audio

The current Genblaze implementation uses GMI Cloud's audio provider. The default model is:

```text
minimax-tts-speech-2.6-turbo
```

A different supported GMI Cloud audio model can be entered as a model override. `GMI_API_KEY` must be present in the local `.env` file.

Click:

```text
Generate three narration clips with Genblaze
```

The page streams and persists:

```text
Narration generation request saved
Scene 1 narration request submitted
Scene 1 audio and manifest stored
Scene 2 narration request submitted
Scene 2 audio and manifest stored
Scene 3 narration request submitted
Scene 3 audio and manifest stored
Final narration summary stored
```

## B2 layout

```text
evidencecast/
└── sources/
    └── {sha-prefix}/
        └── {source-sha256}/
            └── storyboards/
                └── {storyboard-id}/
                    └── narration/
                        └── {narration-id}/
                            ├── narration-plan.json
                            ├── narration-review.json
                            └── runs/
                                └── {audio-run-id}/
                                    ├── generation-request.json
                                    ├── generation-summary.json
                                    ├── progress/
                                    │   ├── current.json
                                    │   └── events/
                                    │       ├── 001.json
                                    │       └── ...
                                    └── segments/
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

Genblaze separately persists each successful audio asset and canonical provenance manifest through its Backblaze B2 sink. EvidenceCast segment results link to the audio URL, SHA-256, manifest URI, canonical hash and verification result.

## Controlled failure

The current GMI Cloud organisation may still return HTTP 402 because it has no usable credits. That result validates authentication and failure preservation, but it does not create an audio clip.

On failure, EvidenceCast must retain:

- narration plan;
- approved narration review;
- generation request;
- progress events;
- submitted segment request;
- failed segment result; and
- failed generation summary.

The application must not report an audio SHA-256, manifest or successful completion when no audio was produced.

## Acceptance criteria

### Available without paid provider execution

- [x] Three-segment narration plan.
- [x] Storyboard and evidence-card traceability.
- [x] Editable spoken text.
- [x] Human approval gate.
- [x] Narration plan and review persistence in B2.
- [x] Audio progress event model.
- [x] Per-segment request and result persistence.
- [x] Partial-failure preservation.
- [x] Automated tests without paid calls.

### Live audio validation

- [ ] All automated tests pass in Codespaces.
- [ ] Three narration segments approved and saved.
- [ ] Narration plan and review confirmed in B2.
- [ ] Three audio clips generated.
- [ ] Three audio SHA-256 values present.
- [ ] Three provenance manifests persisted.
- [ ] `Manifest.verify()` returns `True` for every clip.
- [ ] Final audio summary reports `completed`.
