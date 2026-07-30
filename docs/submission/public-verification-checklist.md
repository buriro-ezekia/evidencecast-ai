# Public Application and Repository Verification

Complete this checklist only after the deployment and repository-access decisions are final.

## 1. Repository access decision

The hackathon accepts either:

- a public repository with setup instructions; or
- a private repository that grants GitHub user `b2genblaze` contributor access.

The current repository is private and `b2genblaze` currently has no access. For the simplest judge experience, make the repository public after confirming that no secrets, populated `.env` files or sensitive B2 object data are committed. Otherwise, keep it private and grant the required contributor access.

## 2. Deploy the public application

Use the root `render.yaml` to create:

- `evidencecast-api`; and
- `evidencecast-web`.

Add B2 values only through Render environment secrets. Provider keys are optional for fixture judging and must not be required to load the public app.

Record:

```text
EVIDENCECAST_WEB_PUBLIC_URL=
EVIDENCECAST_API_PUBLIC_URL=
REPOSITORY_URL=https://github.com/buriro-ezekia/evidencecast-ai
```

## 3. Automated public smoke test

From the repository root, run:

```bash
python scripts/smoke_test_deployment.py \
  --api-url "$EVIDENCECAST_API_PUBLIC_URL" \
  --web-url "$EVIDENCECAST_WEB_PUBLIC_URL" \
  --startup-timeout 180
```

Required passes:

- frontend health;
- backend health;
- backend readiness;
- fixture catalogue;
- `biolarviciding-community-acceptance`;
- `climate-finance-smallholders`; and
- `teacher-attendance-supervision`.

Do not call the deployment verified unless the exact command output is retained.

## 4. Private-browser application test

Open a new private or incognito browser window with all normal sessions excluded.

### Landing and navigation

- [ ] The public Streamlit URL opens without authentication.
- [ ] No browser security or mixed-content warning appears.
- [ ] The application title and purpose are visible.
- [ ] Sidebar pages load without a Python exception.
- [ ] No API key, B2 application key or secret value appears.

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

Open these public URLs directly in the private window:

```text
<API_URL>/healthz
<API_URL>/readyz
<API_URL>/api/v1/capabilities
<API_URL>/api/v1/fixtures
```

- [ ] `/healthz` reports `status: ok`.
- [ ] `/readyz` reports `status: ready` and `fixture_count: 3`.
- [ ] Capabilities disclose configuration booleans only, never secret values.
- [ ] The fixture endpoint returns three records.

### Responsive and cold-start checks

- [ ] Refresh the application after five minutes of inactivity.
- [ ] Allow for a Render cold start and confirm the application recovers.
- [ ] Test at desktop width and a narrow mobile-width browser window.
- [ ] Confirm long B2 URIs and JSON blocks do not make essential controls unreachable.

## 5. Private-browser repository test

### Public-repository route

- [ ] Open the repository URL while signed out.
- [ ] README renders.
- [ ] Setup instructions are visible.
- [ ] `requirements.txt`, Dockerfiles, `docker-compose.yml` and `render.yaml` are accessible.
- [ ] `docs/submission/` is accessible.
- [ ] No secret or populated `.env` file is present.
- [ ] The selected licence decision is visible, or the absence of a licence is accepted deliberately.

### Private-repository route

A private browser window without a GitHub session will normally show no repository. Therefore:

- [ ] Confirm `b2genblaze` has contributor access in **Settings → Collaborators**.
- [ ] Retain a screenshot showing the collaborator invitation or accepted access without exposing unrelated account information.
- [ ] Ensure Devpost clearly states that the repository is private and access has been granted.

## 6. Final Devpost link test

After entering the URLs in Devpost:

- [ ] Open the app link from the Devpost preview.
- [ ] Open the repository link from the Devpost preview.
- [ ] Play the complete video from the Devpost preview.
- [ ] Confirm the video is publicly visible and does not require sign-in.
- [ ] Confirm the description names every provider and model accurately.
- [ ] Confirm the description distinguishes provider integrations from the local reviewed fallback.
- [ ] Confirm no statement claims a live provider asset that was not actually produced.

## 7. Final evidence to retain

Save the following in the submission issue or a private local checklist:

- exact public web URL;
- exact public API URL;
- exact repository URL and visibility decision;
- public video URL;
- public smoke-test output;
- private-browser test date and time;
- final branch or commit SHA submitted; and
- Devpost submission confirmation screenshot.
