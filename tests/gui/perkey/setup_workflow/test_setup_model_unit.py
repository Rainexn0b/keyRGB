from __future__ import annotations

import dataclasses

import pytest

from keyrgb.gui.perkey.setup_workflow.model import (
    SetupSource,
    cancel_setup,
    draft_from_snapshot,
    draft_from_source,
    snapshot_copy,
    snapshot_from_source,
    validate_keymap_for_calibration_skip,
)


def _source() -> SetupSource:
    return SetupSource(
        physical_layout="tongfang-iso",
        legend_pack=" Pack A ".strip(),
        profile_name="Default",
        slot_overrides={"slot-01": {"visible": False, "label": "Esc"}},
        keymap={"slot-01": ((0, 0),), "slot-02": ((0, 1), (0, 2))},
        layout_tweaks={"inset": 0.06},
        per_key_layout_tweaks={"slot-01": {"dx": 1.0}},
    )


def test_draft_is_isolated_from_source_and_snapshot() -> None:
    source = _source()
    snapshot = snapshot_from_source(source)
    draft = draft_from_snapshot(snapshot)

    draft.slot_overrides["slot-01"]["label"] = "MUTATED"
    draft.keymap["slot-01"] = ((9, 9),)
    draft.per_key_layout_tweaks["slot-01"]["dx"] = 99.0
    draft.layout_tweaks["inset"] = 99.0

    assert source.slot_overrides == {"slot-01": {"visible": False, "label": "Esc"}}
    assert snapshot.slot_overrides == {"slot-01": {"visible": False, "label": "Esc"}}
    assert snapshot.keymap == {"slot-01": ((0, 0),), "slot-02": ((0, 1), (0, 2))}
    assert snapshot.per_key_layout_tweaks == {"slot-01": {"dx": 1.0}}
    assert snapshot.layout_tweaks == {"inset": 0.06}


def test_snapshot_blocks_attribute_rebinding_but_not_nested_mutation() -> None:
    # Honest contract: frozen blocks rebinding, while contained dicts stay
    # plain (mutable) so opaque legacy payloads keep exact shapes. Isolation
    # comes from snapshot_copy, covered below and by the rollback tests.
    snapshot = snapshot_from_source(_source())
    with pytest.raises(dataclasses.FrozenInstanceError):
        snapshot.physical_layout = "other"  # type: ignore[misc]


def test_snapshot_copy_is_equal_but_independent() -> None:
    snapshot = snapshot_from_source(_source())
    copied = snapshot_copy(snapshot)
    assert copied == snapshot
    assert copied is not snapshot
    copied.keymap["slot-01"] = ((9, 9),)
    copied.slot_overrides["slot-01"]["label"] = "MUTATED"
    copied.per_key_layout_tweaks["slot-01"]["dx"] = 99.0
    copied.layout_tweaks["inset"] = 99.0
    assert snapshot == snapshot_from_source(_source())


def test_opaque_keymap_payloads_round_trip_verbatim() -> None:
    legacy = {"CANON-001": "0,1", "legacy key": [[0, 0]], "slot-09": None}
    draft = draft_from_source(SetupSource(keymap=legacy))
    assert draft.keymap == legacy
    assert draft.keymap is not legacy
    assert draft.original.keymap == legacy


def test_mutators_deep_copy_caller_owned_objects() -> None:
    draft = draft_from_source(SetupSource())
    override = {"visible": True}
    draft.put_slot_override("slot-07", override)
    override["visible"] = False
    assert draft.slot_overrides["slot-07"] == {"visible": True}

    keymap = {"slot-07": ((1, 1),)}
    draft.set_keymap(keymap)
    keymap["slot-07"] = ((5, 5),)
    assert draft.keymap == {"slot-07": ((1, 1),)}


