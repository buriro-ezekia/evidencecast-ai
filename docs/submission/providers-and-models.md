# Providers, Models, Genblaze and Backblaze B2

## Provider and model inventory

| Modality | Provider | Model or tool | EvidenceCast role | Live validation status |
|---|---|---|---|---|
| Image | GMI Cloud | `seedream-5.0-lite` | Primary three-scene image generation route | Authenticated request reached the provider boundary; HTTP 402 insufficient credits prevented an asset. |
| Audio | GMI Cloud | `minimax-tts-speech-2.6-turbo` | Primary approved narration route | Correct `text` payload and voice mapping reached the provider boundary; HTTP 402 insufficient credits prevented an asset. |
| Image | OpenAI API | `gpt-image-1` | Optional image fallback | Integration implemented; separately funded live validation was not claimed. |
| Image | NVIDIA NIM | `stabilityai/stable-diffusion-3-5-large` | Optional NVIDIA scene-image route | Genblaze preflight probed the hosted endpoint and returned model not found or unavailable for the account. |
| Audio | NVIDIA hosted NIM | `nvidia/magpie-tts-multilingual` | Optional NVIDIA narration route | The synthesis endpoint returned HTTP 504; the voice-list endpoint later timed out. |
| Image fallback | Local Pillow renderer | No AI model | Reviewed, deterministic scene-card images | Completed and verified; explicitly `provider_generated: false`. |
| Audio fallback | eSpeak NG | No AI model | Reviewed narration WAV files | Completed and verified; explicitly `provider_generated: false`. |
| Composition | FFmpeg and FFprobe | No AI model | Timing, subtitles, thumbnail inputs and captioned MP4 | Completed and verified. |

No failed provider request is represented as a successful generated asset. Provider failures retain the provider, model, exact error, request record, result record and B2 summary URI.

## How Genblaze is used

Genblaze is not a decorative dependency. It controls the media-generation lifecycle and provenance boundary.

### Scene and segment isolation

Each image scene and narration segment is submitted as an independent Genblaze pipeline. This design provides:

- one provider/model record per media item;
- isolated failure handling;
- bounded retries for transient failures;
- non-retryable stopping for authentication, invalid input, content-policy and credit failures;
- scene-level regeneration without rebuilding successful assets; and
- parent-child lineage between original and regenerated runs.

### Object storage sink

EvidenceCast connects Genblaze to Backblaze B2 through `genblaze-s3`:

```text
Provider step
    ↓
Genblaze Pipeline
    ↓
ObjectStorageSink
    ↓
S3StorageBackend.for_backblaze(...)
    ↓
Private Backblaze B2 bucket
```

The hierarchical key strategy keeps media and manifests grouped by project, run and step.

### Success gate

A provider result is accepted only when all of the following are true:

1. Genblaze records a completed step.
2. The step contains a non-empty media asset.
3. The asset has a SHA-256 value.
4. The canonical provenance manifest has a B2 URI.
5. The manifest has a canonical hash.
6. `Manifest.verify()` returns `True`.

A request that fails any gate is stored as a failure and cannot enter the final provider-generated delivery path.

## How Backblaze B2 is used

Backblaze B2 is the application’s durable system of record rather than a final-file dump.

### Source and review layer

B2 stores:

- original PDF, Markdown and text evidence;
- SHA-256-addressed source roots;
- extracted page-aware text;
- extraction metadata;
- evidence-card candidates;
- edited claims, decisions and reviewer notes; and
- approved evidence-card records.

### Media-planning layer

B2 stores:

- three-scene storyboards;
- evidence-card links;
- source excerpts and page references;
- scene prompts and narration drafts;
- narration plans; and
- approved narration reviews.

### Generation and observability layer

B2 stores:

- provider and model requests;
- per-scene and per-segment request JSON;
- immutable progress events;
- current progress snapshots;
- successful results;
- controlled failure results;
- Genblaze provenance manifests;
- asset SHA-256 values; and
- completed or failed generation summaries.

### Evaluation and delivery layer

B2 stores:

- structural evaluations;
- scene-level regeneration requests;
- attempt records and retry classification;
- parent-child lineage;
- SRT and WebVTT captions;
- scene images and narration audio;
- the captioned MP4;
- thumbnail and infographic;
- final assembly manifest; and
- B2 object-size and SHA-256 verification results.

## Verified example

The current verified demonstration package is:

```text
DEL-LOCAL-20260729T082428Z-aaa74869
```

Assembly manifest:

```text
b2://evidencecast-ai-buriro-2026/evidencecast/sources/c9/c959ebebe624ebec10c23a73c7ec1a4e4a270feacaa0748d4a7a7fbbf7f9fcfe/storyboards/SB-e27c3386b25a84a0/deliveries/DEL-LOCAL-20260729T082428Z-aaa74869/assembly-manifest.json
```

This package proves the full reviewed workflow and B2 delivery path. It is deliberately labelled:

```json
{
  "delivery_mode": "local_validation_fallback",
  "provider_generated": false,
  "image_generator": "pillow",
  "narration_generator": "espeak"
}
```
