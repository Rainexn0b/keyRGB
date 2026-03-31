from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import src.gui.settings.panels.version_panel as version_panel


class _FakeWidget:
    def __init__(self, parent=None, **kwargs):
        self.parent = parent
        self.options = dict(kwargs)
        self.configure_calls = []
        self.pack_calls = []
        self.grid_calls = []

    def configure(self, **kwargs):
        self.configure_calls.append(dict(kwargs))
        self.options.update(kwargs)

    def pack(self, **kwargs):
        self.pack_calls.append(dict(kwargs))

    def grid(self, **kwargs):
        self.grid_calls.append(dict(kwargs))


class _FakeRoot:
    def __init__(self):
        self.clipboard_cleared = 0
        self.clipboard_values = []
        self.after_calls = []

    def clipboard_clear(self):
        self.clipboard_cleared += 1

    def clipboard_append(self, value):
        self.clipboard_values.append(value)

    def after(self, delay_ms, callback):
        self.after_calls.append((delay_ms, callback))


def _install_fake_ttk(monkeypatch: pytest.MonkeyPatch):
    registry = {"frames": [], "labels": [], "buttons": []}

    class FakeFrame(_FakeWidget):
        def __init__(self, parent=None, **kwargs):
            super().__init__(parent, **kwargs)
            registry["frames"].append(self)

    class FakeLabel(_FakeWidget):
        def __init__(self, parent=None, **kwargs):
            super().__init__(parent, **kwargs)
            registry["labels"].append(self)

    class FakeButton(_FakeWidget):
        def __init__(self, parent=None, **kwargs):
            super().__init__(parent, **kwargs)
            registry["buttons"].append(self)

    monkeypatch.setattr(
        version_panel,
        "ttk",
        SimpleNamespace(Frame=FakeFrame, Label=FakeLabel, Button=FakeButton),
    )
    return registry


def _make_panel(*, installed_version: str = "v1.0.0") -> version_panel.VersionPanel:
    panel = version_panel.VersionPanel.__new__(version_panel.VersionPanel)
    panel._installed_version = installed_version
    panel.lbl_latest_stable_version = _FakeWidget()
    panel.lbl_latest_prerelease_version = _FakeWidget()
    panel.lbl_update_status = _FakeWidget()
    return panel


def _install_urlopen(monkeypatch: pytest.MonkeyPatch, payload=None, *, exc: Exception | None = None) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            if isinstance(payload, bytes):
                return payload
            return json.dumps(payload).encode("utf-8")

    def fake_urlopen(_request, timeout=0.0):
        assert timeout == 5.0
        if exc is not None:
            raise exc
        return FakeResponse()

    monkeypatch.setattr(version_panel, "urlopen", fake_urlopen)


def test_version_panel_init_wires_widgets_and_starts_check(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _install_fake_ttk(monkeypatch)
    started = []

    monkeypatch.setattr(
        version_panel.VersionPanel,
        "_installed_version_text",
        lambda self: "v1.2.3 (dev)",
    )
    monkeypatch.setattr(
        version_panel.VersionPanel,
        "start_latest_version_check",
        lambda self: started.append(self),
    )

    root = _FakeRoot()
    status_label = _FakeWidget(text="")
    panel = version_panel.VersionPanel(object(), root=root, get_status_label=lambda: status_label)

    label_texts = [label.options.get("text") for label in registry["labels"]]

    assert started == [panel]
    assert label_texts[:3] == [
        "Version",
        "Shows the KeyRGB version you're running and checks GitHub to see\n"
        "whether you're on the latest stable release (and also shows the latest pre-release).",
        "Installed",
    ]
    assert "Latest (stable)" in label_texts
    assert "Latest (pre-release)" in label_texts
    assert panel.lbl_installed_version.configure_calls[0] == {"text": "v1.2.3 (dev)"}
    assert panel.lbl_installed_version.options["text"] == "v1.2.3 (dev)"
    assert panel.lbl_latest_stable_version.options["text"] == "Checking…"
    assert panel.lbl_latest_prerelease_version.options["text"] == "Checking…"
    assert panel.lbl_update_status.options["text"] == ""
    assert panel.btn_open_repo.options["text"] == "Open repo"
    assert panel.btn_open_repo.options["command"].__self__ is panel
    assert panel.btn_open_repo.pack_calls == [{"side": "left"}]


def test_installed_version_text_prefers_repo_version_and_marks_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        version_panel.VersionPanel,
        "_repo_version_text",
        staticmethod(lambda: "release 1.2.3"),
    )

    def fail_metadata(_name: str) -> str:
        raise AssertionError("metadata.version should not be used when repo version exists")

    monkeypatch.setattr(version_panel.metadata, "version", fail_metadata)

    panel = version_panel.VersionPanel.__new__(version_panel.VersionPanel)

    assert panel._installed_version_text() == "v1.2.3 (dev)"


def test_installed_version_text_falls_back_to_metadata_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(version_panel.VersionPanel, "_repo_version_text", staticmethod(lambda: None))
    monkeypatch.setattr(version_panel.metadata, "version", lambda _name: "v2.0.1rc2")

    panel = version_panel.VersionPanel.__new__(version_panel.VersionPanel)

    assert panel._installed_version_text() == "v2.0.1rc2"


