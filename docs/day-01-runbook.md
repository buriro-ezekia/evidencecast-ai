# Day 1 Runbook: Genblaze Image Generation and Backblaze B2 Persistence

## Objective

Complete one working vertical slice that:

1. generates an image through the GMI Cloud Genblaze connector;
2. stores the generated image in the private Backblaze B2 bucket;
3. stores the canonical Genblaze provenance manifest alongside the asset;
4. confirms that the asset has a SHA-256 hash; and
5. confirms that `Manifest.verify()` returns `True`.

## Prerequisites

- Python 3.11 or later.
- A private Backblaze B2 bucket.
- A bucket-restricted Backblaze application key with read and write access to that bucket.
- A GMI Cloud API key.
- The Genblaze GitHub repository starred from the hackathon participant's GitHub account.

## Local setup

```bash
git clone https://github.com/buriro-ezekia/evidencecast-ai.git
cd evidencecast-ai
git switch feat/day-01-genblaze-b2

python -m venv .venv
```

Activate the environment on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the dependencies:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Create the local configuration file:

```powershell
Copy-Item .env.example .env
```

Populate `.env` locally:

```dotenv
B2_KEY_ID=your_bucket_restricted_key_id
B2_APP_KEY=your_bucket_restricted_application_key
B2_BUCKET=your_exact_bucket_name
B2_REGION=your_bucket_region
GMI_API_KEY=your_gmi_cloud_api_key
```

Do not paste these credentials into GitHub issues, source files, commits, screenshots or the Devpost description.

## Execute the vertical slice

```bash
python scripts/day01_generate_image.py
```

A successful execution prints:

- the Genblaze run ID;
- the B2 image location;
- the image SHA-256 value;
- the B2 manifest location;
- the canonical manifest hash; and
- `Manifest verified: True`.

It also writes a non-secret local summary to:

```text
artifacts/day01-result.json
```

The `artifacts/` directory is excluded from Git so that generated outputs are not committed accidentally.

## Verification in Backblaze

Open the Backblaze bucket and confirm that the run created both generated media and provenance data. The exact object hierarchy is controlled by Genblaze's hierarchical key strategy, so use the printed run ID or manifest location to identify the objects.

## Completion criteria

Day 1 is complete only when all of the following are true:

- [x] Devpost project created.
- [x] GitHub repository created.
- [x] Private B2 bucket created.
- [x] Bucket-restricted B2 application key created.
- [x] Genblaze dependencies and one image-provider connector defined.
- [ ] Image generated successfully.
- [ ] Image persisted to B2 with a SHA-256 value.
- [ ] Provenance manifest persisted to B2.
- [ ] `Manifest.verify()` returned `True`.
- [ ] Non-secret execution evidence recorded for the project documentation.

## Troubleshooting

### Missing environment variables

Copy `.env.example` to `.env`, then enter the required values. Do not add `.env` to Git.

### B2 access denied

Confirm that the application key is restricted to the correct bucket and has permission to read and write files. Confirm that `B2_BUCKET` matches the bucket name exactly.

### Incorrect B2 region

Enter the bucket's region in `B2_REGION`. Valid examples currently include `us-west-002`, `us-west-004`, `us-east-005` and `eu-central-003`.

### No generated asset

Confirm that `GMI_API_KEY` is active and that the selected GMI Cloud model is available. The default model in the script is `seedream-5.0-lite`.

### Manifest verification fails

Do not mark Day 1 complete. Retain the console output, inspect whether the image was persisted by the storage sink, and confirm that the returned asset contains a SHA-256 value before retrying.
