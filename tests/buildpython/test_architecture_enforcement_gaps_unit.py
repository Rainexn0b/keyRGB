from __future__ import annotations

import pytest

from tests.buildpython._architecture_validation_helpers import scan_configured_rule


@pytest.mark.parametrize(
    "source",
    [
        "from keyrgb import tray\n",
        "import os, keyrgb.tray as runtime\n",
        "from ...tray import deck_pipeline\n",
        "from ... import gui\n",
        "if True: import keyrgb.gui\n",
    ],
)
@pytest.mark.parametrize("filename", ["module.py", "__init__.py"])
def test_core_layer_import_spellings_cannot_bypass_boundary(tmp_path, source, filename) -> None:
    result = scan_configured_rule(
        tmp_path, source, rule_id="core-layer-boundary", relative_path=f"keyrgb/core/example/{filename}"
    )
    assert len(result.findings) == 1


def test_import_boundaries_ignore_documentation_and_allow_core_imports(tmp_path) -> None:
    result = scan_configured_rule(
        tmp_path,
        '"""\nfrom keyrgb.tray import deck_pipeline\n"""\nfrom ..effects import engine\n',
        rule_id="core-layer-boundary",
        relative_path="keyrgb/core/example/module.py",
    )
    assert result.findings == ()


def test_relative_module_alias_cannot_bypass_live_observation_rule(tmp_path) -> None:
    result = scan_configured_rule(
        tmp_path,
        "from ...core.power import system as power\npower.get_status()\n",
        rule_id="tray-ui-no-live-observation",
        relative_path="keyrgb/tray/ui/menu.py",
    )
    assert [f.regex for f in result.findings] == ["call:keyrgb.core.power.system.get_status"]


@pytest.mark.parametrize(
    "source",
    [
        "from threading import Thread as Worker\nWorker(daemon=True, target=work)\n",
        "import threading as threads\nthreads.Thread(None, work)\n",
        "from threading import Timer as Later\nLater(1, work)\n",
        "from threading import Thread\nspawn = Thread\nspawn(target=work)\n",
    ],
)
def test_gui_worker_constructors_use_coordinator(tmp_path, source) -> None:
    result = scan_configured_rule(
        tmp_path, source, rule_id="gui-background-work-uses-tk-async", relative_path="keyrgb/gui/windows/uniform.py"
    )
    assert len(result.findings) == 1


def test_gui_worker_rule_respects_shadowed_import(tmp_path) -> None:
    result = scan_configured_rule(
        tmp_path,
        "from threading import Thread\ndef render(Thread):\n    Thread(target=work)\n",
        rule_id="gui-background-work-uses-tk-async",
        relative_path="keyrgb/gui/windows/uniform.py",
    )
    assert result.findings == ()


@pytest.mark.parametrize(
    "setup, call",
    [
        ("device = engine.kb", "device.set_color()"),
        ("write = engine.kb.set_color", "write()"),
        ('write = getattr(engine.kb, "set_color", None)', "write()"),
        ('device = getattr(engine, "kb")\nwrite = getattr(device, "set_color")', "write()"),
        ("write: object = engine.kb.set_color", "write()"),
        ("", 'getattr(engine.kb, "set_color")()'),
    ],
)
@pytest.mark.parametrize("locked", [True, False])
def test_primary_write_aliases_require_lock_at_invocation(tmp_path, setup, call, locked) -> None:
    source = setup + "\n" + (f"with engine.kb_lock:\n    {call}\n" if locked else f"{call}\n")
    result = scan_configured_rule(
        tmp_path,
        source,
        rule_id="primary-lighting-write-ownership",
        relative_path="keyrgb/core/effects/software/base.py",
    )
    assert len(result.findings) == (0 if locked else 1)


def test_primary_write_alias_cannot_bypass_owner_allowlist(tmp_path) -> None:
    result = scan_configured_rule(
        tmp_path,
        "write = tray.engine.kb.turn_off\nwith tray.engine.kb_lock:\n    write()\n",
        rule_id="primary-lighting-write-ownership",
        relative_path="keyrgb/tray/pollers/example.py",
    )
    assert len(result.findings) == 1
    assert "approved output-owner" in result.findings[0].message


@pytest.mark.parametrize(
    "source",
    [
        "write = engine.kb.set_color\nwrite = callback\nwrite()\n",
        "write = engine.kb.set_color\ndef later(write):\n    write()\n",
    ],
)
def test_primary_write_aliases_respect_rebinding_and_parameters(tmp_path, source) -> None:
    result = scan_configured_rule(
        tmp_path,
        source,
        rule_id="primary-lighting-write-ownership",
        relative_path="keyrgb/core/effects/software/base.py",
    )
    assert result.findings == ()


@pytest.mark.parametrize(
    "deferred",
    ["lambda: engine.kb.set_color()", "(engine.kb.set_color() for color in colors)"],
)
def test_deferred_writes_do_not_inherit_creation_lock(tmp_path, deferred) -> None:
    result = scan_configured_rule(
        tmp_path,
        f"with engine.kb_lock:\n    later = {deferred}\n",
        rule_id="primary-lighting-write-ownership",
        relative_path="keyrgb/core/effects/software/base.py",
    )
    assert len(result.findings) == 1


@pytest.mark.parametrize("suffix", ["device.py", "nested/device.py", "deep/nested/device.py"])
def test_recursive_corpus_exclusions_cover_every_depth(tmp_path, suffix) -> None:
    result = scan_configured_rule(
        tmp_path,
        "kb.set_color()\n",
        rule_id="primary-lighting-write-ownership",
        relative_path=f"keyrgb/core/backends/example/{suffix}",
    )
    assert result.findings == ()
