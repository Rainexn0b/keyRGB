from __future__ import annotations

from pathlib import Path

import pytest

from src.gui.widgets.color_wheel import color_wheel_image


def _split_ppm(ppm: bytes) -> tuple[bytes, bytes, bytes, bytes]:
    return ppm.split(b"\n", 3)


def _pixel(payload: bytes, size: int, x: int, y: int) -> tuple[int, int, int]:
    offset = (y * size + x) * 3
    return tuple(payload[offset : offset + 3])


def test_wheel_cache_path_uses_xdg_cache_home_and_formats_masked_filename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_root = tmp_path / "cache-root"
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache_root))

    path = color_wheel_image.wheel_cache_path(size=9, bg_rgb=(-1, 256, 0x123), center_size=3)

    assert path == cache_root / "keyrgb" / "color_wheel_9_ff0023_3.ppm"


def test_wheel_cache_path_defaults_to_home_cache_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_home = tmp_path / "home"
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setattr(color_wheel_image.Path, "home", lambda: fake_home)

    path = color_wheel_image.wheel_cache_path(size=8, bg_rgb=(1, 2, 3), center_size=2)

    assert path == fake_home / ".cache" / "keyrgb" / "color_wheel_8_010203_2.ppm"


def test_build_wheel_ppm_bytes_has_valid_header_and_expected_length() -> None:
    size = 6
    ppm = color_wheel_image.build_wheel_ppm_bytes(size=size, bg_rgb=(10, 20, 30), center_size=1)
    magic, dims, maxval, payload = _split_ppm(ppm)

    assert magic == b"P6"
    assert dims == b"6 6"
    assert maxval == b"255"
    assert len(payload) == size * size * 3
    assert len(ppm) == len(b"P6\n6 6\n255\n") + (size * size * 3)


def test_build_wheel_ppm_bytes_fills_background_center_and_colored_pixels() -> None:
    size = 6
    bg_rgb = (10, 20, 30)
    ppm = color_wheel_image.build_wheel_ppm_bytes(size=size, bg_rgb=bg_rgb, center_size=1)
    _, _, _, payload = _split_ppm(ppm)

    assert _pixel(payload, size, 0, 0) == bg_rgb
    assert _pixel(payload, size, 5, 0) == bg_rgb
    assert _pixel(payload, size, 2, 2) == (255, 255, 255)

    right_pixel = _pixel(payload, size, 4, 3)
    left_pixel = _pixel(payload, size, 1, 3)

    assert right_pixel != bg_rgb
    assert right_pixel != (255, 255, 255)
    assert left_pixel != bg_rgb
    assert left_pixel != (255, 255, 255)
    assert right_pixel != left_pixel


def test_write_bytes_atomic_writes_new_target_and_cleans_temp_file(tmp_path: Path) -> None:
    target = tmp_path / "wheel.ppm"
    temp = target.with_suffix(target.suffix + ".tmp")

    color_wheel_image.write_bytes_atomic(target, b"fresh-bytes")

    assert target.read_bytes() == b"fresh-bytes"
    assert not temp.exists()


def test_write_bytes_atomic_replaces_existing_target(tmp_path: Path) -> None:
    target = tmp_path / "wheel.ppm"
    target.write_bytes(b"old-bytes")

    color_wheel_image.write_bytes_atomic(target, b"new-bytes")

    assert target.read_bytes() == b"new-bytes"


def test_write_bytes_atomic_cleans_temp_file_when_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "wheel.ppm"
    target.write_bytes(b"old-bytes")
    temp = target.with_suffix(target.suffix + ".tmp")

    def fail_replace(src: Path, dst: Path) -> None:
        assert src == temp
        assert dst == target
        assert temp.exists()
        raise OSError("replace failed")

    monkeypatch.setattr(color_wheel_image.os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        color_wheel_image.write_bytes_atomic(target, b"new-bytes")

    assert target.read_bytes() == b"old-bytes"
    assert not temp.exists()


def test_write_bytes_atomic_swallows_unlink_errors_without_masking_replace_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "wheel.ppm"
    temp = target.with_suffix(target.suffix + ".tmp")

    def fail_replace(_src: Path, _dst: Path) -> None:
        raise OSError("replace failed")

    def fail_unlink(self: Path, missing_ok: bool = False) -> None:
        assert self == temp
        assert missing_ok is True
        raise PermissionError("cannot unlink temp")

    monkeypatch.setattr(color_wheel_image.os, "replace", fail_replace)
    monkeypatch.setattr(color_wheel_image.Path, "unlink", fail_unlink)

    with pytest.raises(OSError, match="replace failed"):
        color_wheel_image.write_bytes_atomic(target, b"new-bytes")

    assert temp.exists()
