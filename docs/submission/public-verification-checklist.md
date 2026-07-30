# Public Application and Repository Verification

Complete this checklist against the final `main` commit before submitting on Devpost.

## Final public values

```text
PUBLIC_APP_URL=https://evidencecast-web-buriro-2026.onrender.com/
PUBLIC_API_URL=https://evidencecast-api-buriro-2026.onrender.com/
REPOSITORY_URL=https://github.com/buriro-ezekia/evidencecast-ai
PROJECT_SITE_URL=https://buriro-ezekia.github.io/evidencecast-ai/
PUBLIC_VIDEO_URL=https://www.youtube.com/watch?v=tCU5KRakVxE
```

## 1. Repository access

- [x] The repository is public.
- [x] The complete project is consolidated into `main`.
- [x] `README.md` contains current judge-facing setup instructions.
- [x] `requirements.txt`, Dockerfiles, `docker-compose.yml` and `render.yaml` are visible.
- [x] `docs/submission/` is visible.
- [x] The MIT licence is visible.
- [ ] Open the repository while signed out and confirm all items above.
- [ ] Confirm no populated `.env` file, API key or private B2 object content is committed.

Because the repository is public, contributor access for `b2genblaze` is not required.

## 2. Public deployment

The Render Blueprint deploys both services from `main`:

```text
evidencecast-api-buriro-2026
evidencecast-web-buriro-2026
```

Public provider keys are intentionally omitted. Fixture mode works without them. Backblaze B2 values are configured only through Render secrets.

The frontend also sets:

```text
EVIDENCECAST_DISABLE_HEAVY_ASSEMBLY=1
```

This protects the Render Free service by disabling new Pillow, eSpeak and FFmpeg assembly controls while retaining workflow restoration, fixture exploration and consistency evaluation.

## 3. Automated public smoke test

From the repository root, run:

```bash
python scripts/smoke_test_deployment.py \
  --api-url https://evidencecast-api-buriro-2026.onrender.com \
  --web-url https://evidencecast-web-buriro-2026.onrender.com \
  --startup-timeout 240
```

Required passes:

- frontend health;
- backend health;
- backend readiness;
- fixture catalogue;
- `biolarviciding-community-acceptance`;
- `climate-finance-smallholders`; and
- `teacher-attendance-supervision`.

- [ ] Retain the exact output against the final commit.

Do not call the final deployment verified unless the exact output is retained.

## 4. Private-browser application test

Open a new private or incognito browser window with normal sessions excluded.

### Landing and navigation

- [ ] The Streamlit URL opens without authentication.
- [ ] No browser security or mixed-content warning appears.
- [ ] The application title and purpose are visible.
- [ ] Sidebar pages load without a Python exception.
- [ ] No API key, B2 application key or secret value appears.
- [ ] The public media-assembly controls are disabled with a clear resource-safety explanation.

### Judge fixtures

- [ ] Open **Fixture mode for judges**.
- [ ] All three fixtures appear.
- [ ] Load each fixture independently.
- [ ] Each fixture is explicitly labelled synthetic.
- [ ] Each fixture contains three approved evidence cards.
- [ ] Each fixture contains a three-scene approved-only storyboard.
- [ ] Each fixture contains three approved narration segments.
- [ ] Evidence-card IDs remain consistent across cards, scenes and narration.

### Backend behaviour

Open:

```text
https://evidencecast-api-buriro-2026.onrender.com/healthz
https://evidencecast-api-buriro-2026.onrender.com/readyz
https://evidencecast-api-buriro-2026.onrender.com/api/v1/capabilities
https://evidencecast-api-buriro-2026.onrender.com/api/v1/fixtures
```

- [ ] `/healthz` reports `status: ok`.
- [ ] `/readyz` reports `status: ready` and `fixture_count: 3`.
- [ ] Capabilities disclose configuration booleans only, never secret values.
- [ ] The fixture endpoint returns three records.

### Responsive and cold-start checks

- [ ] Refresh after at least five minutes of inactivity.
- [ ] Allow for a Render cold start and confirm the application recovers.
- [ ] Test at desktop width and a narrow mobile-width browser window.
- [ ] Confirm long B2 URIs and JSON blocks do not make essential controls unreachable.

## 5. Public repository test

- [ ] Open the repository URL while signed out.
- [ ] The final README renders.
- [ ] Setup instructions use `main`, not a historical feature branch.
- [ ] Application code, tests, fixtures and deployment files are accessible.
- [ ] No secret or populated `.env` file is present.
- [ ] The MIT licence is visible.

## 6. Devpost preview test

After entering the URLs in Devpost:

- [ ] Open the app link from the Devpost preview.
- [ ] Open the repository link from the Devpost preview.
- [ ] Play the complete video from the Devpost preview.
- [ ] Confirm the video is public and requires no sign-in.
- [ ] Confirm every provider and model is named accurately.
- [ ] Confirm provider integrations are distinguished from deterministic fallbacks.
- [ ] Confirm no statement claims a live provider asset that was not produced.
- [ ] Confirm the reviewed local delivery remains labelled `provider_generated: false`.

## 7. Final evidence to retain

Save:

- exact public web URL;
- exact public API URL;
- exact repository URL;
- public video URL;
- public smoke-test output;
- private-browser test date and time;
- final submitted commit SHA;
- Render deployment confirmation for both services; and
- Devpost submission confirmation screenshot.
