# Exposes EvidenceCast health, capability and fixture endpoints for deployment.
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from evidencecast.fixtures import (
    FixtureError,
    build_fixture_workflow,
    fixture_mode_enabled,
    list_fixture_reports,
)


def _allowed_origins() -> list[str]:
    configured = os.getenv("EVIDENCECAST_ALLOWED_ORIGINS", "*").strip()
    if not configured or configured == "*":
        return ["*"]
    return [value.strip() for value in configured.split(",") if value.strip()]


app = FastAPI(
    title="EvidenceCast API",
    version="1.1.0",
    description=(
        "Deployment health, capability and deterministic fixture endpoints for EvidenceCast AI. "
        "Provider and B2 credentials are never returned by this API."
    ),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/", tags=["system"])
def root() -> dict[str, Any]:
    return {
        "service": "evidencecast-api",
        "status": "ok",
        "documentation": "/docs",
        "fixture_catalogue": "/api/v1/fixtures",
    }


@app.get("/healthz", tags=["system"])
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "evidencecast-api",
        "fixture_mode": fixture_mode_enabled(),
    }


@app.get("/readyz", tags=["system"])
def readiness() -> dict[str, Any]:
    fixtures = list_fixture_reports()
    return {
        "status": "ready",
        "fixture_count": len(fixtures),
        "fixture_mode": fixture_mode_enabled(),
        "b2_configured": bool(
            os.getenv("B2_KEY_ID", "").strip()
            and os.getenv("B2_APP_KEY", "").strip()
            and os.getenv("B2_BUCKET", "").strip()
        ),
        "gmi_configured": bool(os.getenv("GMI_API_KEY", "").strip()),
        "nvidia_configured": bool(os.getenv("NVIDIA_API_KEY", "").strip()),
        "openai_configured": bool(os.getenv("OPENAI_API_KEY", "").strip()),
    }


@app.get("/api/v1/capabilities", tags=["system"])
def capabilities() -> dict[str, Any]:
    return {
        "frontend": "Streamlit",
        "backend": "FastAPI",
        "storage": "Backblaze B2 via the S3-compatible API",
        "orchestration": "Genblaze",
        "image_models": [
            "seedream-5.0-lite",
            "stabilityai/stable-diffusion-3-5-large",
            "black-forest-labs/flux.1-schnell",
            "gpt-image-1",
        ],
        "audio_models": [
            "minimax-tts-speech-2.6-turbo",
            "nvidia/magpie-tts-multilingual",
        ],
        "provider_validation": {
            "nvidia": {
                "single_scene_image": True,
                "single_segment_tts": True,
                "credentials_exposed": False,
            }
        },
        "local_validation": {
            "images": "Pillow",
            "narration": "eSpeak NG",
            "composition": "FFmpeg",
            "provider_generated": False,
        },
        "fixture_mode": fixture_mode_enabled(),
    }


@app.get("/api/v1/fixtures", tags=["fixtures"])
def fixtures() -> dict[str, Any]:
    if not fixture_mode_enabled():
        raise HTTPException(status_code=404, detail="Fixture mode is disabled.")
    return {"count": len(list_fixture_reports()), "fixtures": list_fixture_reports()}


@app.get("/api/v1/fixtures/{fixture_id}", tags=["fixtures"])
def fixture(fixture_id: str) -> dict[str, Any]:
    if not fixture_mode_enabled():
        raise HTTPException(status_code=404, detail="Fixture mode is disabled.")
    try:
        return build_fixture_workflow(fixture_id)
    except FixtureError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
