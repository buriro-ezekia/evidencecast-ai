# Stores final media, evaluations, assembly manifests and regeneration lineage in Backblaze B2.
from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError

from .audio_store import B2AudioStore
from .storage import StorageOperationError, StoredObject


class B2FinalMediaStore(B2AudioStore):
    """Backblaze B2 repository for final delivery and evaluation artefacts."""

    @staticmethod
    def _safe_id(value: str, label: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
        if not safe:
            raise StorageOperationError(f"{label} cannot be empty.")
        return safe

    def delivery_root(self, source_sha256: str, storyboard_id: str, delivery_id: str) -> str:
        return (
            f"{self.storyboard_root(source_sha256, storyboard_id)}/deliveries/"
            f"{self._safe_id(delivery_id, 'Delivery ID')}"
        )

    def regeneration_root(
        self,
        source_sha256: str,
        storyboard_id: str,
        child_run_id: str,
    ) -> str:
        return (
            f"{self.storyboard_root(source_sha256, storyboard_id)}/regenerations/"
            f"{self._safe_id(child_run_id, 'Child run ID')}"
        )

    def store_evaluation_report(
        self,
        *,
        source_sha256: str,
        storyboard_id: str,
        evaluation: dict[str, Any],
    ) -> StoredObject:
        evaluation_id = self._safe_id(str(evaluation["evaluation_id"]), "Evaluation ID")
        return self.put_json(
            key=(
                f"{self.storyboard_root(source_sha256, storyboard_id)}/evaluations/"
                f"{evaluation_id}.json"
            ),
            value=evaluation,
        )

    def store_delivery_asset(
        self,
        *,
        source_sha256: str,
        storyboard_id: str,
        delivery_id: str,
        filename: str,
        data: bytes,
        media_type: str,
        role: str,
    ) -> StoredObject:
        safe_filename = self.safe_filename(filename)
        return self.put_bytes(
            key=f"{self.delivery_root(source_sha256, storyboard_id, delivery_id)}/assets/{safe_filename}",
            data=data,
            media_type=media_type,
            metadata={"delivery-id": delivery_id, "asset-role": role},
        )

    def store_subtitle_asset(
        self,
        *,
        source_sha256: str,
        storyboard_id: str,
        delivery_id: str,
        filename: str,
        text: str,
        media_type: str,
    ) -> StoredObject:
        return self.put_bytes(
            key=f"{self.delivery_root(source_sha256, storyboard_id, delivery_id)}/subtitles/{self.safe_filename(filename)}",
            data=text.encode("utf-8"),
            media_type=media_type,
            metadata={"delivery-id": delivery_id, "asset-role": "subtitles"},
        )

    def store_assembly_manifest(
        self,
        *,
        source_sha256: str,
        storyboard_id: str,
        delivery_id: str,
        manifest: dict[str, Any],
    ) -> StoredObject:
        return self.put_json(
            key=f"{self.delivery_root(source_sha256, storyboard_id, delivery_id)}/assembly-manifest.json",
            value=manifest,
        )

    def store_regeneration_request(
        self,
        *,
        source_sha256: str,
        storyboard_id: str,
        child_run_id: str,
        request: dict[str, Any],
    ) -> StoredObject:
        return self.put_json(
            key=f"{self.regeneration_root(source_sha256, storyboard_id, child_run_id)}/request.json",
            value=request,
        )

    def store_regeneration_attempt(
        self,
        *,
        source_sha256: str,
        storyboard_id: str,
        child_run_id: str,
        attempt: int,
        record: dict[str, Any],
    ) -> StoredObject:
        return self.put_json(
            key=(
                f"{self.regeneration_root(source_sha256, storyboard_id, child_run_id)}"
                f"/attempts/{attempt:02d}.json"
            ),
            value=record,
        )

    def store_regeneration_summary(
        self,
        *,
        source_sha256: str,
        storyboard_id: str,
        child_run_id: str,
        summary: dict[str, Any],
    ) -> StoredObject:
        return self.put_json(
            key=f"{self.regeneration_root(source_sha256, storyboard_id, child_run_id)}/summary.json",
            value=summary,
        )

    def store_lineage_edge(
        self,
        *,
        source_sha256: str,
        storyboard_id: str,
        child_run_id: str,
        parent_run_id: str,
        media_kind: str,
        scene_number: int,
    ) -> StoredObject:
        payload = {
            "parent_run_id": parent_run_id,
            "child_run_id": child_run_id,
            "relationship": "scene_regeneration",
            "media_kind": media_kind,
            "scene_number": scene_number,
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        return self.put_json(
            key=f"{self.regeneration_root(source_sha256, storyboard_id, child_run_id)}/lineage.json",
            value=payload,
        )

    def verify_stored_object(self, stored: StoredObject) -> dict[str, Any]:
        """Verify the B2 object metadata SHA and content length after upload."""

        try:
            response = self.client.head_object(Bucket=stored.bucket, Key=stored.key)
        except (BotoCoreError, ClientError) as exc:
            raise StorageOperationError(f"Could not verify {stored.uri}: {exc}") from exc
        remote_sha = str(response.get("Metadata", {}).get("sha256", "")).lower()
        remote_size = int(response.get("ContentLength", -1))
        verified = remote_sha == stored.sha256.lower() and remote_size == stored.size_bytes
        return {
            "uri": stored.uri,
            "local_sha256": stored.sha256,
            "remote_sha256": remote_sha,
            "local_size_bytes": stored.size_bytes,
            "remote_size_bytes": remote_size,
            "verified": verified,
            "verified_at": datetime.now(UTC).isoformat(),
        }
