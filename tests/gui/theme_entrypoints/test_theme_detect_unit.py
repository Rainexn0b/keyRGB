from __future__ import annotations

import builtins
import io
from types import SimpleNamespace

import pytest

from src.gui.theme import detect


def test_detect_theme_override_accepts_dark_light_and_rejects_other_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_THEME", " dark ")
    assert detect._detect_theme_override() is True

    monkeypatch.setenv("KEYRGB_THEME", "LIGHT")
    assert detect._detect_theme_override() is False

    monkeypatch.setenv("KEYRGB_THEME", "system")
    assert detect._detect_theme_override() is None


def test_detect_gtk_theme_env_detects_dark_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GTK_THEME", "Breeze:dark")
    assert detect._detect_gtk_theme_env() is True

    monkeypatch.setenv("GTK_THEME", "Adwaita")
    assert detect._detect_gtk_theme_env() is None

    monkeypatch.delenv("GTK_THEME", raising=False)
    assert detect._detect_gtk_theme_env() is None


@pytest.mark.parametrize(
    ("stdout", "expected"),
    [
        ("'prefer-dark'\n", True),
        ("'prefer-light'\n", False),
        ("'default'\n", None),
    ],
)
def test_detect_gsettings_color_scheme_interprets_subprocess_output(
    monkeypatch: pytest.MonkeyPatch, stdout: str, expected: bool | None
) -> None:
    monkeypatch.setattr(detect, "which", lambda tool: "/usr/bin/gsettings")
    monkeypatch.setattr(
        detect.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout=stdout),
    )

    assert detect._detect_gsettings_color_scheme() is expected


def test_detect_gsettings_color_scheme_returns_none_without_tool_or_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(detect, "which", lambda tool: None)
    assert detect._detect_gsettings_color_scheme() is None

    monkeypatch.setattr(detect, "which", lambda tool: "/usr/bin/gsettings")

    def raise_runtime_error(*args, **kwargs):
        raise detect.subprocess.TimeoutExpired("gsettings", 0.25)

    monkeypatch.setattr(detect.subprocess, "run", raise_runtime_error)
    assert detect._detect_gsettings_color_scheme() is None


def test_detect_gsettings_color_scheme_returns_none_for_unrecognized_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    monkeypatch.setattr(detect, "which", lambda tool: "/usr/bin/gsettings")

    def fake_run(*args, **kwargs):
        calls.append(list(args[0]))
        return SimpleNamespace(stdout="'default'\n")

    monkeypatch.setattr(detect.subprocess, "run", fake_run)

    assert detect._detect_gsettings_color_scheme() is None
    assert calls == [["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"]]