def test_installed_version_text_returns_unknown_on_metadata_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(version_panel.VersionPanel, "_repo_version_text", staticmethod(lambda: None))
    monkeypatch.setattr(
        version_panel.metadata,
        "version",
        lambda _name: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    panel = version_panel.VersionPanel.__new__(version_panel.VersionPanel)

    assert panel._installed_version_text() == "unknown"


def test_repo_version_text_reads_project_section_and_ignores_other_sections(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "\n".join(
            [
                "[tool.poetry]",
                'version = "9.9.9"',
                "",
                "# ignored comment",
                "[project]",
                'name = "keyrgb"',
                'version = "1.4.2" # trailing comment',
                "",
                "[tool.ruff]",
                'version = "0.0.1"',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(version_panel, "repo_root_from", lambda _path: tmp_path)

    assert version_panel.VersionPanel._repo_version_text() == "1.4.2"


def test_repo_version_text_returns_none_for_missing_file_and_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(version_panel, "repo_root_from", lambda _path: tmp_path)
    assert version_panel.VersionPanel._repo_version_text() is None

    monkeypatch.setattr(
        version_panel,
        "repo_root_from",
        lambda _path: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    assert version_panel.VersionPanel._repo_version_text() is None


def test_fetch_latest_github_versions_picks_first_stable_and_prerelease(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_urlopen(
        monkeypatch,
        [
            {"draft": True, "tag_name": "v9.9.9"},
            {"prerelease": True, "tag_name": " v2.0.0rc1 "},
            {"prerelease": False, "tag_name": " 1.9.0 "},
            {"prerelease": False, "tag_name": "1.8.0"},
        ],
    )

    panel = version_panel.VersionPanel.__new__(version_panel.VersionPanel)

    assert panel._fetch_latest_github_versions() == ("1.9.0", "v2.0.0rc1")


@pytest.mark.parametrize(
    ("payload", "exc"),
    [
        ({"tag_name": "v1.0.0"}, None),
        (b"{not json", None),
        (None, OSError("network down")),
    ],
)
def test_fetch_latest_github_versions_returns_unknown_for_bad_responses(
    monkeypatch: pytest.MonkeyPatch,
    payload,
    exc: Exception | None,
) -> None:
    _install_urlopen(monkeypatch, payload, exc=exc)

    panel = version_panel.VersionPanel.__new__(version_panel.VersionPanel)

    assert panel._fetch_latest_github_versions() == (None, None)


def test_apply_latest_version_result_marks_unknown_when_github_check_fails() -> None:
    panel = _make_panel()

    panel._apply_latest_version_result(None, None)

    assert panel.lbl_latest_stable_version.options["text"] == "Unknown"
    assert panel.lbl_latest_prerelease_version.options["text"] == "Unknown"
    assert panel.lbl_update_status.options["text"] == "Couldn't check GitHub"


def test_apply_latest_version_result_handles_uncomparable_versions_and_missing_prerelease(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    panel = _make_panel(installed_version="v1.0.0")
    monkeypatch.setattr(version_panel, "compare_versions", lambda _installed, _stable: None)

    panel._apply_latest_version_result("1.2.3", None)

    assert panel.lbl_latest_stable_version.options["text"] == "v1.2.3"
    assert panel.lbl_latest_prerelease_version.options["text"] == "None"
    assert panel.lbl_update_status.options["text"] == "Couldn't compare versions"


@pytest.mark.parametrize(
    ("cmp_result", "expected_status"),
    [
        (0, "✓ You are on the latest stable version"),
        (-1, "Update available (stable): v1.2.3"),
        (1, "You are ahead of the latest stable release"),
    ],
)
def test_apply_latest_version_result_covers_compare_branches_and_prerelease_display(
    monkeypatch: pytest.MonkeyPatch,
    cmp_result: int,
    expected_status: str,
) -> None:
    panel = _make_panel(installed_version="v1.0.0")
    monkeypatch.setattr(version_panel, "compare_versions", lambda _installed, _stable: cmp_result)

    panel._apply_latest_version_result("1.2.3", "1.3.0rc1")

    assert panel.lbl_latest_stable_version.options["text"] == "v1.2.3"
    assert panel.lbl_latest_prerelease_version.options["text"] == "v1.3.0rc1"
    assert panel.lbl_update_status.options["text"] == expected_status


def test_open_repo_sets_status_and_clears_it_after_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(version_panel.webbrowser, "open", lambda url, new: url.endswith("keyRGB") and new == 2)

    root = _FakeRoot()
    status = _FakeWidget(text="")
    panel = version_panel.VersionPanel.__new__(version_panel.VersionPanel)
    panel._root = root
    panel._get_status_label = lambda: status

    panel._open_repo()

    assert status.options["text"] == "Opened repo"
    assert root.clipboard_cleared == 0
    assert root.clipboard_values == []
    assert len(root.after_calls) == 1
    delay_ms, callback = root.after_calls[0]
    assert delay_ms == 2000

    callback()
    assert status.options["text"] == ""


def test_open_repo_copies_url_when_browser_open_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(version_panel.webbrowser, "open", lambda _url, new: False)

    root = _FakeRoot()
    status = _FakeWidget(text="")
    panel = version_panel.VersionPanel.__new__(version_panel.VersionPanel)
    panel._root = root
    panel._get_status_label = lambda: status

    panel._open_repo()

    assert root.clipboard_cleared == 1
    assert root.clipboard_values == ["https://github.com/Rainexn0b/keyRGB"]
    assert status.options["text"] == "Couldn't open browser (URL copied)"
    assert root.after_calls[0][0] == 2000


def test_open_repo_tolerates_status_label_lookup_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        version_panel.webbrowser,
        "open",
        lambda _url, new: (_ for _ in ()).throw(RuntimeError("browser failed")),
    )

    root = _FakeRoot()
    panel = version_panel.VersionPanel.__new__(version_panel.VersionPanel)
    panel._root = root
    panel._get_status_label = lambda: (_ for _ in ()).throw(RuntimeError("no label"))

    panel._open_repo()

    assert root.clipboard_cleared == 1
    assert root.clipboard_values == ["https://github.com/Rainexn0b/keyRGB"]
    assert root.after_calls == []