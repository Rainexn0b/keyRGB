from __future__ import annotations

from types import SimpleNamespace

import pytest

from keyrgb.gui.theme import metrics, ttk as ttk_theme


class _FakeStyle:
    def __init__(self, lookups: dict[tuple[str, str], str] | None = None) -> None:
        self._lookups = dict(lookups or {})
        self.map_calls: list[tuple[str, dict[str, object]]] = []
        self.configure_calls: list[tuple[str, dict[str, object]]] = []

    def theme_use(self, name: str) -> None:
        pass

    def lookup(self, style_name: str, option: str) -> str:
        return self._lookups.get((style_name, option), "")

    def configure(self, style_name: str, **kwargs: object) -> None:
        self.configure_calls.append((style_name, kwargs))

    def map(self, style_name: str, **kwargs: object) -> None:
        self.map_calls.append((style_name, kwargs))


class _FakeRoot:
    def __init__(self) -> None:
        self.tk = SimpleNamespace(call=lambda *args: None)

    def configure(self, **kwargs: object) -> None:
        pass


def _patch_style(monkeypatch: pytest.MonkeyPatch, style: _FakeStyle) -> None:
    monkeypatch.setattr(ttk_theme.ttk, "Style", lambda _root=None: style)


@pytest.fixture(autouse=True)
def _headless_fonts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep map tests independent of any ambient Tk interpreter.

    Font-specific tests below re-patch ``nametofont`` with richer fakes.
    """

    def _no_tk(name: str, root: object = None) -> object:
        raise ttk_theme.tk.TclError("no display")

    monkeypatch.setattr(ttk_theme.tkfont, "nametofont", _no_tk)


def _merged_maps(style: _FakeStyle) -> dict[str, dict[str, object]]:
    merged: dict[str, dict[str, object]] = {}
    for style_name, kwargs in style.map_calls:
        merged.setdefault(style_name, {}).update(kwargs)
    return merged


def _states_of(mapped: dict[str, object]) -> set[str]:
    states: set[str] = set()
    for specs in mapped.values():
        assert isinstance(specs, list)
        for spec in specs:
            assert isinstance(spec, tuple)
            states.update(str(part) for part in spec[0:-1] for part in str(spec[0]).split())
            states.add(str(spec[0]))
    return states


@pytest.mark.parametrize("apply", ["light", "dark"])
def test_focus_maps_cover_interactive_controls(monkeypatch: pytest.MonkeyPatch, apply: str) -> None:
    style = _FakeStyle(
        {
            ("TFrame", "background"): "#fafafa",
            ("TLabel", "foreground"): "#111111",
            ("TEntry", "fieldbackground"): "#ffffff",
        }
    )
    _patch_style(monkeypatch, style)
    monkeypatch.delenv("KEYRGB_TK_SCALING", raising=False)

    if apply == "light":
        ttk_theme.apply_clam_light_theme(_FakeRoot())  # type: ignore[arg-type]
    else:
        ttk_theme.apply_clam_dark_theme(_FakeRoot())  # type: ignore[arg-type]

    mapped = _merged_maps(style)
    for style_name in (*metrics.FOCUSABLE_BASE_STYLES, *metrics.SEMANTIC_BUTTON_STYLES):
        assert style_name in mapped, style_name
        assert "focus" in _states_of(mapped[style_name]), style_name


@pytest.mark.parametrize("apply", ["light", "dark"])
def test_disabled_maps_cover_interactive_controls(monkeypatch: pytest.MonkeyPatch, apply: str) -> None:
    style = _FakeStyle()
    _patch_style(monkeypatch, style)
    monkeypatch.delenv("KEYRGB_TK_SCALING", raising=False)

    if apply == "light":
        ttk_theme.apply_clam_light_theme(_FakeRoot())  # type: ignore[arg-type]
    else:
        ttk_theme.apply_clam_dark_theme(_FakeRoot())  # type: ignore[arg-type]

    mapped = _merged_maps(style)
    for style_name in (*metrics.FOCUSABLE_BASE_STYLES, *metrics.SEMANTIC_BUTTON_STYLES):
        assert style_name in mapped, style_name
        assert "disabled" in _states_of(mapped[style_name]), style_name


def test_ensure_theme_fonts_uses_absolute_sizes_not_base_derivation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Live KDE/Tk sessions report TkDefaultFont as fixed 8; roles must keep Sans 14/11/10/9/8."""

    created: dict[str, object] = {}
    creation_counts: dict[str, int] = {}
    nametofont_calls: list[tuple[str, object]] = []

    class _FakeBaseFont:
        def actual(self) -> dict[str, object]:
            return {"size": 8, "family": "fixed", "slant": "roman"}

    class _FakeFont:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs
            name = str(kwargs.get("name"))
            created[name] = self
            creation_counts[name] = creation_counts.get(name, 0) + 1

        def configure(self, **kwargs: object) -> None:
            self.kwargs.update(kwargs)

    def _fake_nametofont(name: str, root: object = None) -> object:
        nametofont_calls.append((name, root))
        if name == "TkDefaultFont":
            return _FakeBaseFont()
        raise ttk_theme.tk.TclError("missing")

    monkeypatch.setattr(ttk_theme.tkfont, "nametofont", _fake_nametofont)
    monkeypatch.setattr(ttk_theme.tkfont, "Font", _FakeFont)
    monkeypatch.setattr(ttk_theme, "_FONT_REFS", {})

    root = _FakeRoot()
    fonts = ttk_theme.ensure_theme_fonts(root)  # type: ignore[arg-type]

    assert fonts[metrics.TITLE_LABEL_STYLE] == metrics.TITLE_FONT_NAME
    # The supplied root is forwarded instead of relying on the implicit root.
    assert ("TkDefaultFont", root) in nametofont_calls
    expected_sizes = {
        metrics.TITLE_FONT_NAME: 14,
        metrics.SECTION_FONT_NAME: 11,
        metrics.BODY_FONT_NAME: 9,
        metrics.CAPTION_FONT_NAME: 8,
        metrics.STATUS_FONT_NAME: 9,
        metrics.VALUE_FONT_NAME: 10,
        metrics.ACTION_FONT_NAME: 9,
    }
    assert set(created) == set(expected_sizes)
    for font_name, size in expected_sizes.items():
        font = created[font_name]
        assert isinstance(font, _FakeFont)
        assert font.kwargs["root"] is root
        assert font.kwargs["family"] == "Sans"
        assert font.kwargs["slant"] == "roman"
        assert font.kwargs["size"] == size
    title_font = created[metrics.TITLE_FONT_NAME]
    assert isinstance(title_font, _FakeFont)
    assert title_font.kwargs["weight"] == "bold"
    assert {font_name for _interpreter_id, font_name in ttk_theme._FONT_REFS} == set(metrics.FONT_SPECS)
    assert creation_counts[metrics.ACTION_FONT_NAME] == 1


