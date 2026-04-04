from __future__ import annotations

import pytest

from src.core.config.perkey_colors import deserialize_per_key_colors, serialize_per_key_colors


class _BrokenInt:
    def __int__(self) -> int:
        raise RuntimeError("boom")


class _BrokenStrKey:
    def __str__(self) -> str:
        raise RuntimeError("boom")


def test_serialize_per_key_colors_returns_empty_for_non_dict_input() -> None:
    assert serialize_per_key_colors(object()) == {}


def test_serialize_per_key_colors_coerces_valid_entries_and_skips_invalid_ones() -> None:
    result = serialize_per_key_colors(
        {
            ("1", "2"): ("3", 4.8, True),
            (0, 1): object(),
            "bad-key": (1, 2, 3),
            (7, 8, 9): (1, 2, 3),
        }
    )

    assert result == {"1,2": [3, 4, 1]}


def test_serialize_per_key_colors_propagates_unexpected_coercion_errors() -> None:
    with pytest.raises(RuntimeError, match="boom"):
        serialize_per_key_colors({(0, 1): (_BrokenInt(), 2, 3)})


def test_deserialize_per_key_colors_returns_empty_for_non_dict_input() -> None:
    assert deserialize_per_key_colors(object()) == {}


def test_deserialize_per_key_colors_parses_valid_entries_and_skips_invalid_ones() -> None:
    result = deserialize_per_key_colors(
        {
            " 1 , 2 ": ["3", 4.2, True],
            "bad": [1, 2, 3],
            "3,4": [1, 2],
            "5,6": object(),
        }
    )

    assert result == {(1, 2): (3, 4, 1)}


def test_deserialize_per_key_colors_propagates_unexpected_stringification_errors() -> None:
    with pytest.raises(RuntimeError, match="boom"):
        deserialize_per_key_colors({_BrokenStrKey(): [1, 2, 3]})
