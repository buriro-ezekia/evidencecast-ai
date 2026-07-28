# Extends EvidenceCast B2 storage with narration plans, audio intermediates and progress records.
from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from .storage import B2EvidenceStore, StorageOperationError, StoredObject


class B2AudioStore(B2EvidenceStore):
    """Backblaze B2 repository for narration-review and audio-generation artefacts."""

    @staticmethod
    def _safe_identifier(value: str, label: str) -> str:
        safe_value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
        if not safe_value:
            raise StorageOperationError(f"{label} cannot be empty.")
        return safe_value

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
