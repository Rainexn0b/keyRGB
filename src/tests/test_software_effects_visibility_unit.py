from __future__ import annotations


class _StopEvent:
    def __init__(self) -> None:
        self._set = False

    def is_set(self) -> bool:
        return self._set

    def set(self) -> None:
        self._set = True

    def wait(self, _dt: float) -> None:
        # Tests must not sleep.
        return


def test_strobe_off_frame_not_full_black_when_brightness_nonzero(monkeypatch) -> None:
    from src.core.effects.software import effects as sw

    rendered: list[dict] = []

    def _render(engine, *, color_map):
        rendered.append(dict(color_map))
        engine.running = False

    monkeypatch.setattr(sw, "render", _render)

    class E:
        def __init__(self) -> None:
            self.running = True
            self.stop_event = _StopEvent()
            self.brightness = 25
            self.speed = 4
            self.current_color = (255, 0, 0)
            self.per_key_colors = None

    sw.run_strobe(E())

    assert rendered, "Expected at least one rendered frame"
    first = rendered[0]
    assert any(rgb != (0, 0, 0) for rgb in first.values()), "Strobe should not write a full-black frame"


def test_chase_visible_even_when_current_color_black(monkeypatch) -> None:
    from src.core.effects.software import effects as sw

    rendered: list[dict] = []

    def _render(engine, *, color_map):
        rendered.append(dict(color_map))
        engine.running = False

    monkeypatch.setattr(sw, "render", _render)

    class _KB:
        def set_key_colors(self, *_a, **_k):
            raise AssertionError("Should not be called in this test")

    class E:
        def __init__(self) -> None:
            self.running = True
            self.stop_event = _StopEvent()
            self.brightness = 25
            self.speed = 4
            self.current_color = (0, 0, 0)
            self.per_key_colors = None
            self.kb = _KB()

    sw.run_chase(E())

    assert rendered, "Expected at least one rendered frame"
    first = rendered[0]
    assert any(rgb != (0, 0, 0) for rgb in first.values()), "Chase should be visible even with black current_color"
