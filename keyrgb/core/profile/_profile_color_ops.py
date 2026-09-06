from __future__ import annotations

from collections.abc import Callable

from . import _profile_storage_payloads as storage_payloads


def load_per_key_colors(
    *,
    name: str | None,
    paths_for: Callable[..., object],
    read_json: Callable[..., object],
    safe_profile_name: Callable[..., object],
    default_colors: dict[tuple[int, int], tuple[int, int, int]],
) -> dict[tuple[int, int], tuple[int, int, int]]:
    raw = read_json(paths_for(name).per_key_colors)  # type: ignore[attr-defined]
    if raw is None:
        return default_colors.copy()
    return storage_payloads.parse_per_key_colors(raw)


def save_per_key_colors(
    *,
    colors: dict[tuple[int, int], tuple[int, int, int]],
    name: str | None,
    paths_for: Callable[..., object],
    write_json_atomic: Callable[..., object],
) -> None:
    write_json_atomic(
        paths_for(name).per_key_colors,  # type: ignore[attr-defined]
        storage_payloads.encode_per_key_colors(colors or {}),
    )
