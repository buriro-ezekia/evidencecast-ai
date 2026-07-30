# Restores an approved-only three-scene storyboard directly from Backblaze B2 into Streamlit session state.
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
from evidencecast.narration import NarrationValidationError
from evidencecast.storage import B2Settings, StorageConfigurationError, StorageOperationError

load_dotenv(REPOSITORY_ROOT / ".env", override=True)

st.set_page_config(
    page_title="Load Storyboard from B2",
    page_icon="📥",
    layout="wide",
)

st.title("Load storyboard from Backblaze B2")
st.caption(
    "Restore a previously saved approved-only three-scene storyboard after a Streamlit session expires."
)

st.info(
    "Use the B2 path ending in `/storyboard.json`. An evidence-card review file is not a storyboard "
    "and cannot be used for narration generation."
)

storyboard_uri = st.text_input(
    "Storyboard B2 URI",
    value=str(st.session_state.get("storyboard_uri", "") or ""),
    placeholder="b2://bucket/evidencecast/sources/.../storyboards/SB-.../storyboard.json",
    help="Paste the exact B2 URI shown when the Day 3 storyboard was saved.",
)

if st.button(
    "Load storyboard into this session",
    type="primary",
    disabled=not storyboard_uri.strip(),
    use_container_width=True,
):
    try:
        store = B2AudioStore(B2Settings.from_environment())
        loaded = store.load_json_from_b2_uri(storyboard_uri)
        if loaded.get("scene_count") != 3 or loaded.get("review_mode") != "approved_only":
            raise NarrationValidationError(
                "The B2 JSON is not a validated approved-only three-scene storyboard."
            )
        scenes = loaded.get("scenes")
        if not isinstance(scenes, list) or len(scenes) != 3:
            raise NarrationValidationError("The storyboard must contain exactly three scenes.")

        st.session_state.storyboard = loaded
        st.session_state.storyboard_uri = storyboard_uri.strip()
        st.session_state.narration_plan = None
        st.session_state.narration_plan_uri = None
        st.session_state.narration_review_uri = None
        st.session_state.audio_events = []
        st.session_state.audio_summary = None
        st.session_state.audio_summary_uri = None

        st.success(
            f"Storyboard {loaded['storyboard_id']} loaded with three approved-only scenes."
        )
        st.json(
            {
                "storyboard_id": loaded["storyboard_id"],
                "source_sha256": loaded["source_sha256"],
                "scene_count": loaded["scene_count"],
                "review_mode": loaded["review_mode"],
                "approved_card_ids": loaded.get("approved_card_ids", []),
            }
        )
        st.page_link(
            "pages/3_Narration_and_audio.py",
            label="Open Narration and audio",
            icon="🎙️",
            use_container_width=True,
        )
    except (
        NarrationValidationError,
        StorageConfigurationError,
        StorageOperationError,
        KeyError,
    ) as exc:
        st.error(str(exc))
