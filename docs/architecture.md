# EvidenceCast AI Architecture

## System purpose

EvidenceCast converts approved research evidence into traceable communication assets. The system separates source review, media planning, generation, evaluation and final delivery so that a failed provider request never erases the approved evidence or creates a false success record.

## Deployment topology

```text
Judge or reviewer
      │
      ▼
Streamlit frontend (`evidencecast-web`)
      │  HTTP/JSON: health, capabilities and fixtures
      ▼
FastAPI backend (`evidencecast-api`)
      │
      ├── Bundled synthetic fixture reports
      └── Provider-independent fixture workflows

Streamlit production workflows
      │
      ├── Backblaze B2 S3-compatible API
      │     ├── source documents
      │     ├── extracted text and evidence reviews
      │     ├── storyboards and narration reviews
      │     ├── generation requests, events and results
      │     └── final deliveries and manifests
      │
      ├── Genblaze orchestration
      │     ├── GMI Cloud image and audio providers
      │     └── optional OpenAI image provider
      │
      └── Local validation tools
            ├── Pillow scene rendering
            ├── eSpeak NG narration
            └── FFmpeg/FFprobe composition and timing
```

## Frontend responsibilities

The Streamlit service provides the human-facing workflow:

1. source upload and extraction;
2. evidence-card approval, rejection and editing;
3. approved-only storyboard creation;
4. narration review and approval;
5. image and audio generation controls;
6. evidence consistency evaluation;
7. scene-level regeneration and lineage inspection;
8. final subtitle, MP4, thumbnail and infographic delivery; and
9. judge fixture exploration.

The frontend never displays secret values. It reports only whether B2 or provider credentials are configured.

## Backend responsibilities

The FastAPI service is deliberately small and stateless. It provides:

- `GET /healthz` for liveness;
- `GET /readyz` for fixture and configuration readiness;
- `GET /api/v1/capabilities` for transparent technology and model disclosure;
- `GET /api/v1/fixtures` for the three-report fixture catalogue; and
- `GET /api/v1/fixtures/{fixture_id}` for one complete approved workflow.

The fixture API does not require B2 or provider credentials. If the backend is unavailable, the frontend can use the same bundled fixtures directly.

## Storage architecture

Backblaze B2 is the durable system of record. The application uses SHA-256-addressed source roots and explicit JSON records rather than relying on transient Streamlit session state.

```text
evidencecast/sources/{sha-prefix}/{source-sha}/
├── original/
├── derived/
├── reviews/
└── storyboards/{storyboard-id}/
    ├── storyboard.json
    ├── scene-prompts.json
    ├── runs/
    ├── narration/{narration-id}/
    ├── evaluations/
    ├── regenerations/
    └── deliveries/
```

Each stored delivery input and output carries SHA-256 metadata. Final delivery verification compares the expected digest and byte count with B2 object metadata before the assembly manifest can report `completed`.

## Evidence and provenance controls

- Media planning selects approved evidence cards only.
- Storyboard scenes retain evidence-card identifiers, claims, excerpts and page references.
- Narration segments retain scene and evidence-card identifiers.
- Provider success requires an asset SHA-256, persisted manifest and successful `Manifest.verify()` result.
- Failed provider calls preserve requests, progress events, attempt records and summaries.
- Regeneration creates a child run and records the parent run ID, media type and scene number.
- Fixture and local-validation outputs are explicitly labelled as synthetic or non-provider-generated.

## Failure model

Deterministic failures stop immediately:

- invalid payloads;
- missing parameters;
- authentication or authorisation failures;
- content-policy refusals; and
- insufficient provider credits.

Transient failures may use bounded retries:

- timeouts;
- rate limits;
- temporary provider unavailability; and
- selected HTTP 5xx errors.

Every attempt remains inspectable even when a later retry succeeds.

## Deployment boundaries

The frontend and backend are separately containerised and can be deployed independently. In Render, the frontend receives the backend private `hostport` through `EVIDENCECAST_API_URL`. In Docker Compose, the frontend reaches the backend at `http://api:8000`.

No database is required for the deployment milestone because durable workflow records are stored in B2 and fixture data is immutable. A transactional database can be introduced later for user accounts, permissions and multi-user workflow coordination.
