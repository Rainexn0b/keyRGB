from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.gui.theme import ttk as ttk_theme


class _FakeStyle:
    def __init__(self, lookups: dict[tuple[str, str], str] | None = None) -> None:
        self._lookups = dict(lookups or {})
        self.theme_calls: list[str] = []
        self.configure_calls: list[tuple[str, dict[str, object]]] = []
        self.map_calls: list[tuple[str, dict[str, object]]] = []

    def theme_use(self, name: str) -> None:
        self.theme_calls.append(name)

    def lookup(self, style_name: str, option: str) -> str:
        return self._lookups.get((style_name, option), "")

    def configure(self, style_name: str, **kwargs: object) -> None:
        self.configure_calls.append((style_name, kwargs))

    def map(self, style_name: str, **kwargs: object) -> None:
        self.map_calls.append((style_name, kwargs))


class _FakeRoot:
    def __init__(
        self,
        *,
        configure_error: Exception | None = None,
        tk_call_error: Exception | None = None,
    ) -> None:
        self._configure_error = configure_error
        self._tk_call_error = tk_call_error
        self.configure_calls: list[dict[str, object]] = []
        self.tk_calls: list[tuple[object, ...]] = []
        self.tk = SimpleNamespace(call=self._tk_call)

    def configure(self, **kwargs: object) -> None:
        self.configure_calls.append(kwargs)
        if self._configure_error is not None:
            raise self._configure_error

    def _tk_call(self, *args: object) -> None:
        self.tk_calls.append(args)
        if self._tk_call_error is not None:
            raise self._tk_call_error


def _patch_style(monkeypatch: pytest.MonkeyPatch, style: _FakeStyle) -> None:
    monkeypatch.setattr(ttk_theme.ttk, "Style", lambda: style)


def _configured_calls(style: _FakeStyle) -> dict[str, dict[str, object]]:
    return {style_name: kwargs for style_name, kwargs in style.configure_calls}


def _mapped_calls(style: _FakeStyle) -> dict[str, dict[str, object]]:
    return {style_name: kwargs for style_name, kwargs in style.map_calls}


def test_apply_clam_light_theme_uses_ttk_lookups_and_optional_checkbutton_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    style = _FakeStyle(
        {
            ("TFrame", "background"): "#fafafa",
            ("TLabel", "foreground"): "#111111",
            ("TEntry", "fieldbackground"): "#ffffff",
            ("TScale", "troughcolor"): "#d7d7d7",
        }
    )
    root = _FakeRoot()

    _patch_style(monkeypatch, style)
    monkeypatch.setenv("KEYRGB_TK_SCALING", "1.5")

    bg_color, fg_color = ttk_theme.apply_clam_light_theme(
        root,
        include_checkbuttons=True,
        map_checkbutton_state=True,
    )

    assert (bg_color, fg_color) == ("#fafafa", "#111111")
    assert style.theme_calls == ["clam"]
    assert root.configure_calls == [{"bg": "#fafafa"}]
    assert root.tk_calls == [("tk", "scaling", 1.5)]

    configured = _configured_calls(style)
    assert configured["TFrame"] == {"background": "#fafafa"}
    assert configured["TLabel"] == {"background": "#fafafa", "foreground": "#111111"}
    assert configured["TLabelframe"] == {"background": "#fafafa", "foreground": "#111111"}
    assert configured["TLabelframe.Label"] == {"background": "#fafafa", "foreground": "#111111"}
    assert configured["TRadiobutton"] == {"background": "#fafafa", "foreground": "#111111"}
    assert configured["TEntry"] == {"fieldbackground": "#ffffff", "foreground": "#111111"}
    assert configured["TCombobox"] == {"fieldbackground": "#ffffff", "foreground": "#111111"}
    assert configured["TSpinbox"] == {"fieldbackground": "#ffffff", "foreground": "#111111"}
    assert configured["TScale"] == {"background": "#fafafa", "troughcolor": "#d7d7d7"}
    assert configured["TScrollbar"] == {"background": "#fafafa", "troughcolor": "#d7d7d7"}
    assert configured["TCheckbutton"] == {"background": "#fafafa", "foreground": "#111111"}

    mapped = _mapped_calls(style)
    assert mapped["TCheckbutton"] == {
        "background": [("disabled", "#fafafa"), ("active", "#fafafa")],
        "foreground": [("disabled", "#777777"), ("!disabled", "#111111")],
    }
    assert mapped["TRadiobutton"] == {
        "background": [("disabled", "#fafafa"), ("active", "#fafafa")],
        "foreground": [("disabled", "#777777"), ("!disabled", "#111111")],
    }


def test_apply_clam_light_theme_falls_back_to_default_colors_and_tolerates_root_configure_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    style = _FakeStyle()
    root = _FakeRoot(configure_error=RuntimeError("no background"))

    _patch_style(monkeypatch, style)
    monkeypatch.delenv("KEYRGB_TK_SCALING", raising=False)

    bg_color, fg_color = ttk_theme.apply_clam_light_theme(
        root,
        include_checkbuttons=True,
        map_checkbutton_state=False,
    )

    assert (bg_color, fg_color) == ("#f0f0f0", "#000000")
    assert root.configure_calls == [{"bg": "#f0f0f0"}]
    assert root.tk_calls == []

    configured = _configured_calls(style)
    assert configured["TEntry"] == {"fieldbackground": "#ffffff", "foreground": "#000000"}
    assert configured["TCombobox"] == {"fieldbackground": "#ffffff", "foreground": "#000000"}
    assert configured["TSpinbox"] == {"fieldbackground": "#ffffff", "foreground": "#000000"}
    assert configured["TScale"] == {"background": "#f0f0f0", "troughcolor": "#ffffff"}
    assert configured["TScrollbar"] == {"background": "#f0f0f0", "troughcolor": "#ffffff"}
    assert configured["TCheckbutton"] == {"background": "#f0f0f0", "foreground": "#000000"}

    mapped = _mapped_calls(style)
    assert "TCheckbutton" not in mapped
    assert mapped["TRadiobutton"] == {
        "background": [("disabled", "#f0f0f0"), ("active", "#f0f0f0")],
        "foreground": [("disabled", "#777777"), ("!disabled", "#000000")],
    }