def test_ensure_theme_fonts_reuses_existing_named_fonts_with_supplied_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nametofont_calls: list[tuple[str, object]] = []
    configured_calls: list[dict[str, object]] = []

    class _FakeBaseFont:
        def actual(self) -> dict[str, object]:
            return {"size": 8, "family": "fixed", "slant": "italic"}

    class _FakeExistingFont:
        def configure(self, **kwargs: object) -> None:
            configured_calls.append(kwargs)

    def _fake_nametofont(name: str, root: object = None) -> object:
        nametofont_calls.append((name, root))
        return _FakeBaseFont() if name == "TkDefaultFont" else _FakeExistingFont()

    monkeypatch.setattr(ttk_theme.tkfont, "nametofont", _fake_nametofont)
    monkeypatch.setattr(ttk_theme, "_FONT_REFS", {})

    root = _FakeRoot()
    fonts = ttk_theme.ensure_theme_fonts(root)  # type: ignore[arg-type]

    assert fonts[metrics.BODY_LABEL_STYLE] == metrics.BODY_FONT_NAME
    assert all(passed_root is root for _, passed_root in nametofont_calls)
    assert len(configured_calls) == len(metrics.FONT_NAME_BY_STYLE)
    body_index = list(metrics.FONT_NAME_BY_STYLE).index(metrics.BODY_LABEL_STYLE)
    assert configured_calls[body_index]["family"] == "Sans"
    assert configured_calls[body_index]["size"] == 9
    assert configured_calls[body_index]["slant"] == "italic"


def test_ensure_theme_fonts_ignores_negative_pixel_base_sizes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Negative TkDefaultFont sizes are pixel sizes; roles must stay absolute points."""

    created: dict[str, object] = {}

    class _FakeBaseFont:
        def actual(self) -> dict[str, object]:
            return {"size": -12, "family": "fixed", "slant": "roman"}

    class _FakeFont:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs
            created[str(kwargs.get("name"))] = self

        def configure(self, **kwargs: object) -> None:
            self.kwargs.update(kwargs)

    def _fake_nametofont(name: str, root: object = None) -> object:
        if name == "TkDefaultFont":
            return _FakeBaseFont()
        raise ttk_theme.tk.TclError("missing")

    monkeypatch.setattr(ttk_theme.tkfont, "nametofont", _fake_nametofont)
    monkeypatch.setattr(ttk_theme.tkfont, "Font", _FakeFont)
    monkeypatch.setattr(ttk_theme, "_FONT_REFS", {})

    fonts = ttk_theme.ensure_theme_fonts()

    assert fonts[metrics.TITLE_LABEL_STYLE] == metrics.TITLE_FONT_NAME
    title_font = created[metrics.TITLE_FONT_NAME]
    assert isinstance(title_font, _FakeFont)
    assert title_font.kwargs["family"] == "Sans"
    assert title_font.kwargs["size"] == 14


def test_ensure_theme_fonts_defaults_invalid_base_slant(monkeypatch: pytest.MonkeyPatch) -> None:
    created: dict[str, object] = {}

    class _FakeBaseFont:
        def actual(self) -> dict[str, object]:
            return {"size": 8, "family": "fixed", "slant": "oblique"}

    class _FakeFont:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs
            created[str(kwargs.get("name"))] = self

        def configure(self, **kwargs: object) -> None:
            self.kwargs.update(kwargs)

    def _fake_nametofont(name: str, root: object = None) -> object:
        if name == "TkDefaultFont":
            return _FakeBaseFont()
        raise ttk_theme.tk.TclError("missing")

    monkeypatch.setattr(ttk_theme.tkfont, "nametofont", _fake_nametofont)
    monkeypatch.setattr(ttk_theme.tkfont, "Font", _FakeFont)
    monkeypatch.setattr(ttk_theme, "_FONT_REFS", {})

    fonts = ttk_theme.ensure_theme_fonts()

    assert fonts[metrics.BODY_LABEL_STYLE] == metrics.BODY_FONT_NAME
    body_font = created[metrics.BODY_FONT_NAME]
    assert isinstance(body_font, _FakeFont)
    assert body_font.kwargs["slant"] == "roman"


def test_ensure_theme_fonts_returns_empty_without_tk(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(name: str, root: object = None) -> object:
        raise ttk_theme.tk.TclError("no display")

    monkeypatch.setattr(ttk_theme.tkfont, "nametofont", _raise)

    assert ttk_theme.ensure_theme_fonts() == {}
