# Day 5 Runbook: Final Media and Evaluation

## Scope review

The requested milestone was reviewed against the repository before implementation.

| Requested capability | Status before Day 5 | Day 5 action |
|---|---|---|
| Generate narration | Implemented; live output blocked by GMI credit | Retained and connected to final assembly |
| Produce subtitles | Not implemented | Added SRT and WebVTT generation |
| Compose captioned MP4 with FFmpeg | Not implemented | Added three-scene still-image/audio assembly with burned captions |
| Create thumbnail | Not implemented | Added 1280 × 720 JPEG export |
| Create infographic export | Not implemented | Added 1080 × 1350 PNG export from approved claims |
| Evidence consistency checks | Partial approved-only controls | Added cross-stage consistency report |
| Manifest verification | Implemented for successful Genblaze image/audio assets | Added summary-record checks and B2 delivery-object verification |
| Scene-level regeneration | Not implemented | Added single image or audio scene child runs |
| Parent-child run relationships | Not implemented | Added lineage records |
| Failure and retry handling | Partial failure persistence | Added retry classification and bounded exponential retry handling |

## Branch

```bash
git fetch origin
git switch feat/day-05-final-media-evaluation
git pull origin feat/day-05-final-media-evaluation
pip install -r requirements.txt
```

Install FFmpeg in the Codespace when it is not already available:

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg
ffmpeg -version
ffprobe -version
```

Run the complete test suite:

```bash
pytest -q
```

Start Streamlit:

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

Open **Final media and evaluation** from the Streamlit sidebar.

## 1. Restore approved inputs

The page reuses the current Streamlit session when the storyboard and narration are already present. After a restart, it can load both records from B2.

Current validated records:

```text
Storyboard:
b2://evidencecast-ai-buriro-2026/evidencecast/sources/c9/c959ebebe624ebec10c23a73c7ec1a4e4a270feacaa0748d4a7a7fbbf7f9fcfe/storyboards/SB-e27c3386b25a84a0/storyboard.json

Approved narration:
b2://evidencecast-ai-buriro-2026/evidencecast/sources/c9/c959ebebe624ebec10c23a73c7ec1a4e4a270feacaa0748d4a7a7fbbf7f9fcfe/storyboards/SB-e27c3386b25a84a0/narration/NP-15ad65aedbeaf9c0/narration-review.json
```

Click:

```text
Restore storyboard and approved narration from B2
```

## 2. Run evidence consistency checks

Click:

```text
Run consistency checks and save evaluation to B2
```

Without completed provider summaries, the evaluator checks:

- exactly three storyboard scenes;
- approved-only storyboard mode;
- valid and matching source SHA-256;
- matching storyboard IDs;
- exactly three narration segments;
- matching scene numbers;
- matching evidence-card identifiers;
- non-empty source claims; and
- approved non-empty narration.

When completed image and audio summary URIs are supplied, it additionally requires three asset records, valid asset SHA-256 values, manifest URIs and `manifest_verified: true` for every scene.

Evaluation records are stored under:

```text
{storyboard-root}/evaluations/{evaluation-id}.json
```

## 3. Produce subtitles and final exports

The page requires one image and one narration clip for each of the three scenes. This permits final assembly from successful provider outputs or manually reviewed assets while the provider account remains unfunded.

Supported inputs:

- images: PNG, JPEG and WebP;
- audio: MP3, WAV, M4A and AAC.

Click:

```text
Build and verify final delivery package
```

The workflow:

1. stores all six inputs in B2 with SHA-256 metadata;
2. uses FFprobe to read each narration duration;
3. produces timed SRT and WebVTT captions;
4. creates one MP4 segment per image/audio pair;
5. concatenates the three segments;
6. burns subtitles into the final MP4;
7. creates a 16:9 JPEG thumbnail;
8. creates a three-card PNG infographic;
9. uploads every output to B2;
10. checks B2 metadata SHA-256 and content length; and
11. stores an assembly manifest.

Delivery layout:

```text
{storyboard-root}/deliveries/{delivery-id}/
├── assets/
│   ├── scene-01-image.*
│   ├── scene-01-audio.*
│   ├── scene-02-image.*
│   ├── scene-02-audio.*
│   ├── scene-03-image.*
│   ├── scene-03-audio.*
│   ├── evidencecast-captioned.mp4
│   ├── thumbnail.jpg
│   └── infographic.png
├── subtitles/
│   ├── captions.srt
│   └── captions.vtt
└── assembly-manifest.json
```

The final package reports `completed` only when every stored object passes its B2 SHA-256 and size verification.

## 4. Scene-level regeneration

Select:

- media kind: image or audio;
- scene number: 1, 2 or 3;
- parent generation run ID;
- reason for regeneration;
- maximum attempts; and
- optional model override.

Click:

```text
Regenerate selected scene with lineage
```

Every child run stores:

```text
{storyboard-root}/regenerations/{child-run-id}/
├── request.json
├── lineage.json
├── attempts/
│   ├── 01.json
│   └── 02.json
└── summary.json
```

`lineage.json` records:

- parent run ID;
- child run ID;
- relationship `scene_regeneration`;
- media kind; and
- scene number.

## Retry rules

Retries are bounded and conservative.

Retryable examples:

- timeout;
- HTTP 429;
- HTTP 500, 502, 503 or 504;
- temporary provider unavailability; and
- connection reset.

Non-retryable examples:

- HTTP 400 or invalid payload;
- required parameter missing;
- HTTP 401 or 403;
- content-policy refusal; and
- HTTP 402 insufficient credits.

This prevents repeated paid submissions for deterministic failures. Each failed attempt remains stored even when a later retry succeeds.

## Acceptance criteria

### Implemented

- [x] Evidence consistency evaluator.
- [x] Optional generated-asset manifest checks.
- [x] SRT and WebVTT subtitles.
- [x] FFmpeg captioned MP4 assembly.
- [x] Thumbnail export.
- [x] Infographic export.
- [x] Final B2 assembly manifest.
- [x] B2 SHA-256 and size verification.
- [x] Image and audio scene-level regeneration.
- [x] Parent-child run lineage.
- [x] Failure classification and bounded retry handling.
- [x] Automated tests added.

### Live validation still required

- [ ] Full test suite passes in Codespaces.
- [ ] FFmpeg and FFprobe detected.
- [ ] Structural evaluation passes and is confirmed in B2.
- [ ] Three reviewed images supplied.
- [ ] Three reviewed narration clips supplied.
- [ ] Captioned MP4 assembled.
- [ ] SRT and WebVTT outputs confirmed.
- [ ] Thumbnail and infographic confirmed.
- [ ] Assembly manifest reports `completed`.
- [ ] All B2 object verifications report `true`.
- [ ] One scene-level child run records correct parent lineage.

## Provider limitation

GMI Cloud currently rejects image and audio generation because the organisation has insufficient credits. Final assembly therefore cannot yet use live GMI assets. The manual reviewed-asset path allows FFmpeg, subtitle, export, B2 integrity and delivery-manifest validation without pretending that the assets were generated by GMI.
