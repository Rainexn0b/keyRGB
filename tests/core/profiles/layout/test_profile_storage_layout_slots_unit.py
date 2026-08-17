from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor

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

    def test_load_layout_slots_migrates_prior_profile_sidecar(self, monkeypatch, tmp_path) -> None:
        cfg_dir = tmp_path / "cfg"
        monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(cfg_dir))

        from src.core.config import layout_slots

        prior_file = cfg_dir / "profiles" / "test_profile" / "layout_slots.json"
        prior_file.parent.mkdir(parents=True, exist_ok=True)
        prior_file.write_text(
            json.dumps(
                {
                    "nonusbackslash": {"visible": False},
                    "nonushash": {"label": "ISO #"},
                    "jp_at": {"label": "JP @"},
                }
            ),
            encoding="utf-8",
        )

        loaded = layout_slots.load_layout_slot_overrides("iso", prior_profile_name="test_profile")

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

    def test_concurrent_layout_updates_preserve_each_layout(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(tmp_path / "cfg"))

        from src.core.config import layout_slots

        original_load = layout_slots._load_all_layout_slot_overrides
        reads_completed = threading.Barrier(2)

        def synchronized_load():
            payload = original_load()
            reads_completed.wait(timeout=2.0)
            return payload

        monkeypatch.setattr(layout_slots, "_load_all_layout_slot_overrides", synchronized_load)

        def save(layout_id: str, payload: dict[str, dict[str, object]]) -> None:
            layout_slots.save_layout_slot_overrides(layout_id, payload)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(save, "iso", {"nonusbackslash": {"visible": False}}),
                executor.submit(save, "jis", {"jp_at": {"label": "JP @"}}),
            ]
            for future in futures:
                future.result(timeout=3.0)

        monkeypatch.setattr(layout_slots, "_load_all_layout_slot_overrides", original_load)
        persisted = json.loads(layout_slots.layout_slots_path().read_text(encoding="utf-8"))["layouts"]
        assert set(persisted) == {"iso", "jis"}
