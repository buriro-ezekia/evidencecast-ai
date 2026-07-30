# Configures safe public-hosting behaviour for resource-intensive Streamlit controls.
from __future__ import annotations

import os
from pathlib import Path

TRUTHY_VALUES = {"1", "true", "yes", "on"}


def env_flag(name: str, *, default: bool = False) -> bool:
    """Return a boolean environment flag using explicit, case-insensitive values."""

    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in TRUTHY_VALUES


def heavy_assembly_disabled() -> bool:
    """Return whether public hosting should disable media assembly controls.

    An explicit EVIDENCECAST_DISABLE_HEAVY_ASSEMBLY value always wins. When the
    flag is absent, Render is treated as a public hosted environment because it
    automatically sets RENDER=true at runtime. Local development remains enabled.
    """

    explicit = os.getenv("EVIDENCECAST_DISABLE_HEAVY_ASSEMBLY")
    if explicit is not None:
        return explicit.strip().lower() in TRUTHY_VALUES
    return env_flag("RENDER", default=False)


def _replace_once(text: str, old: str, new: str, *, path: Path) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Could not find the expected public-UI patch target in {path}.")
    return text.replace(old, new, 1)


def configure_public_ui(repository_root: Path) -> list[Path]:
    """Patch Streamlit pages at container start when heavy assembly is disabled.

    The source repository retains the complete local workflow. The public Render image
    receives a runtime-only guard that disables Pillow, eSpeak and FFmpeg controls on
    small instances while preserving restoration, inspection and evaluation features.
    """

    if not heavy_assembly_disabled():
        return []

    changed: list[Path] = []

    local_page = repository_root / "pages" / "7_Local_validation_delivery.py"
    local_text = local_page.read_text(encoding="utf-8")
    updated_local = _replace_once(
        local_text,
        'if st.button("Generate, assemble and verify local delivery", type="primary", use_container_width=True):',
        'if st.button(\n    "Generate, assemble and verify local delivery",\n    type="primary",\n    use_container_width=True,\n    disabled=True,\n    help="Disabled on the public Render service. Run locally or on a larger private instance.",\n):',
        path=local_page,
    )
    updated_local = _replace_once(
        updated_local,
        'st.subheader("Build complete local validation package")',
        'st.subheader("Build complete local validation package")\nst.info(\n    "Public judge mode keeps this resource-intensive control disabled to protect the "\n    "hosted Render service. Restore and inspect the approved workflow here, then "\n    "run assembly locally or on an adequately provisioned private deployment."\n)',
        path=local_page,
    )
    if updated_local != local_text:
        local_page.write_text(updated_local, encoding="utf-8")
        changed.append(local_page)

    final_page = repository_root / "pages" / "6_Final_media_and_evaluation.py"
    final_text = final_page.read_text(encoding="utf-8")
    updated_final = _replace_once(
        final_text,
        'disabled=not assembly_ready,',
        'disabled=True,\n    help="Disabled on the public Render service. Run locally or on a larger private instance.",',
        path=final_page,
    )
    updated_final = _replace_once(
        updated_final,
        'st.subheader("2. Subtitles, captioned MP4, thumbnail and infographic")',
        'st.subheader("2. Subtitles, captioned MP4, thumbnail and infographic")\nst.info(\n    "Public judge mode allows workflow restoration and consistency evaluation but "\n    "disables new FFmpeg assembly on the hosted instance. Use the documented "\n    "local workflow for new delivery builds."\n)',
        path=final_page,
    )
    if updated_final != final_text:
        final_page.write_text(updated_final, encoding="utf-8")
        changed.append(final_page)

    return changed
