from __future__ import annotations

from typing import ClassVar

from keyrgb.gui.settings import navigation


class _FakeWidget:
    def __init__(self, parent=None, **kwargs) -> None:
        self.parent = parent
        self.kwargs = kwargs


class _FakeNotebook(_FakeWidget):
    def __init__(self, parent=None, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self.add_calls: list[dict[str, object]] = []
        self.select_calls: list[object] = []

    def add(self, child, **kwargs) -> None:
        self.add_calls.append({"child": child, **kwargs})

    def select(self, child) -> None:
        self.select_calls.append(child)


class _FakeScrollArea:
    instances: ClassVar[list[_FakeScrollArea]] = []

    def __init__(self, parent, *, bg_color: str, padding: int) -> None:
        self.parent = parent
        self.bg_color = bg_color
        self.padding = padding
        self.frame = _FakeWidget(parent)
        type(self).instances.append(self)


def _build(**kwargs):
    _FakeScrollArea.instances.clear()
    notebooks: list[_FakeNotebook] = []

    def notebook_cls(parent=None, **kw):
        notebook = _FakeNotebook(parent, **kw)
        notebooks.append(notebook)
        return notebook

    result = navigation.build_navigation(
        object(),
        notebook_cls=notebook_cls,
        frame_cls=_FakeWidget,
        scroll_area_cls=_FakeScrollArea,
        bg_color="#abc",
        **kwargs,
    )
    return result, notebooks[0]


def test_category_order_titles_and_default() -> None:
    assert navigation.CATEGORY_IDS == ("lighting_power", "automation", "app", "advanced", "about")
    assert navigation.CATEGORY_TITLES == ("Lighting & Power", "Automation", "App", "Advanced", "About & Support")
    assert navigation.DEFAULT_CATEGORY_ID == "lighting_power"
    assert navigation.CATEGORY_BY_ID["automation"].panels == ("dim_sync", "time_scheduler")
    assert navigation.CATEGORY_BY_ID["lighting_power"].panels == ("management", "power_source")
    assert navigation.CATEGORY_BY_ID["app"].panels == ("autostart",)
    assert navigation.CATEGORY_BY_ID["advanced"].panels == ("idle_transition_advanced", "experimental")
    assert navigation.CATEGORY_BY_ID["about"].panels == ("version",)


def test_build_navigation_creates_one_page_per_category_with_expected_parents() -> None:
    result, notebook = _build()

    assert set(result.page_frames) == set(navigation.CATEGORY_IDS)
    assert set(result.scroll_areas) == set(navigation.CATEGORY_IDS)
    assert notebook.add_calls == [
        {"child": result.page_frames[category.id], "text": category.title} for category in navigation.CATEGORIES
    ]
    for category in navigation.CATEGORIES:
        page = result.page_frames[category.id]
        assert page.parent is notebook
        scroll = result.scroll_areas[category.id]
        assert scroll.parent is page
        assert scroll.bg_color == "#abc"
        assert scroll.padding == 10
    # Exactly one scroll area per category: tab switches reselect, never rebuild.
    assert len(_FakeScrollArea.instances) == len(navigation.CATEGORIES)


def test_build_navigation_selects_default_category() -> None:
    result, notebook = _build()

    assert notebook.select_calls == [result.page_frames[navigation.DEFAULT_CATEGORY_ID]]


def test_build_navigation_maps_every_declared_panel_to_its_category_page() -> None:
    result, _notebook = _build()

    expected: dict[str, object] = {}
    for category in navigation.CATEGORIES:
        for panel_id in category.panels:
            expected[panel_id] = result.scroll_areas[category.id].frame
    assert result.panel_parents == expected
    assert set(result.panel_parents) == {
        "management",
        "power_source",
        "dim_sync",
        "time_scheduler",
        "autostart",
        "idle_transition_advanced",
        "experimental",
        "version",
    }
    # Panels sharing a category share one content frame.
    assert result.panel_parents["management"] is result.panel_parents["power_source"]
    assert result.panel_parents["dim_sync"] is result.panel_parents["time_scheduler"]
    assert result.panel_parents["idle_transition_advanced"] is result.panel_parents["experimental"]
