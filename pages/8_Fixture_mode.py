# Renders deterministic judge fixtures that work without an available media provider.
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from evidencecast.deployment import (
    DeploymentClientError,
    fetch_backend_json,
    get_fixture_catalogue,
    get_fixture_workflow,
    normalise_api_url,
)
from evidencecast.fixtures import FixtureError


st.set_page_config(page_title="EvidenceCast Fixture Mode", page_icon="🧪", layout="wide")
st.title("Fixture mode for judges")
st.caption(
    "Explore three complete, synthetic and pre-approved report workflows even when an image or "
    "audio provider is unavailable. Fixture claims remain traceable to the bundled source text."
)
st.warning(
    "Fixture reports are synthetic deployment samples. They are not new research findings and "
    "fixture assets must not be described as provider-generated media."
)

api_url = normalise_api_url()
with st.sidebar:
    st.subheader("Deployment status")
    st.code(f"Backend: {api_url}")
    try:
        health = fetch_backend_json("/healthz", timeout_seconds=4)
        st.success(f"Backend healthy: {health.get('status', 'unknown')}")
    except DeploymentClientError as exc:
        st.info("Backend is unavailable; bundled fixture fallback remains active.")
        st.caption(str(exc))

try:
    catalogue, catalogue_source = get_fixture_catalogue()
except (FixtureError, DeploymentClientError) as exc:
    st.error(str(exc))
    st.stop()

st.info(f"Fixture catalogue source: **{catalogue_source}**")
fixture_by_title = {str(item["title"]): item for item in catalogue}
selected_title = st.selectbox("Sample report", options=list(fixture_by_title))
selected = fixture_by_title[selected_title]

summary_columns = st.columns(4)
summary_columns[0].metric("Domain", selected.get("domain", "Unknown"))
summary_columns[1].metric("Scenes", selected.get("scene_count", 3))
summary_columns[2].metric("Provider required", "No")
summary_columns[3].metric("Characters", f"{int(selected.get('character_count', 0)):,}")
st.write(selected.get("description", ""))

if st.button("Load complete approved fixture workflow", type="primary", use_container_width=True):
    try:
        workflow, workflow_source = get_fixture_workflow(str(selected["fixture_id"]))
        storyboard = workflow["storyboard"]
        narration = workflow["narration"]
        review = workflow["review"]
        st.session_state.fixture_workflow = workflow
        st.session_state.fixture_mode_active = True
        st.session_state.fixture_id = selected["fixture_id"]
        st.session_state.evidence_cards = review["cards"]
        st.session_state.storyboard = storyboard
        st.session_state.narration_plan = narration
        st.session_state.fixture_workflow_source = workflow_source
        st.success(
            f"Loaded {workflow['fixture']['title']} from {workflow_source}. "
            "The storyboard and approved narration are now available to downstream pages."
        )
    except (FixtureError, DeploymentClientError, KeyError, TypeError, ValueError) as exc:
        st.error(str(exc))

workflow = st.session_state.get("fixture_workflow")
if not workflow:
    st.info("Load a sample report to inspect its source, evidence cards, storyboard and narration.")
    st.stop()

fixture = workflow["fixture"]
source = workflow["source"]
review = workflow["review"]
storyboard = workflow["storyboard"]
narration = workflow["narration"]

st.divider()
metrics = st.columns(5)
metrics[0].metric("Fixture", fixture["fixture_id"])
metrics[1].metric("Evidence cards", len(review["cards"]))
metrics[2].metric("Approved", sum(card["status"] == "approved" for card in review["cards"]))
metrics[3].metric("Storyboard scenes", storyboard["scene_count"])
metrics[4].metric("Narration segments", narration["segment_count"])

source_tab, cards_tab, storyboard_tab, narration_tab, handoff_tab = st.tabs(
    ["Source report", "Approved evidence", "Storyboard", "Narration", "Continue workflow"]
)

with source_tab:
    st.code(f"Source SHA-256: {source['source_sha256']}")
    st.markdown(source["text"])

with cards_tab:
    card_rows = [
        {
            "Card ID": card["card_id"],
            "Decision": card["status"],
            "Claim": card["claim"],
            "Page": card["page_number"],
            "Source excerpt": card["source_excerpt"],
        }
        for card in review["cards"]
    ]
    st.dataframe(pd.DataFrame(card_rows), use_container_width=True, hide_index=True)

with storyboard_tab:
    scene_rows = [
        {
            "Scene": scene["scene_number"],
            "Title": scene["title"],
            "Evidence card": ", ".join(scene["evidence_card_ids"]),
            "Approved claim": scene["key_claim"],
            "On-screen text": scene["on_screen_text"],
        }
        for scene in storyboard["scenes"]
    ]
    st.dataframe(pd.DataFrame(scene_rows), use_container_width=True, hide_index=True)
    with st.expander("Visual prompts"):
        for scene in storyboard["scenes"]:
            st.markdown(f"**Scene {scene['scene_number']}**")
            st.write(scene["visual_prompt"])

with narration_tab:
    narration_rows = [
        {
            "Scene": segment["scene_number"],
            "Decision": segment["review_status"],
            "Evidence card": ", ".join(segment["evidence_card_ids"]),
            "Approved narration": segment["reviewed_text"],
        }
        for segment in narration["segments"]
    ]
    st.dataframe(pd.DataFrame(narration_rows), use_container_width=True, hide_index=True)

with handoff_tab:
    st.success(
        "Fixture workflow is loaded into this Streamlit session. Provider-free inspection is complete, "
        "and the local delivery route can create a clearly disclosed Pillow/eSpeak demonstration package."
    )
    st.page_link(
        "pages/7_Local_validation_delivery.py",
        label="Open local validation delivery",
        icon="🎬",
        use_container_width=True,
    )
    st.page_link(
        "pages/6_Final_media_and_evaluation.py",
        label="Open final media and evaluation",
        icon="✅",
        use_container_width=True,
    )
