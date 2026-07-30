# Extends EvidenceCast B2 storage with narration plans, audio intermediates and progress records.
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError

from .storage import B2EvidenceStore, StorageOperationError, StoredObject


class B2AudioStore(B2EvidenceStore):
    """Backblaze B2 repository for narration-review and audio-generation artefacts."""

    @staticmethod
    def _safe_identifier(value: str, label: str) -> str:
        safe_value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
        if not safe_value:
            raise StorageOperationError(f"{label} cannot be empty.")
        return safe_value

    def load_json_from_b2_uri(self, uri: str) -> dict[str, Any]:
        """Load a JSON object from this store's configured bucket using a strict B2 URI."""

        candidate = uri.strip()
        match = re.fullmatch(r"b2://([^/]+)/(.+)", candidate)
        if not match:
            raise StorageOperationError(
                "Enter a complete B2 URI in the form b2://bucket-name/path/to/file.json."
            )
        bucket, key = match.groups()
        if bucket != self.settings.bucket:
            raise StorageOperationError(
                f"The URI points to bucket '{bucket}', but this application is configured for "
                f"'{self.settings.bucket}'."
            )
        if not key.lower().endswith(".json"):
            raise StorageOperationError("The selected B2 object must be a JSON file.")

        try:
            response = self.client.get_object(Bucket=bucket, Key=key)
            raw = response["Body"].read()
            value = json.loads(raw.decode("utf-8"))
        except (BotoCoreError, ClientError, UnicodeDecodeError, json.JSONDecodeError, KeyError) as exc:
            raise StorageOperationError(f"Could not load {candidate}: {exc}") from exc

        if not isinstance(value, dict):
            raise StorageOperationError("The B2 JSON object must contain a top-level JSON object.")
        return value

    def narration_root(
        self,
        source_sha256: str,
        storyboard_id: str,
        narration_id: str,
    ) -> str:
        safe_narration_id = self._safe_identifier(narration_id, "Narration ID")
        return f"{self.storyboard_root(source_sha256, storyboard_id)}/narration/{safe_narration_id}"

    def audio_run_root(
        self,
        source_sha256: str,
        storyboard_id: str,
        narration_id: str,
        audio_run_id: str,
    ) -> str:
        safe_audio_run_id = self._safe_identifier(audio_run_id, "Audio run ID")
        return (
            f"{self.narration_root(source_sha256, storyboard_id, narration_id)}"
            f"/runs/{safe_audio_run_id}"
        )

    def store_narration_plan(
        self,
        *,
        source_sha256: str,
        storyboard_id: str,
        narration_id: str,
        narration_plan: dict[str, Any],
    ) -> StoredObject:
        return self.put_json(
            key=(
                f"{self.narration_root(source_sha256, storyboard_id, narration_id)}"
                "/narration-plan.json"
            ),
            value=narration_plan,
        )

    def store_narration_review(
        self,
        *,
        source_sha256: str,
        storyboard_id: str,
        narration_id: str,
        segments: list[dict[str, Any]],
        review_status: str,
        language: str,
        voice_style: str,
    ) -> StoredObject:
        payload = {
            "narration_id": narration_id,
            "storyboard_id": storyboard_id,
            "source_sha256": source_sha256,
            "review_status": review_status,
            "language": language,
            "voice_style": voice_style,
            "saved_at": datetime.now(UTC).isoformat(),
            "segments": segments,
        }
        return self.put_json(
            key=(
                f"{self.narration_root(source_sha256, storyboard_id, narration_id)}"
                "/narration-review.json"
            ),
            value=payload,
        )

    def store_audio_generation_request(
        self,
        *,
        source_sha256: str,
        storyboard_id: str,
        narration_id: str,
        audio_run_id: str,
        request: dict[str, Any],
    ) -> StoredObject:
        return self.put_json(
            key=(
                f"{self.audio_run_root(source_sha256, storyboard_id, narration_id, audio_run_id)}"
                "/generation-request.json"
            ),
            value=request,
        )

    def store_audio_segment_request(
        self,
        *,
        source_sha256: str,
        storyboard_id: str,
        narration_id: str,
        audio_run_id: str,
        scene_number: int,
        request: dict[str, Any],
    ) -> StoredObject:
        return self.put_json(
            key=(
                f"{self.audio_run_root(source_sha256, storyboard_id, narration_id, audio_run_id)}"
                f"/segments/scene-{scene_number:02d}/request.json"
            ),
            value=request,
        )

    def store_audio_segment_result(
        self,
        *,
        source_sha256: str,
        storyboard_id: str,
        narration_id: str,
        audio_run_id: str,
        scene_number: int,
        result: dict[str, Any],
    ) -> StoredObject:
        return self.put_json(
            key=(
                f"{self.audio_run_root(source_sha256, storyboard_id, narration_id, audio_run_id)}"
                f"/segments/scene-{scene_number:02d}/result.json"
            ),
            value=result,
        )

    def store_audio_progress_event(
        self,
        *,
        source_sha256: str,
        storyboard_id: str,
        narration_id: str,
        audio_run_id: str,
        sequence: int,
        event: dict[str, Any],
    ) -> StoredObject:
        root = self.audio_run_root(source_sha256, storyboard_id, narration_id, audio_run_id)
        immutable = self.put_json(
            key=f"{root}/progress/events/{sequence:03d}.json",
            value=event,
        )
        self.put_json(key=f"{root}/progress/current.json", value=event)
        return immutable

    def store_audio_generation_summary(
        self,
        *,
        source_sha256: str,
        storyboard_id: str,
        narration_id: str,
        audio_run_id: str,
        summary: dict[str, Any],
    ) -> StoredObject:
        return self.put_json(
            key=(
                f"{self.audio_run_root(source_sha256, storyboard_id, narration_id, audio_run_id)}"
                "/generation-summary.json"
            ),
            value=summary,
        )
