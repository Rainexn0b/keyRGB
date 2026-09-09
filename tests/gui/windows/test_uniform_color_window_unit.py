from __future__ import annotations

from types import SimpleNamespace

import pytest

from keyrgb.gui.windows import (
    _uniform_color_bootstrap as uniform_color_bootstrap,
    uniform,
)


class _FakeWidget:
    def __init__(self, parent=None, **kwargs) -> None:
        self.parent = parent
        self.kwargs = kwargs
        self.pack_calls: list[dict[str, object]] = []
        self.grid_calls: list[dict[str, object]] = []
        self.bind_calls: list[tuple[str, object]] = []
        self.configure_calls: list[dict[str, object]] = []
        self.columnconfigure_calls: list[tuple[int, int]] = []

    def pack(self, **kwargs) -> None:
        self.pack_calls.append(dict(kwargs))

    def grid(self, **kwargs) -> None:
        self.grid_calls.append(dict(kwargs))

    def bind(self, sequence: str, callback, add=None) -> None:
        self.bind_calls.append((sequence, callback, add))

    def configure(self, **kwargs) -> None:
        self.configure_calls.append(dict(kwargs))

    def columnconfigure(self, index: int, weight: int = 0, **_kwargs) -> None:
        self.columnconfigure_calls.append((index, weight))

    def config(self, **kwargs) -> None:
        self.configure(**kwargs)

    def winfo_width(self) -> int:
        return int(self.kwargs.get("width_px", 560))

    def winfo_reqwidth(self) -> int:
        return int(self.kwargs.get("reqwidth_px", self.winfo_width()))

    def winfo_reqheight(self) -> int:
        return int(self.kwargs.get("reqheight_px", 640))


class _FakeRoot:
    def __init__(self) -> None:
        self.title_calls: list[str] = []
        self.geometry_calls: list[str] = []
        self.minsize_calls: list[tuple[int, int]] = []
        self.resizable_calls: list[tuple[bool, bool]] = []
        self.after_calls: list[tuple[int, object]] = []
        self.destroy_calls = 0
        self.update_idletasks_calls = 0
        self.protocol_calls: list[tuple[str, object]] = []
        self.bind_calls: list[tuple[str, object, object | None]] = []

    def title(self, text: str) -> None:
        self.title_calls.append(text)

    def geometry(self, value: str) -> None:
        self.geometry_calls.append(value)

    def minsize(self, width: int, height: int) -> None:
        self.minsize_calls.append((width, height))

    def resizable(self, width: bool, height: bool) -> None:
        self.resizable_calls.append((width, height))

    def after(self, delay: int, callback) -> None:
        self.after_calls.append((delay, callback))

    def update_idletasks(self) -> None:
        self.update_idletasks_calls += 1

    def winfo_screenwidth(self) -> int:
        return 800

    def winfo_screenheight(self) -> int:
        return 600

    def destroy(self) -> None:
        self.destroy_calls += 1

    def protocol(self, name: str, callback) -> None:
        self.protocol_calls.append((name, callback))

    def bind(self, sequence: str, callback, add=None) -> None:
        self.bind_calls.append((sequence, callback, add))


class _FakeColorWheel:
    def __init__(self, parent, *, size: int, initial_color: tuple[int, int, int], callback, release_callback) -> None:
        self.parent = parent
        self.size = size
        self.initial_color = initial_color
        self.callback = callback
        self.release_callback = release_callback
        self.pack_calls: list[dict[str, object]] = []

    def pack(self, **kwargs) -> None:
        self.pack_calls.append(dict(kwargs))

    def get_color(self) -> tuple[int, int, int]:
        return self.initial_color


def test_resolve_secondary_route_prefers_requested_backend_route() -> None:
    sentinel = SimpleNamespace(display_name="Mouse")

    result = uniform_color_bootstrap.resolve_secondary_route(
        target_context="mouse:external",
        requested_backend="ite8291r3_perkey",
        route_for_backend_name_fn=lambda name: sentinel if name == "ite8291r3_perkey" else None,
        route_for_device_type_fn=lambda _name: (_ for _ in ()).throw(AssertionError("unexpected device type")),
    )

    assert result is sentinel


