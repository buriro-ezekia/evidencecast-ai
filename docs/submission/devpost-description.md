# EvidenceCast AI — Devpost Description

## Project name

EvidenceCast AI

## Elevator pitch

Turn approved research findings into traceable infographics, narration and short videos, with every claim, media asset and provenance record preserved in Backblaze B2 through Genblaze.

## Inspiration

Research teams often have strong evidence but limited time and specialist capacity to convert it into clear public-facing media. Conventional content workflows also make it difficult to prove which source passage supports a visual, narration line or final video scene. EvidenceCast AI was designed to make evidence communication faster without sacrificing human review, traceability or storage durability.

## What it does

EvidenceCast AI converts trusted PDF, Markdown or plain-text evidence into an auditable multimedia workflow:

1. upload and hash the source document;
2. extract page-aware text and create evidence-card candidates;
3. require a human reviewer to approve, edit or reject every claim;
4. build a three-scene storyboard using approved cards only;
5. create editable narration and require approval of every segment;
6. orchestrate image and audio generation attempts through Genblaze;
7. preserve provider failures and retry lineage instead of hiding them;
8. assemble captions, an infographic, a thumbnail and a short MP4; and
9. store the source, intermediate JSON, media, hashes, evaluation records and provenance manifests in Backblaze B2.

The application includes three synthetic judge fixtures covering public health, climate adaptation and education. Fixture mode lets judges inspect the complete evidence-to-story workflow without needing provider credentials.

## How we built it

The user interface is built with Streamlit and the deployment API with FastAPI. EvidenceCast runs as separate frontend and backend Docker services and includes a Render Blueprint for public deployment.

Genblaze is the orchestration and provenance layer. Each scene image and narration segment is submitted as an independent pipeline step. This isolates failures, supports scene-level regeneration, records provider/model metadata, and produces canonical provenance manifests. EvidenceCast accepts a provider result only when the step contains a media asset, the asset has a SHA-256 value, the manifest has been persisted, and `Manifest.verify()` returns `True`.

Backblaze B2 is the durable system of record. The app uses the B2 S3-compatible API through `genblaze-s3` and a hierarchical key strategy. B2 stores original sources, extracted text, evidence-card reviews, storyboards, prompts, narration reviews, provider requests, progress events, results, media assets, manifests, subtitles, evaluations, regeneration lineage and final delivery packages. Final objects are checked against their B2 size and SHA-256 metadata before completion is recorded.

The final verified demonstration package is `DEL-LOCAL-20260729T082428Z-aaa74869`. It contains three reviewed scene images, three narration tracks, SRT and WebVTT captions, a captioned MP4, a thumbnail, an infographic and an assembly manifest. It is transparently labelled `provider_generated: false` because it uses Pillow, eSpeak NG and FFmpeg after hosted media providers were unavailable.

## Providers and models

- GMI Cloud image: `seedream-5.0-lite` — integration implemented; requests reached the authenticated provider boundary but live output was blocked by insufficient credits.
- GMI Cloud audio: `minimax-tts-speech-2.6-turbo` — payload and voice mapping implemented; live output was blocked by insufficient credits.
- OpenAI image: `gpt-image-1` — implemented as an optional fallback; no funded live validation was claimed.
- NVIDIA image: `stabilityai/stable-diffusion-3-5-large` — the hosted preflight probe returned model unavailable for the account.
- NVIDIA audio: `nvidia/magpie-tts-multilingual` — the hosted synthesis endpoint returned HTTP 504 and the voice-list endpoint subsequently timed out.
- Local reviewed delivery: Pillow images, eSpeak NG narration and FFmpeg composition — deterministic fallback tooling, not an AI provider, and always labelled `provider_generated: false`.

## Challenges we ran into

The largest challenge was building a useful media workflow while refusing to blur the line between successful provider generation and local validation. GMI Cloud authenticated requests but returned insufficient-credit responses. NVIDIA image preflight found the selected model unavailable, while Magpie TTS returned a gateway timeout. EvidenceCast therefore records requests, exact errors and failed summaries in B2 rather than describing an absent asset as successful.

A second challenge was maintaining traceability across many artefacts. A single approved claim must remain connected to its source excerpt, evidence-card identifier, storyboard scene, narration segment, media request, generated or reviewed asset, evaluation record and final delivery manifest. We addressed this with deterministic identifiers, SHA-256-addressed source roots, scene-level B2 paths and strict validation gates.

Deployment also required separate frontend and backend containers, resilient health checks, fixture fallback behaviour and a smoke test that tolerates cold starts.

## Accomplishments that we are proud of

- A complete evidence-to-media workflow with explicit human approval gates.
- Meaningful Genblaze orchestration across image and audio provider integrations.
- Durable B2 storage for sources, intermediates, progress, failures, provenance and final media.
- Canonical manifest verification and asset SHA-256 enforcement.
- Scene-level regeneration lineage with bounded retry handling.
- Three deterministic judge fixtures requiring no provider credentials.
- A verified captioned video, thumbnail and infographic delivery package.
- Forty-five automated tests passing locally, plus a successful Docker deployment smoke test.
- Transparent handling of provider unavailability without misleading success claims.

## What we learned

Reliable generative-media systems need more than a prompt and a model. They need human review, durable intermediate records, explicit failure states, content hashes, retriable scene boundaries and a clear distinction between provider-generated and locally validated assets. We also learned that B2 can serve as both media storage and an auditable workflow ledger when requests, progress events, manifests and lineage records share a consistent hierarchy.

## What is next

The next production step is to validate funded provider-generated image and audio assets end to end, then allow the final compositor to select only provider assets whose SHA-256 and Genblaze manifests have passed verification. Further work will add organisation-level review roles, signed publication links, multilingual evidence review, richer media-quality evaluation and search across B2-hosted evidence and provenance records.

## Built with

Python, Streamlit, FastAPI, Docker, Render, Genblaze, Backblaze B2, GMI Cloud, NVIDIA NIM, OpenAI API, Pillow, eSpeak NG, FFmpeg, boto3, pypdf and pytest.

## Final links to insert before submission

- Working application: `PUBLIC_APP_URL`
- Repository: `REPOSITORY_URL`
- Demonstration video: `PUBLIC_VIDEO_URL`