def test_mutator_input_validation() -> None:
    draft = draft_from_source(SetupSource())
    with pytest.raises(ValueError):
        draft.set_physical_layout("  ")
    with pytest.raises(ValueError):
        draft.set_legend_pack("")
    with pytest.raises(ValueError):
        draft.put_slot_override("", {"visible": True})
    with pytest.raises(TypeError):
        draft.put_slot_override("slot-01", ["not-a-mapping"])  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        draft.set_keymap([("slot-01", (0, 0))])  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        draft.set_layout_tweak("inset", True)
    with pytest.raises(TypeError):
        draft.put_per_key_layout_tweak("slot-01", "dx", "far")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        draft.set_per_key_layout_tweaks({"slot-01": [1.0]})  # type: ignore[dict-item]


def test_slot_override_and_per_key_tweak_lifecycle() -> None:
    draft = draft_from_source(SetupSource())
    draft.put_slot_override("slot-02", {"label": "Q"})
    draft.remove_slot_override("slot-02")
    assert "slot-02" not in draft.slot_overrides
    draft.remove_slot_override("missing-slot")  # no-op, stays open
    draft.clear_slot_overrides()
    assert draft.slot_overrides == {}

    draft.put_per_key_layout_tweak("slot-03", "dx", 2)
    assert draft.per_key_layout_tweaks["slot-03"] == {"dx": 2.0}
    draft.remove_per_key_layout_tweak("slot-03", "dx")
    assert "slot-03" not in draft.per_key_layout_tweaks


def test_cancel_returns_untouched_original() -> None:
    draft = draft_from_source(_source())
    draft.set_physical_layout("other-layout")
    draft.set_keymap({"slot-01": ((3, 3),)})

    original = cancel_setup(draft)
    assert original is not draft.original
    assert original == draft.original
    assert original.physical_layout == "tongfang-iso"
    assert original.keymap == {"slot-01": ((0, 0),), "slot-02": ((0, 1), (0, 2))}
    # Draft keeps its edits: cancelling discards them by abandoning the draft.
    assert draft.physical_layout == "other-layout"


def test_validate_keymap_accepts_matrix_covering_keymap() -> None:
    result = validate_keymap_for_calibration_skip(
        {"a": ((0, 0),), "b": [(0, 1), [1, 2]], "c": (2, 3)},
        rows=6,
        cols=16,
    )
    assert result.valid is True
    assert result.entry_count == 3
    assert result.cell_count == 4


@pytest.mark.parametrize(
    "keymap",
    [
        None,
        {},
        {"a": ()},
        {"a": []},
        {"a": None},
        {"a": "0,1"},
        {"a": ((0, 0), (6, 0))},  # row out of range
        {"a": ((0, -1),)},  # negative col
        {"a": ((True, 0),)},  # bool cell rejected
        {"a": ((0.0, 1),)},  # float cell rejected
        {"a": (("0", "1"),)},  # string cell rejected
        {"a": ({"row": 0},)},  # dict cell rejected
        {"a": ((0, 0, 0),)},  # malformed cell rejected
        {"a": ((0,),)},  # malformed cell rejected
        {"ok": ((0, 0),), "bad": "legacy-string"},  # one bad entry fails all
        ["not-a-mapping"],
    ],
)
def test_validate_keymap_rejects_bad_payloads(keymap) -> None:
    assert validate_keymap_for_calibration_skip(keymap, rows=6, cols=16).valid is False


def test_validate_keymap_rejects_bad_dimensions() -> None:
    good = {"a": ((0, 0),)}
    assert validate_keymap_for_calibration_skip(good, rows=0, cols=16).valid is False
    assert validate_keymap_for_calibration_skip(good, rows=True, cols=16).valid is False  # type: ignore[arg-type]


def test_validate_keymap_is_read_only() -> None:
    keymap = {"a": ((0, 0),), "b": "legacy"}
    before = {"a": ((0, 0),), "b": "legacy"}
    validate_keymap_for_calibration_skip(keymap, rows=6, cols=16)
    assert keymap == before
