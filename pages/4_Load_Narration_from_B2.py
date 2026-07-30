# Restores an approved narration review and its storyboard from Backblaze B2 after a Streamlit restart.
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from evidencecast.audio_store import B2AudioStore
from evidencecast.narration import NarrationValidationError, require_all_segments_approved
from evidencecast.storage import B2Settings, StorageConfigurationError, StorageOperationError

load_dotenv(REPOSITORY_ROOT / ".env", override=True)

st.set_page_config(
    page_title="Load Narration from B2",
    page_icon="♻️",
    layout="wide",
)

st.title("Load approved narration from B2")
st.caption(
    "Restore an already reviewed narration package and its linked storyboard after a Streamlit "
    "restart, without repeating evidence review or narration editing."
)

review_uri = st.text_input(
    "B2 narration-review URI",
    value=(
        "b2://evidencecast-ai-buriro-2026/evidencecast/sources/c9/"
        "c959ebebe624ebec10c23a73c7ec1a4e4a270feacaa0748d4a7a7fbbf7f9fcfe/"
        "storyboards/SB-e27c3386b25a84a0/narration/NP-15ad65aedbeaf9c0/"
        "narration-review.json"
    ),
)

if st.button("Load narration review into this session", type="primary", use_container_width=True):
    try:
        store = B2AudioStore(B2Settings.from_environment())
        review = store.load_json_from_b2_uri(review_uri)

        required_fields = {
            "narration_id",
            "storyboard_id",
            "source_sha256",
            "review_status",
            "language",
            "voice_style",
            "segments",
        }
        missing = sorted(required_fields - set(review))
        if missing:
            raise NarrationValidationError(
                "The narration review is missing required fields: " + ", ".join(missing)
            )
        if review.get("review_status") != "completed":
            raise NarrationValidationError(
                "The narration review must have status 'completed' before it can be restored."
            )
        segments = list(review.get("segments", []))
        require_all_segments_approved(segments)

        source_sha256 = str(review["source_sha256"])
        storyboard_id = str(review["storyboard_id"])
        storyboard_uri = (
            f"b2://{store.settings.bucket}/{store.storyboard_root(source_sha256, storyboard_id)}"
            "/storyboard.json"
        )
        storyboard = store.load_json_from_b2_uri(storyboard_uri)
        if storyboard.get("scene_count") != 3 or storyboard.get("review_mode") != "approved_only":
            raise NarrationValidationError(
                "The linked storyboard is not a validated approved-only three-scene storyboard."
            )

        narration_plan = {
            "narration_id": review["narration_id"],
            "storyboard_id": storyboard_id,
            "source_sha256": source_sha256,
            "created_at": review.get("saved_at"),
            "language": review["language"],
            "voice_style": review["voice_style"],
            "segment_count": len(segments),
            "review_status": review["review_status"],
            "segments": segments,
        }

        st.session_state.storyboard = storyboard
        st.session_state.storyboard_uri = storyboard_uri
        st.session_state.narration_plan = narration_plan
        st.session_state.narration_plan_uri = review_uri.replace(
            "narration-review.json", "narration-plan.json"
        )
        st.session_state.narration_review_uri = review_uri
        st.session_state.audio_events = []
        st.session_state.audio_summary = None
        st.session_state.audio_summary_uri = None

        st.success(
            f"Narration {review['narration_id']} restored with three approved segments and its "
            f"linked storyboard {storyboard_id}."
        )
        st.code(
            "\n".join(
                [
                    f"Narration review: {review_uri}",
                    f"Storyboard: {storyboard_uri}",
                    "Approved narration segments: 3",
                ]
            )
        )
        if st.button("Open Narration and audio", use_container_width=True):
            st.switch_page("pages/3_Narration_and_audio.py")
    except (
        NarrationValidationError,
        StorageConfigurationError,
        StorageOperationError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        st.error(str(exc))