def test_apply_clam_dark_theme_configures_dark_palette_and_optional_checkbutton_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    style = _FakeStyle()
    root = _FakeRoot()

    _patch_style(monkeypatch, style)
    monkeypatch.delenv("KEYRGB_TK_SCALING", raising=False)

    bg_color, fg_color = ttk_theme.apply_clam_dark_theme(
        root,
        include_checkbuttons=True,
        map_checkbutton_state=True,
    )

    assert (bg_color, fg_color) == ("#2b2b2b", "#e0e0e0")
    assert style.theme_calls == ["clam"]
    assert root.configure_calls == [{"bg": "#2b2b2b"}]

    configured = _configured_calls(style)
    assert configured["TFrame"] == {"background": "#2b2b2b"}
    assert configured["TLabel"] == {"background": "#2b2b2b", "foreground": "#e0e0e0"}
    assert configured["TButton"] == {"background": "#404040", "foreground": "#e0e0e0"}
    assert configured["TLabelframe"] == {"background": "#2b2b2b", "foreground": "#e0e0e0"}
    assert configured["TLabelframe.Label"] == {"background": "#2b2b2b", "foreground": "#e0e0e0"}
    assert configured["TRadiobutton"] == {"background": "#2b2b2b", "foreground": "#e0e0e0"}
    assert configured["TEntry"] == {"fieldbackground": "#3a3a3a", "foreground": "#e0e0e0"}
    assert configured["TCombobox"] == {"fieldbackground": "#3a3a3a", "foreground": "#e0e0e0"}
    assert configured["TSpinbox"] == {"fieldbackground": "#3a3a3a", "foreground": "#e0e0e0"}
    assert configured["TScale"] == {"background": "#2b2b2b", "troughcolor": "#3a3a3a"}
    assert configured["TScrollbar"] == {"background": "#2b2b2b", "troughcolor": "#3a3a3a"}
    assert configured["TCheckbutton"] == {"background": "#2b2b2b", "foreground": "#e0e0e0"}

    mapped = _mapped_calls(style)
    assert mapped["TButton"] == {"background": [("active", "#505050")]}
    assert mapped["TCheckbutton"] == {
        "background": [("disabled", "#2b2b2b"), ("active", "#2b2b2b")],
        "foreground": [("disabled", "#777777"), ("!disabled", "#e0e0e0")],
    }
    assert mapped["TRadiobutton"] == {
        "background": [("disabled", "#2b2b2b"), ("active", "#2b2b2b")],
        "foreground": [("disabled", "#777777"), ("!disabled", "#e0e0e0")],
    }


def test_apply_clam_dark_theme_tolerates_scaling_and_root_configure_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    style = _FakeStyle()
    root = _FakeRoot(
        configure_error=ttk_theme.tk.TclError("no background"),
        tk_call_error=ttk_theme.tk.TclError("no tk scaling"),
    )

    _patch_style(monkeypatch, style)
    monkeypatch.setenv("KEYRGB_TK_SCALING", "1.25")

    bg_color, fg_color = ttk_theme.apply_clam_dark_theme(root)

    assert (bg_color, fg_color) == ("#2b2b2b", "#e0e0e0")
    assert root.configure_calls == [{"bg": "#2b2b2b"}]
    assert root.tk_calls == [("tk", "scaling", 1.25)]
    assert "TCheckbutton" not in _configured_calls(style)


def test_apply_scaling_if_configured_calls_tk_scaling_for_positive_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _FakeRoot()
    monkeypatch.setenv("KEYRGB_TK_SCALING", "2.0")

    ttk_theme._apply_scaling_if_configured(root)

    assert root.tk_calls == [("tk", "scaling", 2.0)]


@pytest.mark.parametrize("raw_value", [None, "", "0", "-1", "not-a-number"])
def test_apply_scaling_if_configured_ignores_missing_invalid_and_non_positive_values(
    monkeypatch: pytest.MonkeyPatch,
    raw_value: str | None,
) -> None:
    root = _FakeRoot()

    if raw_value is None:
        monkeypatch.delenv("KEYRGB_TK_SCALING", raising=False)
    else:
        monkeypatch.setenv("KEYRGB_TK_SCALING", raw_value)

    ttk_theme._apply_scaling_if_configured(root)

    assert root.tk_calls == []


def test_apply_scaling_if_configured_swallows_tk_call_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    root = _FakeRoot(tk_call_error=ttk_theme.tk.TclError("boom"))
    monkeypatch.setenv("KEYRGB_TK_SCALING", "1.1")

    ttk_theme._apply_scaling_if_configured(root)

    assert root.tk_calls == [("tk", "scaling", 1.1)]
