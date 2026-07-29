# Models, Providers and Generation Modes

## Design principle

EvidenceCast separates approved evidence from generated media. A model may propose or render an asset, but it does not become an accepted EvidenceCast output unless the workflow preserves evidence links, an asset digest and the required provenance records.

## Provider-backed models

| Modality | Provider | Default model | Role | Current live status |
|---|---|---|---|---|
| Image | GMI Cloud | `seedream-5.0-lite` | Three storyboard scene images | Request and failure persistence validated; live output blocked by insufficient credits |
| Image | NVIDIA NIM | `stabilityai/stable-diffusion-3-5-large` | Controlled one-scene live validation, then storyboard images | Official Genblaze NVIDIA connector implemented; account-specific model availability must be confirmed live |
| Image | OpenAI API | `gpt-image-1` | Optional image fallback | Implemented; requires separately funded API billing |
| Audio | GMI Cloud | `minimax-tts-speech-2.6-turbo` | Three narration clips | Correct payload and voice mapping validated; live output blocked by insufficient credits |
| Audio | NVIDIA hosted NIM | `nvidia/magpie-tts-multilingual` | Controlled approved-segment TTS validation | Wrapped as a Genblaze synchronous provider using the hosted Magpie synthesis endpoint |

## NVIDIA provider path

The NVIDIA route uses `NVIDIA_API_KEY`; the hosted key normally begins with `nvapi-`. The secret is read only from the environment and is never written into request JSON, logs, the FastAPI readiness response or B2 metadata.

Image generation uses the official `genblaze-nvidia` `NvidiaImageProvider`. The connector supports NVIDIA NIM image families including Stable Diffusion XL, Stable Diffusion 3.5 and FLUX. Because hosted availability can vary by model and account, EvidenceCast begins with one scene and accepts success only after the asset and manifest verification gates pass.

Narration uses NVIDIA Magpie multilingual TTS through an EvidenceCast synchronous Genblaze provider. The default settings are:

```text
Model: nvidia/magpie-tts-multilingual
Language: en-US
Voice: Magpie-Multilingual.EN-US.Aria
Encoding: LINEAR_PCM
Sample rate: 44100 Hz
```

The public service endpoint is configurable with `NVIDIA_TTS_ENDPOINT`; it is not a credential.

## Orchestration

Genblaze is the provider orchestration and provenance layer. Each image or audio scene is submitted as an independent pipeline so that:

- scene failures are isolated;
- requests and results remain scene-addressable;
- regeneration can target one scene;
- progress can be persisted incrementally; and
- successful assets can retain their own manifest and SHA-256.

A provider-backed success is accepted only when the pipeline records:

1. a completed step;
2. a non-empty media asset;
3. the asset SHA-256;
4. a persisted manifest URI;
5. the canonical manifest hash; and
6. `Manifest.verify() == True`.

## Human review gates

Models do not bypass human approval.

- Evidence cards begin as `pending`.
- Only `approved` evidence cards can enter a storyboard.
- Narration segments must all be `approved` before text-to-speech generation.
- Rejected and pending claims are excluded from generation.
- Final evaluation checks the scene, card and narration links before delivery.

## Local validation mode

The local validation route is not a model-provider success path.

| Component | Tool | Purpose |
|---|---|---|
| Scene images | Pillow | Render labelled evidence cards from approved claims |
| Narration | eSpeak NG | Create WAV narration from approved text |
| Timing | FFprobe | Measure actual narration duration |
| Composition | FFmpeg | Assemble and caption the final MP4 |

Every local delivery records:

```json
{
  "delivery_mode": "local_validation_fallback",
  "provider_generated": false,
  "image_generator": "pillow",
  "narration_generator": "espeak"
}
```

This route proves the complete application and delivery pipeline while avoiding false claims about provider generation.

## Fixture mode

Fixture mode uses no generative model. It provides three immutable synthetic reports with:

- three approved evidence cards;
- a three-scene approved-only storyboard;
- three approved narration segments; and
- deterministic identifiers and source SHA-256 values.

The fixture API and frontend fallback use the same fixture builder. Each fixture test verifies that every approved claim occurs verbatim in the bundled source report.

## Prompt constraints

Image prompts instruct providers not to invent:

- statistics;
- quotations;
- named people;
- organisations;
- causal relationships;
- logos or watermarks; or
- dense unsupported text.

Narration uses reviewer-approved text rather than asking the provider to rewrite the evidence during text-to-speech generation.

## Failure and retry policy

Non-retryable failures include:

- malformed or missing parameters;
- HTTP 400, 401, 402 or 403 responses;
- content-policy refusals; and
- unsupported models.

Potentially retryable failures include:

- timeouts;
- HTTP 429 rate limits;
- connection resets; and
- temporary HTTP 5xx provider errors.

The controlled NVIDIA validation uses zero automatic provider retries. This makes the first live request auditable and prevents repeated submissions while model access or payload compatibility is still being established.

## Model changes

A model override is permitted only within the supported provider and modality. Model changes should be tested against:

1. request-payload compatibility;
2. MIME type and asset extraction;
3. manifest persistence;
4. SHA-256 capture;
5. `Manifest.verify()`; and
6. failure-message translation.

Do not change the documented default model merely to make a failed run appear successful.
