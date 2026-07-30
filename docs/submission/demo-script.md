# EvidenceCast AI Demonstration Script

## Target duration

Aim for 2 minutes 45 seconds to 2 minutes 55 seconds. Do not exceed three minutes.

Record the public application in a private browser window. Use one continuous screen recording where practical. Do not expose `.env`, API keys, B2 credentials, private object URLs containing temporary signatures, browser bookmarks or unrelated tabs.

## Recording preparation

Before recording:

1. Open the public Streamlit application in a private browser window.
2. Confirm the backend and frontend are healthy.
3. Load the `biolarviciding-community-acceptance` fixture once so the first interaction is fast.
4. Keep the verified final delivery ready in the application.
5. Hide the Streamlit developer menu if it distracts from the demonstration.
6. Use microphone narration only; do not add copyrighted music.
7. Set browser zoom so claims, identifiers and status labels remain readable.

## Timed script and screen actions

### 0:00–0:15 — Problem and product

**Screen:** EvidenceCast landing page and project title.

**Narration:**

“Research teams often have strong evidence but limited capacity to turn it into clear public media while preserving traceability. EvidenceCast AI converts reviewed evidence into auditable infographics, narration and short videos.”

### 0:15–0:38 — Judge fixture and source evidence

**Screen:** Open **Fixture mode for judges** and select the public-health fixture. Show the synthetic-source label and source SHA-256.

**Narration:**

“For reliable judging, the application includes three synthetic fixtures that need no provider credentials. I will use the public-health example. The source is hashed, and every later record remains linked to this exact source.”

### 0:38–1:02 — Human approval gate

**Screen:** Show the three evidence cards, their approved status, excerpts and identifiers.

**Narration:**

“Evidence cards preserve the supported claim, source excerpt and identifier. A human must approve each claim before it can enter media generation. Pending or rejected claims are excluded, so generation cannot bypass review.”

### 1:02–1:25 — Storyboard and narration traceability

**Screen:** Show the three-scene storyboard, then the approved narration segments. Keep at least one shared evidence-card ID visible across the card, scene and narration.

**Narration:**

“The approved cards become a structured three-scene storyboard. Narration remains editable and must also be approved. The same evidence-card identifier follows the claim from source review into the scene and spoken text.”

### 1:25–1:53 — Final media in action

**Screen:** Open the final-delivery page. Play 10–15 seconds of the captioned MP4, then show the infographic and thumbnail.

**Narration:**

“EvidenceCast assembles timed narration, captions, scene visuals, a thumbnail, an infographic and a short MP4. This verified demonstration delivery uses reviewed local media tooling and is clearly labelled `provider_generated: false`; the application never misrepresents a provider failure as generated media.”

### 1:53–2:20 — Genblaze orchestration

**Screen:** Show a generation or provenance result containing provider, model, run ID, asset SHA-256, manifest URI and `Manifest verified` status. A controlled provider failure may also be shown briefly.

**Narration:**

“Genblaze orchestrates each image scene and narration segment independently. That isolates failures, supports scene-level regeneration and creates provenance records. A provider asset is accepted only when it has a SHA-256, a persisted manifest and `Manifest.verify()` returns true.”

### 2:20–2:43 — Backblaze B2 as system of record

**Screen:** Show B2 URIs from the source, storyboard, narration, generation summary and final assembly manifest. Do not open credentials.

**Narration:**

“Backblaze B2 is the durable workflow ledger. It stores original evidence, extracted text, reviews, prompts, progress events, provider results, failures, manifests, captions, final media and regeneration lineage in a consistent hierarchy.”

### 2:43–2:55 — Closing value

**Screen:** Return to the fixture catalogue or final media page.

**Narration:**

“EvidenceCast helps research and public-interest teams communicate evidence faster while keeping human approval, traceability and durable storage at the centre of the workflow.”

## Required visible proof

The final video should visibly demonstrate:

- the application functioning, not slides alone;
- one synthetic fixture loading;
- three approved evidence cards;
- the three-scene storyboard;
- approved narration;
- the captioned final MP4 playing;
- an infographic or thumbnail;
- at least one B2 URI;
- provider and model metadata;
- a SHA-256 value;
- a Genblaze manifest record or verification result; and
- transparent `provider_generated: false` labelling for the local demonstration package.

## Suggested video title

EvidenceCast AI — Traceable Research-to-Media Workflows with Genblaze and Backblaze B2

## Suggested video description

EvidenceCast AI converts human-approved research findings into traceable evidence cards, storyboards, narration, infographics and short captioned videos. Genblaze orchestrates scene-level media workflows and provenance, while Backblaze B2 stores sources, reviews, requests, failures, manifests and final delivery assets. Built for the Backblaze Generative Media Hackathon.