def test_read_kde_colorscheme_from_kreadconfig_uses_available_tool_and_falls_back_on_error(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    kdeglobals = tmp_path / "kdeglobals"
    kdeglobals.write_text("[General]\nColorScheme=BreezeDark\n", encoding="utf-8")

    monkeypatch.setattr(
        detect,
        "which",
        lambda tool: None if tool == "kreadconfig6" else f"/usr/bin/{tool}",
    )

    calls: list[str] = []

    def fake_run(args, **kwargs):
        calls.append(args[0])
        return SimpleNamespace(stdout="BreezeDark\n")

    monkeypatch.setattr(detect.subprocess, "run", fake_run)
    assert detect._read_kde_colorscheme_from_kreadconfig(str(kdeglobals)) == "breezedark"
    assert calls == ["kreadconfig5"]

    monkeypatch.setattr(detect, "which", lambda tool: f"/usr/bin/{tool}")
    calls.clear()

    def fake_run_with_failure(args, **kwargs):
        calls.append(args[0])
        if args[0] == "kreadconfig6":
            raise detect.subprocess.TimeoutExpired(args[0], 0.25)
        return SimpleNamespace(stdout="BreezeLight\n")

    monkeypatch.setattr(detect.subprocess, "run", fake_run_with_failure)
    assert detect._read_kde_colorscheme_from_kreadconfig(str(kdeglobals)) == "breezelight"
    assert calls == ["kreadconfig6", "kreadconfig5"]


def test_read_kde_colorscheme_from_ini_reads_general_section_only(tmp_path) -> None:
    kdeglobals = tmp_path / "kdeglobals"
    kdeglobals.write_text(
        "\n".join(
            [
                "# comment",
                "[Other]",
                "ColorScheme=IgnoreMe",
                "[General]",
                "ColorScheme = BreezeDark",
            ]
        ),
        encoding="utf-8",
    )

    assert detect._read_kde_colorscheme_from_ini(str(kdeglobals)) == "breezedark"


def test_read_kde_colorscheme_from_kreadconfig_returns_none_when_file_or_tools_are_missing(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "missing-kdeglobals"
    assert detect._read_kde_colorscheme_from_kreadconfig(str(missing)) is None

    kdeglobals = tmp_path / "kdeglobals"
    kdeglobals.write_text("[General]\nColorScheme=BreezeDark\n", encoding="utf-8")
    monkeypatch.setattr(detect, "which", lambda tool: None)

    assert detect._read_kde_colorscheme_from_kreadconfig(str(kdeglobals)) is None


def test_read_kde_colorscheme_from_ini_returns_none_for_missing_blank_or_open_error(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "missing-kdeglobals"
    assert detect._read_kde_colorscheme_from_ini(str(missing)) is None

    blank = tmp_path / "blank-kdeglobals"
    blank.write_text("[General]\nColorScheme=   \n", encoding="utf-8")
    assert detect._read_kde_colorscheme_from_ini(str(blank)) is None

    kdeglobals = tmp_path / "error-kdeglobals"
    kdeglobals.write_text("[General]\nColorScheme=BreezeDark\n", encoding="utf-8")

    real_open = builtins.open

    def fake_open(path, *args, **kwargs):
        if path == str(kdeglobals):
            raise OSError("permission denied")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", fake_open)
    assert detect._read_kde_colorscheme_from_ini(str(kdeglobals)) is None


def test_detect_kde_prefers_dark_requires_kde_desktop_and_uses_ini_fallback(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "GNOME")
    assert detect._detect_kde_prefers_dark() is None

    home = tmp_path / "home"
    kdeglobals = home / ".config" / "kdeglobals"
    kdeglobals.parent.mkdir(parents=True)
    kdeglobals.write_text("[General]\nColorScheme=BreezeDark\n", encoding="utf-8")

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
    monkeypatch.setattr(detect, "_read_kde_colorscheme_from_kreadconfig", lambda path: None)

    assert detect._detect_kde_prefers_dark() is True


def test_detect_kde_prefers_dark_supports_plasma_and_returns_none_without_scheme(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    kdeglobals = home / ".config" / "kdeglobals"
    kdeglobals.parent.mkdir(parents=True)
    kdeglobals.write_text("[General]\nColorScheme=BreezeLight\n", encoding="utf-8")

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "plasma")
    monkeypatch.setattr(detect, "_read_kde_colorscheme_from_kreadconfig", lambda path: None)

    assert detect._detect_kde_prefers_dark() is False

    monkeypatch.setattr(detect, "_read_kde_colorscheme_from_ini", lambda path: None)
    assert detect._detect_kde_prefers_dark() is None


def test_detect_system_prefers_dark_uses_first_non_none_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def override():
        calls.append("override")
        return None

    def gtk_theme():
        calls.append("gtk")
        return None

    def gsettings():
        calls.append("gsettings")
        return False

    def kde():
        calls.append("kde")
        return True

    monkeypatch.setattr(detect, "_detect_theme_override", override)
    monkeypatch.setattr(detect, "_detect_gtk_theme_env", gtk_theme)
    monkeypatch.setattr(detect, "_detect_gsettings_color_scheme", gsettings)
    monkeypatch.setattr(detect, "_detect_kde_prefers_dark", kde)

    assert detect.detect_system_prefers_dark() is False
    assert calls == ["override", "gtk", "gsettings"]


def test_detect_system_prefers_dark_logs_and_skips_unexpected_provider_errors(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    calls: list[str] = []

    def override():
        calls.append("override")
        raise RuntimeError("broken override")

    def gtk_theme():
        calls.append("gtk")
        return None

    def gsettings():
        calls.append("gsettings")
        return False

    monkeypatch.setattr(detect, "_detect_theme_override", override)
    monkeypatch.setattr(detect, "_detect_gtk_theme_env", gtk_theme)
    monkeypatch.setattr(detect, "_detect_gsettings_color_scheme", gsettings)
    monkeypatch.setattr(detect, "_detect_kde_prefers_dark", lambda: True)

    with caplog.at_level("WARNING"):
        assert detect.detect_system_prefers_dark() is False

    assert calls == ["override", "gtk", "gsettings"]
    assert "Theme detection provider 'override' failed" in caplog.text
    assert "broken override" in caplog.text


def test_detect_system_prefers_dark_returns_none_when_all_providers_are_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(detect, "_detect_theme_override", lambda: None)
    monkeypatch.setattr(detect, "_detect_gtk_theme_env", lambda: None)
    monkeypatch.setattr(detect, "_detect_gsettings_color_scheme", lambda: None)
    monkeypatch.setattr(detect, "_detect_kde_prefers_dark", lambda: None)

    assert detect.detect_system_prefers_dark() is None


def test_kde_colorscheme_prefers_dark_uses_luminance_before_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(detect, "_kde_colorscheme_background_luminance", lambda scheme: 0.2)
    assert detect._kde_colorscheme_prefers_dark("BrightName") is True

    monkeypatch.setattr(detect, "_kde_colorscheme_background_luminance", lambda scheme: 0.8)
    assert detect._kde_colorscheme_prefers_dark("BreezeDark") is False


def test_kde_colorscheme_prefers_dark_falls_back_to_scheme_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(detect, "_kde_colorscheme_background_luminance", lambda scheme: None)

    assert detect._kde_colorscheme_prefers_dark("BreezeDark") is True
    assert detect._kde_colorscheme_prefers_dark("Breeze") is False
    assert detect._kde_colorscheme_prefers_dark("Custom") is None


def test_kde_colorscheme_prefers_dark_handles_blank_names_and_threshold_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(detect, "_kde_colorscheme_background_luminance", lambda scheme: 0.5)
    assert detect._kde_colorscheme_prefers_dark("BreezeDark") is False

    monkeypatch.setattr(detect, "_kde_colorscheme_background_luminance", lambda scheme: None)
    assert detect._kde_colorscheme_prefers_dark("   ") is None


def test_kde_colorscheme_background_luminance_reads_window_then_view(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    scheme_dir = home / ".local" / "share" / "color-schemes"
    scheme_dir.mkdir(parents=True)
    scheme_path = scheme_dir / "BreezeDark.colors"
    scheme_path.write_text(
        "\n".join(
            [
                "[Colors:Window]",
                "BackgroundNormal=0, 0, 0",
                "[Colors:View]",
                "BackgroundNormal=255, 255, 255",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(home))
    assert detect._kde_colorscheme_background_luminance("BreezeDark") == pytest.approx(0.0)

    scheme_path.write_text(
        "\n".join(
            [
                "[Colors:Window]",
                "BackgroundNormal=not,rgb",
                "[Colors:View]",
                "BackgroundNormal=255, 255, 255",
            ]
        ),
        encoding="utf-8",
    )

    assert detect._kde_colorscheme_background_luminance("BreezeDark") == pytest.approx(1.0)


def test_kde_colorscheme_background_luminance_returns_none_for_missing_invalid_or_malformed_files(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    scheme_dir = home / ".local" / "share" / "color-schemes"
    scheme_dir.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    assert detect._kde_colorscheme_background_luminance("Missing") is None

    invalid = scheme_dir / "Invalid.colors"
    invalid.write_text(
        "\n".join(
            [
                "[Colors:Window]",
                "BackgroundNormal=1, 2",
                "[Colors:View]",
                "BackgroundNormal=hello",
            ]
        ),
        encoding="utf-8",
    )
    assert detect._kde_colorscheme_background_luminance("Invalid") is None

    malformed = scheme_dir / "Malformed.colors"
    malformed.write_text("[Colors:Window\nBackgroundNormal=0, 0, 0\n", encoding="utf-8")
    assert detect._kde_colorscheme_background_luminance("Malformed") is None


def test_kde_colorscheme_background_luminance_falls_back_to_system_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    target = "/usr/share/color-schemes/BreezeDark.colors"

    def fake_exists(path: str) -> bool:
        return path == target

    def fake_open(path, *args, **kwargs):
        if path == target:
            return io.StringIO("[Colors:Window]\nBackgroundNormal=0, 0, 0\n")
        raise FileNotFoundError(path)

    monkeypatch.setattr(detect.os.path, "exists", fake_exists)
    monkeypatch.setattr(builtins, "open", fake_open)

    assert detect._kde_colorscheme_background_luminance("BreezeDark") == pytest.approx(0.0)


def test_parse_kde_rgb_validates_triplets() -> None:
    assert detect._parse_kde_rgb("12, 34, 56") == (12, 34, 56)
    assert detect._parse_kde_rgb("12,34") is None
    assert detect._parse_kde_rgb("256,0,0") is None
    assert detect._parse_kde_rgb("a,b,c") is None


def test_relative_luminance_srgb_matches_black_white_and_mid_gray() -> None:
    assert detect._relative_luminance_srgb(0, 0, 0) == pytest.approx(0.0)
    assert detect._relative_luminance_srgb(255, 255, 255) == pytest.approx(1.0)

    gray = detect._relative_luminance_srgb(127, 127, 127)
    assert 0.0 < gray < 1.0