def test_probe_color_support_fails_closed_when_backend_capability_probe_fails() -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)

    class BrokenBackend:
        def capabilities(self):
            raise RuntimeError("boom")

    assert gui._probe_color_support(BrokenBackend()) is False


def test_probe_color_support_propagates_unexpected_capability_failure() -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)

    class BrokenBackend:
        def capabilities(self):
            raise AssertionError("boom")

    with pytest.raises(AssertionError):
        gui._probe_color_support(BrokenBackend())


def test_select_backend_best_effort_propagates_unexpected_selection_failure(monkeypatch) -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)
    gui.requested_backend = "sysfs-leds"

    monkeypatch.setattr(uniform, "select_backend", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("boom")))

    with pytest.raises(AssertionError):
        gui._select_backend_best_effort()


def test_select_backend_best_effort_uses_secondary_route_backend(monkeypatch) -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)
    sentinel = object()
    gui._secondary_route = SimpleNamespace(get_backend=lambda: sentinel)

    monkeypatch.setattr(uniform, "select_backend", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("boom")))

    assert gui._select_backend_best_effort() is sentinel


def test_secondary_uniform_window_uses_runtime_backend_and_device_in_simulation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from keyrgb.core.secondary_device_routes import route_for_device_type
    from keyrgb.core.secondary_device_runtime import SIMULATION_ENVIRONMENT_VARIABLE

    monkeypatch.setenv(SIMULATION_ENVIRONMENT_VARIABLE, "1")
    route = route_for_device_type("logo")
    assert route is not None

    backend = uniform_color_bootstrap.select_backend_best_effort(
        route,
        requested_backend="ignored-real-backend",
        select_backend_fn=lambda **_kwargs: (_ for _ in ()).throw(AssertionError("real selector called")),
        logger=uniform_color_bootstrap.logging.getLogger(__name__),
    )
    assert backend is not None
    assert str(getattr(backend, "name", "")) == "simulated:ite8258-chassis-logo"

    device = uniform_color_bootstrap.acquire_device_best_effort(
        None,
        secondary_route=route,
        is_device_busy_fn=lambda _exc: False,
        logger=uniform_color_bootstrap.logging.getLogger(__name__),
    )
    assert device is not None
    assert device.device_type == "logo"


def test_acquire_device_best_effort_returns_none_when_device_is_busy(monkeypatch) -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)
    err = OSError("busy")

    class BusyBackend:
        def get_device(self):
            raise err

    monkeypatch.setattr(uniform, "is_device_busy", lambda exc: exc is err)

    assert gui._acquire_device_best_effort(BusyBackend()) is None


def test_acquire_device_best_effort_propagates_unexpected_runtime_failure() -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)

    class BrokenBackend:
        def get_device(self):
            raise AssertionError("boom")

    with pytest.raises(AssertionError):
        gui._acquire_device_best_effort(BrokenBackend())


def test_device_bootstrap_stays_config_only_when_hardware_is_not_allowed() -> None:
    state = uniform.uniform_init_adapter.initialize_device_bootstrap_state(
        secondary_route=None,
        requested_backend=None,
        select_backend_fn=lambda **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected selection")),
        is_device_busy_fn=lambda _exc: False,
        logger=uniform.logger,
        allow_hardware=False,
    )

    assert state.backend is None
    assert state.color_supported is True
    assert state.device is None


def test_apply_color_returns_false_for_recoverable_runtime_failure() -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)

    class BrokenKeyboard:
        def set_color(self, _color, *, brightness: int):
            assert brightness == 25
            raise RuntimeError("boom")

    gui.kb = BrokenKeyboard()

    assert gui._apply_color(1, 2, 3, 25) is False


def test_apply_color_propagates_unexpected_write_failure() -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)

    class BrokenKeyboard:
        def set_color(self, _color, *, brightness: int):
            assert brightness == 25
            raise AssertionError("boom")

    gui.kb = BrokenKeyboard()

    with pytest.raises(AssertionError, match="boom"):
        gui._apply_color(1, 2, 3, 25)


