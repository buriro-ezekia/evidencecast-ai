# Fixture Mode and Three-Report Validation

## Purpose

Fixture mode guarantees that judges can explore the evidence-to-media workflow even when a commercial image or audio provider is unavailable. It does not simulate a provider success or create a fake Genblaze manifest.

## Fixture catalogue

| Fixture ID | Domain | Main workflow focus |
|---|---|---|
| `biolarviciding-community-acceptance` | Public health | Awareness, effectiveness and willingness to support malaria vector control |
| `climate-finance-smallholders` | Climate adaptation | Timing, access and complementary services in climate finance |
| `teacher-attendance-supervision` | Education | Attendance monitoring, mentorship and teacher support |

Each report is synthetic, contains no personal data and is labelled as a deployment fixture.

## What one fixture contains

Every fixture returns:

- the complete Markdown source report;
- a deterministic source SHA-256;
- exactly three approved evidence cards;
- exactly three storyboard scenes;
- approved-only storyboard mode;
- exactly three approved narration segments;
- evidence-card identifiers linked across cards, scenes and narration; and
- `provider_required: false`.

## Backend access

```text
GET /api/v1/fixtures
GET /api/v1/fixtures/{fixture_id}
```

The backend is the preferred source in a deployed environment. When it is unreachable, the Streamlit page loads the same bundled fixture definitions locally and identifies the source as `bundled fallback`.

## Judge workflow

1. Open **Fixture mode for judges**.
2. Confirm the backend health message or bundled-fallback message.
3. Select one sample report.
4. Click **Load complete approved fixture workflow**.
5. Inspect the source report.
6. Inspect the three approved evidence cards and locked excerpts.
7. Inspect the storyboard evidence links and prompts.
8. Inspect the approved narration.
9. Open **Local validation delivery** to create a transparently labelled Pillow/eSpeak package when B2 is configured.

## Automated tests

`tests/test_fixtures.py` loads all three reports and verifies:

- the catalogue contains exactly three fixtures;
- each source digest has 64 hexadecimal characters;
- each fixture has three approved evidence cards;
- each approved claim appears verbatim in its source report;
- each scene references one valid approved card;
- each narration segment references the same card as its scene; and
- all three narration segments are approved.

`tests/test_deployment_api.py` verifies:

- backend liveness and readiness;
- fixture count equals three;
- all three detail endpoints return complete workflows;
- unknown fixture identifiers return HTTP 404; and
- Render private `hostport` values are converted into valid HTTP base URLs.

## Manual sample-report test matrix

| Check | Public health | Climate adaptation | Education |
|---|---:|---:|---:|
| Source report displayed | Required | Required | Required |
| Three approved cards | Required | Required | Required |
| Source excerpts visible | Required | Required | Required |
| Three storyboard scenes | Required | Required | Required |
| Three approved narration segments | Required | Required | Required |
| Downstream handoff enabled | Required | Required | Required |
| No provider call needed | Required | Required | Required |

Record the deployed frontend URL, backend URL, fixture source (`backend` or `bundled fallback`) and pass/fail result for each report.

## Disclosure requirements

Do not describe fixture reports as real studies, newly collected data or provider-generated outputs. Fixture mode validates workflow usability and traceability; it does not replace live provider acceptance testing.
