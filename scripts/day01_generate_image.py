# Generates one EvidenceCast image with a selectable Genblaze provider, stores it and its manifest in Backblaze B2, and verifies provenance integrity.
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from genblaze_core import KeyStrategy, Modality, ObjectStorageSink, Pipeline
from genblaze_gmicloud import GMICloudImageProvider
from genblaze_s3 import S3StorageBackend

DEFAULT_PROMPT = (
    "A professional editorial infographic illustrating how trusted research evidence "
    "is transformed into an accessible community communication story, showing a "
    "research report, verified evidence cards, an infographic, narrated audio and a "
    "short video connected by a clear provenance trail, clean modern composition, "
    "credible public-interest design, no logos, no watermarks, 16:9"
)

BASE_REQUIRED_ENVIRONMENT_VARIABLES = (
    "B2_KEY_ID",
    "B2_APP_KEY",
    "B2_BUCKET",
)

PROVIDER_ENVIRONMENT_VARIABLES = {
    "gmicloud": "GMI_API_KEY",
    "openai": "OPENAI_API_KEY",
}

DEFAULT_MODELS = {
    "gmicloud": "seedream-5.0-lite",
    "openai": "gpt-image-1",
}

B2_BUCKET_ID_PATTERN = re.compile(r"^[0-9a-fA-F]{24}$")
B2_S3_BUCKET_NAME_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{1,61}[a-z0-9])$")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate one image through Genblaze, upload the image and provenance "
            "manifest to Backblaze B2, and verify the manifest."
        )
    )
    parser.add_argument(
        "--provider",
        choices=tuple(PROVIDER_ENVIRONMENT_VARIABLES),
        default=os.getenv("IMAGE_PROVIDER", "gmicloud").strip().lower(),
        help="Image provider to use. Defaults to IMAGE_PROVIDER or gmicloud.",
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="Text prompt used for image generation.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Provider model. Defaults to seedream-5.0-lite or gpt-image-1.",
    )
    parser.add_argument(
        "--aspect-ratio",
        default="16:9",
        help="GMI Cloud image aspect ratio.",
    )
    parser.add_argument(
        "--size",
        default="1536x1024",
        help="OpenAI image size.",
    )
    parser.add_argument(
        "--quality",
        default="low",
        help="OpenAI image quality. Low is the cost-conscious default for the smoke test.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Maximum generation time in seconds.",
    )
    parser.add_argument(
        "--summary",
        default="artifacts/day01-result.json",
        help="Local path for a non-secret execution summary.",
    )
    return parser.parse_args()


def validate_bucket_name(bucket_name: str) -> None:
    if B2_BUCKET_ID_PATTERN.fullmatch(bucket_name):
        raise RuntimeError(
            "B2_BUCKET contains a 24-character Backblaze bucket ID. Genblaze's "
            "S3-compatible backend requires the bucket's unique name instead. Open "
            "Backblaze B2 > Buckets, copy the value under 'Bucket Name', and place "
            "that value in B2_BUCKET."
        )

    if not B2_S3_BUCKET_NAME_PATTERN.fullmatch(bucket_name):
        raise RuntimeError(
            "B2_BUCKET is not a valid S3-compatible bucket name. Use the exact "
            "Backblaze bucket name, preferably lowercase letters, numbers and hyphens, "
            "not the bucket ID."
        )


def require_environment(provider_name: str) -> dict[str, str]:
    provider_variable = PROVIDER_ENVIRONMENT_VARIABLES[provider_name]
    required_names = (*BASE_REQUIRED_ENVIRONMENT_VARIABLES, provider_variable)
    values = {name: os.getenv(name, "").strip() for name in required_names}
    missing = [name for name, value in values.items() if not value]

    if missing:
        missing_text = ", ".join(missing)
        raise RuntimeError(
            f"Missing required environment variables: {missing_text}. "
            "Copy .env.example to .env and provide the values locally."
        )

    validate_bucket_name(values["B2_BUCKET"])

    # Replace raw dotenv values with stripped values before SDKs read them.
    for name, value in values.items():
        os.environ[name] = value

    region = os.getenv("B2_REGION", "").strip()
    if region:
        os.environ["B2_REGION"] = region
        values["B2_REGION"] = region

    return values


