from __future__ import annotations

from types import SimpleNamespace

import pytest

from keyrgb.gui.theme import metrics, ttk as ttk_theme


class _FakeStyle:
    def __init__(self, lookups: dict[tuple[str, str], str] | None = None) -> None:
        self._lookups = dict(lookups or {})
        self.theme_calls: list[str] = []
        self.configure_calls: list[tuple[str, dict[str, object]]] = []
        self.map_calls: list[tuple[str, dict[str, object]]] = []

    def theme_use(self, name: str) -> None:
        self.theme_calls.append(name)

    def layout(self, name: str, layout: list) -> None:
        assert name == "TSeparator"

    def theme_names(self) -> tuple[str, ...]:
        return ("clam",)

    def theme_create(self, name: str, *, parent: str, settings: dict) -> None:
        assert name == ttk_theme.DARK_THEME_NAME and parent == "clam"
        assert "TButton" in settings

    def lookup(self, style_name: str, option: str) -> str:
        return self._lookups.get((style_name, option), "")

    def configure(self, style_name: str, **kwargs: object) -> object:
        if not kwargs:
            return _configured_calls(self).get(style_name, {})
        self.configure_calls.append((style_name, kwargs))
        return None

    def map(self, style_name: str, option: str | None = None, **kwargs: object) -> object:
        if option is not None:
            return _mapped_calls(self)[style_name][option]
        if not kwargs:
            return _mapped_calls(self).get(style_name, {})
        self.map_calls.append((style_name, kwargs))
        return None


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
        self.option_calls: list[tuple[str, str, str]] = []

    def option_add(self, pattern: str, value: str, priority: str) -> None:
        self.option_calls.append((pattern, value, priority))

    def configure(self, **kwargs: object) -> None:
        self.configure_calls.append(kwargs)
        if self._configure_error is not None:
            raise self._configure_error

    def _tk_call(self, *args: object) -> None:
        self.tk_calls.append(args)
        if self._tk_call_error is not None:
            raise self._tk_call_error


def _patch_style(monkeypatch: pytest.MonkeyPatch, style: _FakeStyle) -> None:
    monkeypatch.setattr(ttk_theme.ttk, "Style", lambda _root=None: style)


