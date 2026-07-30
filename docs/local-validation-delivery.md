# Local Validation Delivery

## Purpose

The local validation pathway completes a reviewed FFmpeg delivery package when paid provider media is unavailable. It is a functional fallback, not a substitute claim of successful provider generation.

It creates:

- three 1280 × 720 evidence-grounded PNG scene images with Pillow;
- three approved narration WAV files with eSpeak NG;
- SRT subtitles;
- WebVTT subtitles;
- a captioned MP4 assembled with FFmpeg;
- a 1280 × 720 thumbnail;
- a 1080 × 1350 infographic; and
- an assembly manifest containing B2 integrity verification results.

The inputs are deliberately labelled as local validation assets. They must not be described as provider-generated or as successful GMI, NVIDIA, OpenAI or Genblaze media outputs.

## Public hosted behaviour

The public Render Free service sets:

```text
EVIDENCECAST_DISABLE_HEAVY_ASSEMBLY=1
```

This disables the **Generate, assemble and verify local delivery** control on the hosted Streamlit instance. Judges can still restore and inspect the approved workflow, but the small 512 MB service is protected from a repeated resource-exhaustion failure.

Run the full pathway locally or on an adequately provisioned private instance with:

```text
EVIDENCECAST_DISABLE_HEAVY_ASSEMBLY=0
```

## Install system dependencies

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg espeak-ng

ffmpeg -version
ffprobe -version
espeak-ng --version
```

## Update the supported branch

```bash
git fetch origin
git switch main
git pull origin main
pip install -r requirements.txt
pytest -q
```

## Start the application locally

```bash
EVIDENCECAST_DISABLE_HEAVY_ASSEMBLY=0 \
streamlit run app.py --server.address=0.0.0.0 --server.port=8501
```

Open **Local validation delivery** in the Streamlit sidebar.

## Build the package

1. Click **Restore approved workflow from B2**.
2. Confirm storyboard `SB-e27c3386b25a84a0` and narration `NP-15ad65aedbeaf9c0` are displayed.
3. Click **Generate, assemble and verify local delivery**.
4. Allow the seven stages to finish.

The page performs:

```text
Evidence consistency evaluation
        ↓
Three local evidence-scene PNG files
        ↓
Three approved eSpeak narration WAV files
        ↓
FFprobe duration measurement
        ↓
SRT and WebVTT generation
        ↓
Captioned MP4 composition with FFmpeg
        ↓
Thumbnail and infographic export
        ↓
B2 upload and integrity verification
        ↓
Assembly manifest
```

## Disclosure recorded in the manifest

```json
{
  "delivery_mode": "local_validation_fallback",
  "provider_generated": false,
  "image_generator": "pillow",
  "narration_generator": "espeak"
}
```

Each scene image also visibly states:

```text
LOCAL VALIDATION ASSET
Built from approved evidence; not provider-generated
```

## B2 layout

```text
{storyboard-root}/deliveries/{delivery-id}/
├── assets/
│   ├── scene-01-local.png
│   ├── scene-01-local.wav
│   ├── scene-02-local.png
│   ├── scene-02-local.wav
│   ├── scene-03-local.png
│   ├── scene-03-local.wav
│   ├── evidencecast-captioned.mp4
│   ├── thumbnail.jpg
│   └── infographic.png
├── subtitles/
│   ├── captions.srt
│   └── captions.vtt
└── assembly-manifest.json
```

Every stored input and output carries SHA-256 metadata and is checked against the remote B2 object size before the manifest can report `completed`.

## Verified example

```text
Delivery ID: DEL-LOCAL-20260729T082428Z-aaa74869
Status: completed
Provider-generated: False
Input origin: local Pillow images and eSpeak narration
```

The verified assembly manifest is stored under the corresponding B2 delivery root and retains the source SHA-256, storyboard ID, narration ID, input records, output records and B2 integrity checks.

## Acceptance evidence to retain

Record:

- delivery ID;
- assembly-manifest B2 URI;
- manifest status;
- final MP4 B2 URI and SHA-256;
- subtitle B2 URIs;
- thumbnail and infographic B2 URIs;
- confirmation that every B2 verification is `true`; and
- a clear note that the six inputs were local validation assets rather than provider-generated assets.
