from __future__ import annotations

from keyrgb.gui.settings.panels import _wrap_sync


class _FakeWidget:
    def __init__(self, *, width: int = 0) -> None:
        self.width = width
        self.options: dict[str, object] = {}
        self.bind_calls: list[tuple[str, object]] = []
        self.after_calls: list[tuple[int, object]] = []

    def configure(self, **kwargs) -> None:
        self.options.update(kwargs)

    def bind(self, sequence: str, callback) -> None:
        self.bind_calls.append((sequence, callback))

    def after(self, delay_ms: int, callback) -> None:
        self.after_calls.append((delay_ms, callback))

    def winfo_width(self) -> int:
        return self.width


def test_bind_wraplength_sync_rewraps_labels_to_parent_width() -> None:
    parent = _FakeWidget(width=412)
    label = _FakeWidget()

    _wrap_sync.bind_wraplength_sync(parent, [label])

    assert parent.bind_calls[0][0] == "<Configure>"
    assert parent.after_calls[0][0] == 0

    parent.after_calls[0][1]()
    assert label.options["wraplength"] == 388

    parent.width = 300
    parent.bind_calls[0][1]()
    assert label.options["wraplength"] == 276


def test_bind_wraplength_sync_respects_min_wrap_and_margin() -> None:
    parent = _FakeWidget(width=200)
    label = _FakeWidget()

    _wrap_sync.bind_wraplength_sync(parent, [label], min_wrap=260, margin=48)
    parent.after_calls[0][1]()

    assert label.options["wraplength"] == 260


def test_bind_wraplength_sync_ignores_unsized_and_fake_parents() -> None:
    parent = _FakeWidget(width=1)
    label = _FakeWidget()

    _wrap_sync.bind_wraplength_sync(parent, [label])
    parent.after_calls[0][1]()
    assert label.options == {}

    # Plain objects without Tk methods must not raise.
    _wrap_sync.bind_wraplength_sync(object(), [label])
