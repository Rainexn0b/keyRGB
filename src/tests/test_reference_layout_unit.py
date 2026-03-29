from __future__ import annotations

from src.core.resources.layout import build_layout


def test_reference_layout_includes_iso_extra_key() -> None:
    key_ids = {key.key_id for key in build_layout()}

    assert "nonusbackslash" in key_ids
    assert "lshift" in key_ids
    assert "enter" in key_ids