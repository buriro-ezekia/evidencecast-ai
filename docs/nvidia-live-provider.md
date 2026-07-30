# NVIDIA Live Provider Validation

## Purpose

This route removes the dependency on GMI Cloud credits by using an NVIDIA hosted API key while retaining Genblaze orchestration, Backblaze B2 persistence and manifest verification.

The first acceptance run is deliberately limited to:

1. one storyboard scene image; and
2. one approved narration segment.

The remaining scenes should be submitted only after the first asset in each modality produces a valid SHA-256, B2 manifest URI and `Manifest.verify() == True`.

## Security

The NVIDIA hosted key normally begins with `nvapi-`.

Never paste the key into Streamlit fields, source files, GitHub issues, screenshots, terminal output or chat messages. Add it only to the local `.env` file or deployment secret manager:

```text
NVIDIA_API_KEY=nvapi-...
```

The application exposes only `nvidia_configured: true|false`; it never returns the key.

## Install and update

```bash
git fetch origin
git switch feat/day-07-nvidia-provider
git pull origin feat/day-07-nvidia-provider
python -m pip install --upgrade -r requirements.txt
pytest -q
```

`requirements.txt` installs the official `genblaze-nvidia` connector.

## Start the application

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

Open **NVIDIA live validation** from the sidebar.

## Restore the approved workflow

The page defaults to the validated EvidenceCast records:

```text
Storyboard: SB-e27c3386b25a84a0
Narration: NP-15ad65aedbeaf9c0
```

Click **Restore NVIDIA validation inputs from B2** and confirm:

```text
Scenes: 3
Approved narration: 3
```

## Image validation

Default image model:

```text
stabilityai/stable-diffusion-3-5-large
```

The official Genblaze NVIDIA connector also recognises Stable Diffusion XL, Stable Diffusion 3.5 and FLUX-family slugs. Hosted availability can differ by account, so a model rejection or unavailable endpoint is recorded as a failed B2 summary rather than treated as success.

Select scene 1 and click:

```text
Generate one NVIDIA image through Genblaze
```

Success requires:

- a non-empty image asset;
- an asset SHA-256;
- a B2 manifest URI;
- a canonical manifest hash; and
- `Manifest.verify() == True`.

## Narration validation

Default narration settings:

```text
Model: nvidia/magpie-tts-multilingual
Language: en-US
Voice: Magpie-Multilingual.EN-US.Aria
Encoding: LINEAR_PCM
Sample rate: 44100 Hz
```

Select scene 1 and click:

```text
Generate one NVIDIA narration clip through Genblaze
```

The hosted Magpie endpoint receives the reviewer-approved narration text unchanged. The resulting WAV file is passed back into the Genblaze pipeline, uploaded to B2 and subjected to the same manifest checks as other provider assets.

## Environment options

```text
NVIDIA_API_KEY=
NVIDIA_IMAGE_MODEL=stabilityai/stable-diffusion-3-5-large
NVIDIA_AUDIO_MODEL=nvidia/magpie-tts-multilingual
NVIDIA_TTS_VOICE=Magpie-Multilingual.EN-US.Aria
NVIDIA_TTS_ENDPOINT=https://877104f7-e885-42b9-8de8-f6e4c6303969.invocation.api.nvcf.nvidia.com/v1/audio/synthesize
```

The endpoint is a public service URL, not a credential.

## Docker Compose

The Compose frontend passes all NVIDIA settings from the local `.env` file:

```bash
docker compose down --remove-orphans
docker compose build
docker compose up -d --wait --wait-timeout 180
```

## Render

`render.yaml` requests `NVIDIA_API_KEY` as a secret for `evidencecast-web` and supplies the non-secret model, voice and endpoint defaults. Fixture mode remains functional without the key.

## Acceptance evidence

Record for each successful modality:

- run ID;
- provider and model;
- scene number;
- asset B2 URI;
- asset SHA-256;
- manifest B2 URI;
- canonical manifest hash;
- `Manifest.verify()` result; and
- generation-summary B2 URI.

Do not describe a failed request, local Pillow image or eSpeak narration as NVIDIA-generated media.
