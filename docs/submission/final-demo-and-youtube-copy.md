# EvidenceCast AI Final Demo and YouTube Copy

## Recording requirement

Record the public application in a private browser window. Target 2 minutes 45 seconds to 2 minutes 55 seconds. Keep the mouse movement deliberate and avoid showing credentials, browser bookmarks, unrelated tabs, Render environment variables or private signed URLs.

## Final voice-over script

### 0:00–0:14 — Opening

**Screen:** EvidenceCast AI landing page.

**Narration:**

Research teams often have strong evidence but limited time to turn it into clear public media without losing traceability. EvidenceCast AI converts reviewed findings into evidence cards, storyboards, narration, infographics and short captioned videos.

### 0:14–0:35 — Judge fixture

**Screen:** Open **Fixture mode for judges** and select `biolarviciding-community-acceptance`. Show the synthetic-source label and source SHA-256.

**Narration:**

For reliable judging, the public application includes three synthetic fixtures that require no provider credentials. I will use the community-acceptance example. The source is hashed, and every later record remains linked to this exact evidence package.

### 0:35–0:58 — Human approval

**Screen:** Show the three approved evidence cards, excerpts and identifiers.

**Narration:**

Each evidence card preserves a supported claim, the source excerpt and a stable identifier. A human must approve the claim before it can enter media generation. Pending or rejected findings cannot bypass this review gate.

### 0:58–1:22 — Storyboard and narration

**Screen:** Load storyboard `SB-e27c3386b25a84a0`, then narration `NP-15ad65aedbeaf9c0`. Keep one shared evidence-card ID visible.

**Narration:**

The approved cards become a structured three-scene storyboard. Narration remains editable and must also be approved. The same evidence-card identifier follows the claim from source review into the scene and spoken text.

### 1:22–1:48 — Final media

**Screen:** Open **Final media and evaluation**, restore the storyboard and narration, then show delivery `DEL-LOCAL-20260729T082428Z-aaa74869`. Play approximately ten seconds of the captioned MP4 and show the infographic or thumbnail.

**Narration:**

EvidenceCast assembles scene visuals, timed narration, subtitles, a thumbnail, an infographic and a short MP4. This reviewed demonstration delivery is transparently labelled `provider_generated: false`, so the application never presents a provider failure as generated media.

### 1:48–2:16 — Genblaze and provenance

**Screen:** Show a generation result or provenance panel containing provider, model, run ID, SHA-256, manifest URI and verification status. Briefly show one accurately persisted provider failure if useful.

**Narration:**

Genblaze orchestrates image and audio work at scene level. This isolates failures, supports targeted regeneration and creates provenance records. A provider asset is accepted only when it has a SHA-256 value, a persisted manifest and successful manifest verification.

### 2:16–2:40 — Backblaze B2

**Screen:** Show B2 URIs for the source, storyboard, narration review and final assembly manifest.

**Narration:**

Backblaze B2 is the durable workflow ledger. It stores original evidence, extracted text, human reviews, prompts, progress events, provider results, controlled failures, manifests, captions, final media and regeneration lineage in one consistent hierarchy.

### 2:40–2:54 — Close

**Screen:** Return to the final media page or fixture catalogue.

**Narration:**

EvidenceCast helps research and public-interest teams communicate evidence faster while keeping human approval, traceability and durable storage at the centre of the workflow.

## YouTube title

EvidenceCast AI Demo — Traceable Research-to-Media Workflows with Genblaze and Backblaze B2

## YouTube description

EvidenceCast AI converts human-approved research findings into traceable evidence cards, three-scene storyboards, approved narration, infographics and short captioned videos.

Public application:
https://evidencecast-web-buriro-2026.onrender.com/

Public API:
https://evidencecast-api-buriro-2026.onrender.com/

Repository:
https://github.com/buriro-ezekia/evidencecast-ai

How the project works:

- Human reviewers approve, reject or edit evidence cards before media generation.
- Genblaze orchestrates scene-level image and audio pipelines, regeneration and provenance records.
- Backblaze B2 stores original sources, extracted text, reviews, storyboards, prompts, progress events, provider results, failures, manifests, captions and final delivery assets.
- Final assets are checked with SHA-256 values and provenance-manifest verification.

Providers and models implemented or validated:

- GMI Cloud image: `seedream-5.0-lite`
- GMI Cloud speech: `minimax-tts-speech-2.6-turbo`
- OpenAI image fallback: `gpt-image-1`
- NVIDIA image: `stabilityai/stable-diffusion-3-5-large`
- NVIDIA speech: `nvidia/magpie-tts-multilingual`
- Reviewed local media delivery: FFmpeg and local speech tooling, explicitly labelled `provider_generated: false`

The live provider checks were reported transparently: GMI Cloud reached an insufficient-credit boundary, the NVIDIA image model was unavailable in the hosted catalogue, and the NVIDIA Magpie endpoint returned a gateway timeout. No failed provider request is presented as a generated provider asset.

Built for the Backblaze Generative Media Hackathon: Build with Genblaze on B2.

## Suggested YouTube tags

EvidenceCast AI, Backblaze B2, Genblaze, generative media, provenance, research communication, evidence traceability, Streamlit, FastAPI, AI hackathon

## Suggested pinned comment

EvidenceCast AI is designed around human approval and transparent provenance. The demonstration delivery shown in this video is explicitly marked `provider_generated: false`; controlled provider failures are retained in B2 rather than being misrepresented as successful generated assets.

## Final upload settings

- Visibility: Public
- Audience: No, it is not made for children
- Category: Science & Technology
- Language: English
- Licence: Standard YouTube Licence
- Thumbnail: Use the EvidenceCast final-delivery thumbnail or a clean application screenshot
- Captions: Upload the final `.srt` file or allow YouTube captions only after checking them manually
