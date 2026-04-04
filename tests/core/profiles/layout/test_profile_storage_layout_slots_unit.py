from __future__ import annotations

import json

from src.core.resources.layouts import slot_id_for_key_id


class TestLayoutSlotStorage:
    def test_save_and_load_layout_slots_roundtrip(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(tmp_path / "cfg"))

        from src.core.config import layout_slots

        payload = {
            "nonusbackslash": {"visible": False},
            "nonushash": {"label": "Alt #"},
        }
        canonical_payload = {
            str(slot_id_for_key_id("iso", "nonusbackslash")): {"visible": False},
            str(slot_id_for_key_id("iso", "nonushash")): {"label": "Alt #"},
        }

        saved = layout_slots.save_layout_slot_overrides("iso", payload)
        loaded = layout_slots.load_layout_slot_overrides("iso")

        assert saved == canonical_payload
        assert loaded == canonical_payload

    def test_load_layout_slots_filters_unknown_and_empty_values(
        self,
        monkeypatch,
        tmp_path,
    ) -> None:
        monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(tmp_path / "cfg"))

        from src.core.config import layout_slots

        slot_file = layout_slots.layout_slots_path()
        slot_file.parent.mkdir(parents=True, exist_ok=True)
        slot_file.write_text(
            json.dumps(
                {
                    "layouts": {
                        "iso": {
                            "unknown": {"visible": False},
                            "nonusbackslash": {"visible": False, "label": "  "},
                            "jp_at": {"label": "JP @"},
                        }
                    }
                }
            ),
            encoding="utf-8",
        )

        loaded = layout_slots.load_layout_slot_overrides("iso")

        assert loaded == {str(slot_id_for_key_id("iso", "nonusbackslash")): {"visible": False}}

    def test_load_layout_slots_migrates_legacy_profile_sidecar(self, monkeypatch, tmp_path) -> None:
        cfg_dir = tmp_path / "cfg"
        monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(cfg_dir))

        from src.core.config import layout_slots

        legacy_file = cfg_dir / "profiles" / "test_profile" / "layout_slots.json"
        legacy_file.parent.mkdir(parents=True, exist_ok=True)
        legacy_file.write_text(
            json.dumps(
                {
                    "nonusbackslash": {"visible": False},
                    "nonushash": {"label": "ISO #"},
                    "jp_at": {"label": "JP @"},
                }
            ),
            encoding="utf-8",
        )

        loaded = layout_slots.load_layout_slot_overrides("iso", legacy_profile_name="test_profile")

        assert loaded == {
            str(slot_id_for_key_id("iso", "nonusbackslash")): {"visible": False},
            str(slot_id_for_key_id("iso", "nonushash")): {"label": "ISO #"},
        }
        assert json.loads(layout_slots.layout_slots_path().read_text(encoding="utf-8")) == {
            "layouts": {
                "iso": {
                    str(slot_id_for_key_id("iso", "nonusbackslash")): {"visible": False},
                    str(slot_id_for_key_id("iso", "nonushash")): {"label": "ISO #"},
                }
            }
        }
