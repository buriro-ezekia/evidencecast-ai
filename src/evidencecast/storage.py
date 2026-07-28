# Stores EvidenceCast source documents, extracted text and review artefacts in Backblaze B2.
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError


class StorageConfigurationError(RuntimeError):
    """Raised when required Backblaze B2 configuration is missing or invalid."""


class StorageOperationError(RuntimeError):
    """Raised when a B2 object operation fails."""


@dataclass(frozen=True)
class B2Settings:
    """Validated Backblaze B2 S3-compatible settings."""

    key_id: str
    app_key: str
    bucket: str
    region: str
    prefix: str = "evidencecast"

    @classmethod
    def from_environment(cls) -> "B2Settings":
        values = {
            "key_id": os.getenv("B2_KEY_ID", "").strip(),
            "app_key": os.getenv("B2_APP_KEY", "").strip(),
            "bucket": os.getenv("B2_BUCKET", "").strip(),
            "region": os.getenv("B2_REGION", "").strip(),
            "prefix": os.getenv("EVIDENCECAST_B2_PREFIX", "evidencecast").strip().strip("/"),
        }
        missing = [name for name in ("key_id", "app_key", "bucket", "region") if not values[name]]
        if missing:
            raise StorageConfigurationError(
                "Missing B2 configuration: " + ", ".join(sorted(missing))
            )
        if not values["prefix"]:
            values["prefix"] = "evidencecast"
        return cls(**values)

    @property
    def endpoint_url(self) -> str:
        return f"https://s3.{self.region}.backblazeb2.com"


@dataclass(frozen=True)
class StoredObject:
    """A durable B2 object reference with integrity metadata."""

    bucket: str
    key: str
    sha256: str
    size_bytes: int
    media_type: str

    @property
    def uri(self) -> str:
        return f"b2://{self.bucket}/{self.key}"


class B2EvidenceStore:
    """Small S3-compatible repository for EvidenceCast source and review artefacts."""

    def __init__(self, settings: B2Settings) -> None:
        self.settings = settings
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.endpoint_url,
            region_name=settings.region,
            aws_access_key_id=settings.key_id,
            aws_secret_access_key=settings.app_key,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    @staticmethod
    def sha256_bytes(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def safe_filename(filename: str) -> str:
        base_name = Path(filename).name
        stem = re.sub(r"[^A-Za-z0-9._-]+", "-", base_name).strip("-.")
        return stem or "source.bin"

    def put_bytes(
        self,
        *,
        key: str,
        data: bytes,
        media_type: str,
        metadata: dict[str, str] | None = None,
    ) -> StoredObject:
        sha256 = self.sha256_bytes(data)
        object_metadata = {"sha256": sha256}
        if metadata:
            object_metadata.update({str(k): str(v) for k, v in metadata.items()})

        try:
            self.client.put_object(
                Bucket=self.settings.bucket,
                Key=key,
                Body=data,
                ContentType=media_type,
                Metadata=object_metadata,
            )
        except (BotoCoreError, ClientError) as exc:
            raise StorageOperationError(f"Could not upload b2://{self.settings.bucket}/{key}: {exc}") from exc

        return StoredObject(
            bucket=self.settings.bucket,
            key=key,
            sha256=sha256,
            size_bytes=len(data),
            media_type=media_type,
        )

    def put_json(self, *, key: str, value: Any) -> StoredObject:
        payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        return self.put_bytes(key=key, data=payload, media_type="application/json")

    def source_root(self, source_sha256: str) -> str:
        return f"{self.settings.prefix}/sources/{source_sha256[:2]}/{source_sha256}"

    def store_source_bundle(
        self,
        *,
        filename: str,
        media_type: str,
        source_bytes: bytes,
        extracted_text: str,
        extraction_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        source_sha256 = self.sha256_bytes(source_bytes)
        root = self.source_root(source_sha256)
        safe_name = self.safe_filename(filename)
        resolved_media_type = media_type or mimetypes.guess_type(safe_name)[0] or "application/octet-stream"

        original = self.put_bytes(
            key=f"{root}/original/{safe_name}",
            data=source_bytes,
            media_type=resolved_media_type,
            metadata={"source-filename": safe_name},
        )
        extracted = self.put_bytes(
            key=f"{root}/derived/extracted.txt",
            data=extracted_text.encode("utf-8"),
            media_type="text/plain; charset=utf-8",
        )
        metadata_payload = {
            "source_sha256": source_sha256,
            "stored_at": datetime.now(UTC).isoformat(),
            "original": {
                "uri": original.uri,
                "sha256": original.sha256,
                "size_bytes": original.size_bytes,
                "media_type": original.media_type,
            },
            "extracted_text": {
                "uri": extracted.uri,
                "sha256": extracted.sha256,
                "size_bytes": extracted.size_bytes,
                "media_type": extracted.media_type,
            },
            "extraction": extraction_metadata,
        }
        metadata_object = self.put_json(key=f"{root}/derived/extraction.json", value=metadata_payload)
        metadata_payload["extraction_metadata_uri"] = metadata_object.uri
        return metadata_payload

    def store_evidence_cards(
        self,
        *,
        source_sha256: str,
        cards: list[dict[str, Any]],
        review_status: str,
    ) -> StoredObject:
        payload = {
            "source_sha256": source_sha256,
            "review_status": review_status,
            "saved_at": datetime.now(UTC).isoformat(),
            "cards": cards,
        }
        return self.put_json(
            key=f"{self.source_root(source_sha256)}/reviews/evidence-cards.json",
            value=payload,
        )
