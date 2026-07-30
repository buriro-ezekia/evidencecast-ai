# EvidenceCast AI Submission Readiness

## Deadline

The Devpost deadline is 3 August 2026 at 5:00 PM EDT, which is 4 August 2026 at 12:00 AM East Africa Time.

## Current status

| Requirement | Status | Evidence or remaining action |
|---|---|---|
| Working application URL | Pending owner deployment | `render.yaml`, Docker images, health endpoints and fixture mode are implemented. The repository owner must connect the private repository to Render and create the public services. |
| Repository access | Pending owner action | The repository is currently private. Either make it public or grant GitHub user `b2genblaze` contributor access before submission. |
| Approximately three-minute demo | Script complete; recording pending | Use `docs/submission/demo-script.md`. The final recording and public YouTube or Vimeo upload require the owner’s screen and account. |
| Devpost description | Complete draft | Ready-to-paste text is in `docs/submission/devpost-description.md`. Replace only the final public app, repository and video URLs. |
| Providers and models | Complete | The inventory and transparent validation status are in `docs/submission/providers-and-models.md`. |
| Genblaze and B2 explanation | Complete | The precise architecture explanation is included in the Devpost draft and provider inventory. |
| Local application tests | Complete | Latest recorded result: `45 passed in 4.41s`; the warning was corrected afterwards. |
| Local Docker smoke test | Complete | Frontend, backend, readiness and all three fixture reports passed. |
| Verified final delivery | Complete | Delivery `DEL-LOCAL-20260729T082428Z-aaa74869` is stored and integrity-verified in B2 with `provider_generated: false`. |
| Private-browser verification | Pending public URLs | Follow `docs/submission/public-verification-checklist.md` after deployment and repository access are finalised. |

## Honest provider status

EvidenceCast contains working provider integrations and transparent failure recording, but the final demonstration delivery must not be described as live provider-generated media.

- GMI Cloud image and TTS requests reached the provider boundary but were blocked by insufficient credits.
- NVIDIA image validation found the selected hosted model unavailable.
- NVIDIA Magpie TTS returned HTTP 504 and its voice-list endpoint timed out.
- OpenAI image support is implemented but was not funded for live validation.
- The completed demonstration delivery uses reviewed Pillow scene images, eSpeak NG narration and FFmpeg composition, and is explicitly marked `provider_generated: false`.

## Owner-only completion actions

1. Deploy the Streamlit and FastAPI services publicly.
2. Make the repository public or grant `b2genblaze` contributor access.
3. Run the public smoke test and complete the private-browser checklist.
4. Record the demonstration using the prepared script.
5. Upload the video publicly to YouTube or Vimeo.
6. Insert the three final URLs into Devpost and submit before the deadline.