def create_storage(environment: dict[str, str]) -> ObjectStorageSink:
    backend_options: dict[str, Any] = {
        "auto_lifecycle": False,
        "key_id": environment["B2_KEY_ID"],
        "app_key": environment["B2_APP_KEY"],
    }
    region = environment.get("B2_REGION", "")
    if region:
        backend_options["region"] = region

    try:
        backend = S3StorageBackend.for_backblaze(
            environment["B2_BUCKET"],
            **backend_options,
        )
    except Exception as exc:
        error_text = str(exc)
        if "InvalidAccessKeyId" in error_text or "Malformed Access Key Id" in error_text:
            raise RuntimeError(
                "Backblaze rejected the S3 access-key identifier as malformed. Confirm "
                "that B2_KEY_ID is the keyID from a manually created standard application "
                "key—not the master key, key name, account ID, bucket ID or secret."
            ) from exc
        if "403" in error_text or "Forbidden" in error_text:
            raise RuntimeError(
                "Backblaze rejected the bucket preflight with HTTP 403. Confirm that "
                "B2_BUCKET is the exact bucket name, B2_REGION matches the bucket's S3 "
                "endpoint, B2_KEY_ID/B2_APP_KEY belong to the same restricted key, and "
                "the key has Read and Write access plus 'Allow List All Bucket Names' "
                "enabled for S3-compatible SDK access."
            ) from exc
        raise

    return ObjectStorageSink(
        backend,
        key_strategy=KeyStrategy.HIERARCHICAL,
    )


def create_provider_step(
    args: argparse.Namespace,
) -> tuple[Any, str, dict[str, Any]]:
    model = args.model or DEFAULT_MODELS[args.provider]

    if args.provider == "gmicloud":
        provider = GMICloudImageProvider()
        parameters = {"aspect_ratio": args.aspect_ratio}
        return provider, model, parameters

    try:
        from genblaze_openai import DalleProvider
    except ImportError as exc:
        raise RuntimeError(
            "The OpenAI fallback is not installed. Run 'pip install -r requirements.txt' "
            "after pulling the latest branch."
        ) from exc

    provider = DalleProvider()
    parameters = {
        "size": args.size,
        "quality": args.quality,
    }
    return provider, model, parameters


def raise_for_failed_generation(result: Any, provider_name: str) -> None:
    if not result.failed_steps():
        return

    error_summary = result.error_summary() or "Unknown provider failure."
    normalised_error = error_summary.lower()

    if provider_name == "gmicloud" and (
        "insufficient credits" in normalised_error or "402" in normalised_error
    ):
        raise RuntimeError(
            "GMI Cloud authenticated the request but refused generation because the "
            "organisation has insufficient credits. No image was generated and the Day 1 "
            "live-media check remains pending. Add credit in the GMI Cloud Billing area, "
            "then rerun this command. Alternatively, configure OPENAI_API_KEY with funded "
            "OpenAI API billing and run: python scripts/day01_generate_image.py "
            "--provider openai."
        )

    raise RuntimeError(f"Genblaze image generation failed:\n{error_summary}")


def write_summary(path: str, summary: dict[str, Any]) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output_path


def main() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    load_dotenv(dotenv_path=repository_root / ".env", override=True)
    args = parse_arguments()
    environment = require_environment(args.provider)
    storage = create_storage(environment)
    provider, model, provider_parameters = create_provider_step(args)

    result = (
        Pipeline(
            "evidencecast-day01-image",
            project_id="evidencecast-ai",
        )
        .step(
            provider,
            model=model,
            prompt=args.prompt,
            modality=Modality.IMAGE,
            **provider_parameters,
        )
        .run(
            sink=storage,
            timeout=args.timeout,
            max_retries=1,
            raise_on_failure=False,
        )
    )

    if not result.run.steps:
        raise RuntimeError("Genblaze completed without recording a pipeline step.")

    raise_for_failed_generation(result, args.provider)

    first_step = result.run.steps[0]
    if not first_step.assets:
        raise RuntimeError(
            f"The generation step completed with status {first_step.status!s} "
            "but returned no image asset."
        )

    asset = first_step.assets[0]
    verified = result.manifest.verify()

    if not asset.sha256:
        raise RuntimeError("The B2-persisted image asset has no SHA-256 value.")
    if not result.manifest.manifest_uri:
        raise RuntimeError("The provenance manifest was not persisted to B2.")
    if not verified:
        raise RuntimeError("Manifest.verify() returned False.")

    summary = {
        "pipeline": "evidencecast-day01-image",
        "project_id": "evidencecast-ai",
        "run_id": result.run.run_id,
        "step_status": str(first_step.status),
        "provider": args.provider,
        "model": model,
        "bucket": environment["B2_BUCKET"],
        "asset_url": asset.url,
        "asset_sha256": asset.sha256,
        "asset_mime_type": asset.mime_type,
        "manifest_uri": result.manifest.manifest_uri,
        "manifest_canonical_hash": result.manifest.canonical_hash,
        "manifest_verified": verified,
    }
    summary_path = write_summary(args.summary, summary)

    print("EvidenceCast Day 1 vertical slice completed successfully.")
    print(f"Run ID:            {summary['run_id']}")
    print(f"Provider/model:     {summary['provider']}/{summary['model']}")
    print(f"Image location:     {summary['asset_url']}")
    print(f"Image SHA-256:      {summary['asset_sha256']}")
    print(f"Manifest location:  {summary['manifest_uri']}")
    print(f"Manifest hash:      {summary['manifest_canonical_hash']}")
    print(f"Manifest verified:  {summary['manifest_verified']}")
    print(f"Local summary:      {summary_path}")


if __name__ == "__main__":
    main()
