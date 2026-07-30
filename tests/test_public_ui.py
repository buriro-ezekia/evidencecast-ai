# Tests the public-hosting guard that disables resource-intensive media assembly controls.
from __future__ import annotations

from pathlib import Path

from evidencecast.public_ui import configure_public_ui, env_flag, heavy_assembly_disabled


def _write_fixture_pages(root: Path) -> None:
    pages = root / "pages"
    pages.mkdir(parents=True)
    (pages / "7_Local_validation_delivery.py").write_text(
        'st.subheader("Build complete local validation package")\n'
        'if st.button("Generate, assemble and verify local delivery", type="primary", use_container_width=True):\n'
        "    pass\n",
        encoding="utf-8",
    )
    (pages / "6_Final_media_and_evaluation.py").write_text(
        'st.subheader("2. Subtitles, captioned MP4, thumbnail and infographic")\n'
        'if st.button("Build", disabled=not assembly_ready, use_container_width=True):\n'
        "    pass\n",
        encoding="utf-8",
    )


def test_env_flag_accepts_explicit_truthy_values(monkeypatch) -> None:
    monkeypatch.setenv("EXAMPLE_FLAG", " YeS ")
    assert env_flag("EXAMPLE_FLAG") is True
    monkeypatch.setenv("EXAMPLE_FLAG", "0")
    assert env_flag("EXAMPLE_FLAG") is False


def test_heavy_assembly_is_enabled_for_local_development(monkeypatch) -> None:
    monkeypatch.delenv("EVIDENCECAST_DISABLE_HEAVY_ASSEMBLY", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    assert heavy_assembly_disabled() is False


def test_heavy_assembly_is_disabled_automatically_on_render(monkeypatch) -> None:
    monkeypatch.delenv("EVIDENCECAST_DISABLE_HEAVY_ASSEMBLY", raising=False)
    monkeypatch.setenv("RENDER", "true")
    assert heavy_assembly_disabled() is True


def test_explicit_false_override_can_enable_larger_private_render_instance(monkeypatch) -> None:
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("EVIDENCECAST_DISABLE_HEAVY_ASSEMBLY", "0")
    assert heavy_assembly_disabled() is False


def test_public_ui_guard_is_disabled_by_default(tmp_path: Path, monkeypatch) -> None:
    _write_fixture_pages(tmp_path)
    monkeypatch.delenv("EVIDENCECAST_DISABLE_HEAVY_ASSEMBLY", raising=False)
    monkeypatch.delenv("RENDER", raising=False)

    assert configure_public_ui(tmp_path) == []
    assert "disabled=True" not in (
        tmp_path / "pages" / "7_Local_validation_delivery.py"
    ).read_text(encoding="utf-8")


def test_public_ui_guard_disables_both_assembly_controls(tmp_path: Path, monkeypatch) -> None:
    _write_fixture_pages(tmp_path)
    monkeypatch.setenv("EVIDENCECAST_DISABLE_HEAVY_ASSEMBLY", "1")

    changed = configure_public_ui(tmp_path)
    assert len(changed) == 2

    local_page = (tmp_path / "pages" / "7_Local_validation_delivery.py").read_text(
        encoding="utf-8"
    )
    final_page = (tmp_path / "pages" / "6_Final_media_and_evaluation.py").read_text(
        encoding="utf-8"
    )
    assert "disabled=True" in local_page
    assert "public Render service" in local_page
    assert "disabled=True" in final_page
    assert "Public judge mode" in final_page

    assert configure_public_ui(tmp_path) == []
