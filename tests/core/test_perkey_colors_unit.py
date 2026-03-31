from __future__ import annotations

from src.core.config.perkey_colors import deserialize_per_key_colors, serialize_per_key_colors


def test_serialize_per_key_colors_returns_empty_for_non_dict_input() -> None:
    assert serialize_per_key_colors(object()) == {}


def test_serialize_per_key_colors_coerces_valid_entries_and_skips_invalid_ones() -> None:
    result = serialize_per_key_colors(
        {
            ("1", "2"): ("3", 4.8, True),
            (0, 1): object(),
        }
    )

    assert result == {"1,2": [3, 4, 1]}


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