def test_commit_color_to_config_uses_secondary_route_state(monkeypatch) -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)
    calls: list[tuple[str, tuple[int, int, int], str | None]] = []
    enabled_calls: list[tuple[str, bool]] = []
    profile_updates: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "keyrgb.gui.windows._uniform_color_state.profiles.update_secondary_lighting_area",
        lambda state_key, updates: profile_updates.append((state_key, dict(updates))),
    )

    class _Config:
        effect = "wave"

        def set_secondary_device_color(self, state_key: str, color, *, compatibility_key=None, default=(255, 0, 0)):
            assert default == (255, 0, 0)
            calls.append((state_key, tuple(color), compatibility_key))

        def set_secondary_device_enabled(self, state_key: str, enabled: bool):
            enabled_calls.append((state_key, enabled))

    gui.config = _Config()
    gui._target_is_secondary = True
    gui._secondary_route = SimpleNamespace(state_key="mouse", config_color_attr=None)

    gui._commit_color_to_config(4, 5, 6)

    assert calls == [("mouse", (4, 5, 6), None)]
    assert enabled_calls == [("mouse", True)]
    assert profile_updates == [("mouse", {"enabled": True, "color": [4, 5, 6]})]
    assert gui.config.effect == "wave"


def test_secondary_uniform_color_uses_primary_brightness_for_shared_zone() -> None:
    from keyrgb.core.secondary_device_routes import BRIGHTNESS_POLICY_PRIMARY_SHARED

    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)
    gui.config = SimpleNamespace(
        brightness=40,
        get_secondary_device_brightness=lambda *_args, **_kwargs: 10,
    )
    gui._target_is_secondary = True
    gui._secondary_route = SimpleNamespace(
        brightness_policy=BRIGHTNESS_POLICY_PRIMARY_SHARED,
        state_key="logo",
        config_brightness_attr=None,
    )

    assert gui._current_brightness() == 40


def test_secondary_uniform_color_does_not_store_brightness_for_shared_zone() -> None:
    from keyrgb.core.secondary_device_routes import BRIGHTNESS_POLICY_PRIMARY_SHARED

    writes: list[int] = []
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)
    gui.config = SimpleNamespace(
        brightness=40,
        set_secondary_device_brightness=lambda *_args, **_kwargs: writes.append(1),
    )
    gui._target_is_secondary = True
    gui._secondary_route = SimpleNamespace(
        brightness_policy=BRIGHTNESS_POLICY_PRIMARY_SHARED,
        state_key="logo",
        config_brightness_attr=None,
    )

    gui._store_brightness(25)

    assert writes == []


def test_secondary_uniform_color_stores_independent_brightness_in_active_profile(monkeypatch) -> None:
    from keyrgb.core.secondary_device_routes import BRIGHTNESS_POLICY_INDEPENDENT

    config_writes: list[tuple[str, int, str | None]] = []
    profile_updates: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "keyrgb.gui.windows._uniform_color_state.profiles.update_secondary_lighting_area",
        lambda state_key, updates: profile_updates.append((state_key, dict(updates))),
    )
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)
    gui.config = SimpleNamespace(
        set_secondary_device_brightness=lambda state_key, value, *, compatibility_key=None: config_writes.append(
            (state_key, value, compatibility_key)
        )
    )
    gui._target_is_secondary = True
    gui._secondary_route = SimpleNamespace(
        brightness_policy=BRIGHTNESS_POLICY_INDEPENDENT,
        state_key="lightbar",
        config_brightness_attr="lightbar_brightness",
    )

    gui._store_brightness(35)

    assert config_writes == [("lightbar", 35, "lightbar_brightness")]
    assert profile_updates == [("lightbar", {"enabled": True, "brightness": 35})]


def test_secondary_uniform_color_zero_brightness_preserves_profile_restore_value(monkeypatch) -> None:
    from keyrgb.core.secondary_device_routes import BRIGHTNESS_POLICY_INDEPENDENT

    profile_updates: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "keyrgb.gui.windows._uniform_color_state.profiles.update_secondary_lighting_area",
        lambda state_key, updates: profile_updates.append((state_key, dict(updates))),
    )
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)
    gui.config = SimpleNamespace(set_secondary_device_brightness=lambda *_args, **_kwargs: None)
    gui._target_is_secondary = True
    gui._secondary_route = SimpleNamespace(
        brightness_policy=BRIGHTNESS_POLICY_INDEPENDENT,
        state_key="lightbar",
        config_brightness_attr="lightbar_brightness",
    )

    gui._store_brightness(0)

    assert profile_updates == [("lightbar", {"enabled": False})]