@pytest.fixture(autouse=True)
def _headless_fonts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep apply-path tests independent of any ambient Tk interpreter."""

    def _no_tk(name: str, root: object = None) -> object:
        raise ttk_theme.tk.TclError("no display")

    monkeypatch.setattr(ttk_theme.tkfont, "nametofont", _no_tk)


def _configured_calls(style: _FakeStyle) -> dict[str, dict[str, object]]:
    merged: dict[str, dict[str, object]] = {}
    for style_name, kwargs in style.configure_calls:
        merged.setdefault(style_name, {}).update(kwargs)
    return merged


def _mapped_calls(style: _FakeStyle) -> dict[str, dict[str, object]]:
    merged: dict[str, dict[str, object]] = {}
    for style_name, kwargs in style.map_calls:
        merged.setdefault(style_name, {}).update(kwargs)
    return merged


def test_apply_clam_light_theme_uses_ttk_lookups_and_centralized_checkbutton_mapping(
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

    bg_color, fg_color = ttk_theme.apply_clam_light_theme(root)

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
    # Checkbutton styling is centralized.
    assert configured["TCheckbutton"] == {"background": "#fafafa", "foreground": "#111111"}

    mapped = _mapped_calls(style)
    assert mapped["TCombobox"]["fieldbackground"] == [
        ("disabled", "#ffffff"),
        ("readonly", "#ffffff"),
        ("focus", "#ffffff"),
    ]
    assert mapped["TCombobox"]["foreground"] == [
        ("disabled", ttk_theme.LIGHT_DISABLED_FG),
        ("readonly", "#111111"),
        ("!disabled", "#111111"),
    ]
    assert mapped["TCheckbutton"]["foreground"] == [
        ("disabled", ttk_theme.LIGHT_DISABLED_FG),
        ("!disabled", "#111111"),
    ]
    assert mapped["TRadiobutton"]["foreground"] == [
        ("disabled", ttk_theme.LIGHT_DISABLED_FG),
        ("!disabled", "#111111"),
    ]
    assert mapped["TButton"]["foreground"] == [
        ("disabled", ttk_theme.LIGHT_DISABLED_FG),
        ("!disabled", "#111111"),
    ]


def test_apply_clam_light_theme_falls_back_to_default_colors_and_tolerates_root_configure_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    style = _FakeStyle()
    root = _FakeRoot(configure_error=RuntimeError("no background"))

    _patch_style(monkeypatch, style)
    monkeypatch.delenv("KEYRGB_TK_SCALING", raising=False)

    bg_color, fg_color = ttk_theme.apply_clam_light_theme(root)

    assert (bg_color, fg_color) == ("#f0f0f0", "#000000")
    assert root.configure_calls == [{"bg": "#f0f0f0"}]
    assert root.tk_calls == []

    configured = _configured_calls(style)
    assert configured["TEntry"] == {"fieldbackground": "#ffffff", "foreground": "#000000"}
    assert configured["TCombobox"] == {"fieldbackground": "#ffffff", "foreground": "#000000"}
    assert configured["TSpinbox"] == {"fieldbackground": "#ffffff", "foreground": "#000000"}
    assert configured["TScale"] == {"background": "#f0f0f0", "troughcolor": "#ffffff"}
    assert configured["TScrollbar"] == {"background": "#f0f0f0", "troughcolor": "#ffffff"}
    # Checkbutton styling is centralized.
    assert configured["TCheckbutton"] == {"background": "#f0f0f0", "foreground": "#000000"}

    mapped = _mapped_calls(style)
    assert mapped["TCombobox"]["foreground"] == [
        ("disabled", ttk_theme.LIGHT_DISABLED_FG),
        ("readonly", "#000000"),
        ("!disabled", "#000000"),
    ]
    assert "TCheckbutton" in mapped
    assert mapped["TRadiobutton"]["foreground"] == [
        ("disabled", ttk_theme.LIGHT_DISABLED_FG),
        ("!disabled", "#000000"),
    ]


def test_apply_clam_dark_theme_configures_dark_palette_and_centralized_checkbutton_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    style = _FakeStyle()
    root = _FakeRoot()

    _patch_style(monkeypatch, style)
    monkeypatch.delenv("KEYRGB_TK_SCALING", raising=False)

    bg_color, fg_color = ttk_theme.apply_clam_dark_theme(root)

    assert (bg_color, fg_color) == ("#2b2b2b", "#e0e0e0")
    assert style.theme_calls == ["clam", ttk_theme.DARK_THEME_NAME]
    assert root.configure_calls == [{"bg": "#2b2b2b"}]

    configured = _configured_calls(style)
    assert configured["TFrame"] == {"background": "#2b2b2b"}
    assert configured["TLabel"] == {"background": "#2b2b2b", "foreground": "#e0e0e0"}
    assert configured["TButton"]["background"] == "#404040"
    assert configured["TButton"]["foreground"] == "#e0e0e0"
    assert configured["TButton"]["relief"] == "flat"
    assert configured["TLabelframe"] == {
        "background": "#2b2b2b",
        "foreground": "#e0e0e0",
        "borderwidth": 0,
        "relief": "flat",
    }
    assert configured["TLabelframe.Label"] == {"background": "#2b2b2b", "foreground": "#e0e0e0"}
    for name in ("TEntry", "TCombobox", "TSpinbox"):
        assert configured[name]["fieldbackground"] == "#3a3a3a"
        assert configured[name]["foreground"] == "#e0e0e0"
        assert configured[name]["bordercolor"] == ttk_theme.DARK_BORDER
    for name in ("TScale", "TScrollbar"):
        assert configured[name]["background"] == (
            ttk_theme.DARK_FOCUS if name == "TScale" else ttk_theme.DARK_BUTTON_BG
        )
        assert configured[name]["troughcolor"] == "#3a3a3a"
    for name in ("TCheckbutton", "TRadiobutton"):
        assert configured[name]["background"] == "#2b2b2b"
        assert configured[name]["foreground"] == "#e0e0e0"
        assert configured[name]["indicatorbackground"] == "#3a3a3a"

    mapped = _mapped_calls(style)
    assert mapped["TButton"]["background"] == [
        ("disabled", "#2b2b2b"),
        ("pressed", "#3a3a3a"),
        ("active", "#505050"),
        ("focus", "#505050"),
    ]
    assert mapped["TCombobox"]["fieldbackground"] == [
        ("disabled", "#3a3a3a"),
        ("readonly", "#3a3a3a"),
        ("focus", "#3a3a3a"),
    ]
    assert mapped["TCombobox"]["foreground"] == [
        ("disabled", ttk_theme.DARK_DISABLED_FG),
        ("readonly", "#e0e0e0"),
        ("!disabled", "#e0e0e0"),
    ]
    assert mapped["TCheckbutton"]["foreground"] == [
        ("disabled", ttk_theme.DARK_DISABLED_FG),
        ("!disabled", "#e0e0e0"),
    ]
    assert mapped["TRadiobutton"]["foreground"] == [
        ("disabled", ttk_theme.DARK_DISABLED_FG),
        ("!disabled", "#e0e0e0"),
    ]


def test_dark_surfaces_override_stock_bevels_tabs_and_indicators(monkeypatch: pytest.MonkeyPatch) -> None:
    style = _FakeStyle()
    root = _FakeRoot()
    _patch_style(monkeypatch, style)
    ttk_theme.apply_clam_dark_theme(root)
    configured = _configured_calls(style)
    mapped = _mapped_calls(style)
    for name in ("TButton", *metrics.SEMANTIC_BUTTON_STYLES):
        assert configured[name]["relief"] == "flat"
        assert mapped[name]["bordercolor"][0:2] == [("disabled", ttk_theme.DARK_BG), ("focus", ttk_theme.DARK_FOCUS)]
        assert mapped[name]["background"][1] == ("pressed", ttk_theme.DARK_FIELD_BG)
        assert "lightcolor" in mapped[name] and "darkcolor" in mapped[name]
    assert configured["TNotebook"]["borderwidth"] == 0
    assert mapped["TNotebook.Tab"]["background"][1] == ("selected", ttk_theme.DARK_FIELD_BG)
    assert mapped["TNotebook.Tab"]["bordercolor"] == [
        ("disabled", ttk_theme.DARK_BG),
        ("selected", ttk_theme.DARK_FIELD_BG),
        ("!selected", ttk_theme.DARK_BG),
    ]
    assert configured["TNotebook.Tab"]["focuscolor"] == ttk_theme.DARK_FOCUS
    for name in ("TCheckbutton", "TRadiobutton"):
        assert configured[name]["indicatorbackground"] == ttk_theme.DARK_FIELD_BG
        assert mapped[name]["indicatorbackground"][0] == ("disabled", ttk_theme.DARK_BG)
        assert mapped[name]["upperbordercolor"][0] == ("focus", ttk_theme.DARK_FOCUS)
    assert configured["TScale"]["gripsize"] == 0
    assert ("*Canvas.highlightBackground", ttk_theme.DARK_BORDER, "widgetDefault") in root.option_calls


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
    # Checkbutton styling is centralized.
    assert "TCheckbutton" in _configured_calls(style)
    assert "TCheckbutton" in _mapped_calls(style)


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


def test_semantic_styles_use_named_fonts_not_local_tuples(monkeypatch: pytest.MonkeyPatch) -> None:
    style = _FakeStyle()
    root = _FakeRoot()
    _patch_style(monkeypatch, style)
    monkeypatch.setattr(ttk_theme, "ensure_theme_fonts", lambda _root: dict(metrics.FONT_NAME_BY_STYLE))
    monkeypatch.delenv("KEYRGB_TK_SCALING", raising=False)

    ttk_theme.apply_clam_dark_theme(root)

    configured = _configured_calls(style)
    for semantic in metrics.ALL_SEMANTIC_STYLES:
        assert semantic in configured
        font_value = configured[semantic].get("font")
        assert isinstance(font_value, str)
        assert font_value in metrics.FONT_SPECS


def test_theme_style_uses_the_supplied_root(monkeypatch: pytest.MonkeyPatch) -> None:
    style = _FakeStyle()
    roots: list[object] = []
    root = _FakeRoot()
    monkeypatch.setattr(ttk_theme.ttk, "Style", lambda supplied_root=None: roots.append(supplied_root) or style)
    monkeypatch.delenv("KEYRGB_TK_SCALING", raising=False)

    ttk_theme.apply_clam_dark_theme(root)

    assert roots == [root]


def test_semantic_styles_inherit_safely_when_named_fonts_are_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    style = _FakeStyle()
    root = _FakeRoot()
    _patch_style(monkeypatch, style)
    monkeypatch.delenv("KEYRGB_TK_SCALING", raising=False)

    ttk_theme.apply_clam_dark_theme(root)

    configured = _configured_calls(style)
    for semantic in metrics.ALL_SEMANTIC_STYLES:
        assert semantic in configured
        assert "font" not in configured[semantic]
