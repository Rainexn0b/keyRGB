from __future__ import annotations

import builtins
from pathlib import Path
from unittest.mock import MagicMock


def test_load_tray_dependencies_primary_import_succeeds() -> None:
    from src.tray.integrations.dependencies import load_tray_dependencies

    EffectsEngine, Config, PowerManager = load_tray_dependencies()

    assert EffectsEngine.__name__ == "EffectsEngine"
    assert Config.__name__ == "Config"
    assert PowerManager.__name__ == "PowerManager"


def test_load_tray_dependencies_falls_back_to_repo_root_on_importerror(
    monkeypatch,
) -> None:
    import src.tray.integrations.dependencies as deps

    ensure = MagicMock()
    monkeypatch.setattr(deps, "ensure_repo_root_on_sys_path", ensure)

    orig_import = builtins.__import__
    state = {"raised": False}

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        # Force the first attempt to fail, then allow fallback import to proceed.
        if name == "src.core.effects.engine" and not state["raised"]:
            state["raised"] = True
            raise ImportError("forced")
        return orig_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    EffectsEngine, Config, PowerManager = deps.load_tray_dependencies()

    assert ensure.call_count == 1
    (arg,), _kwargs = ensure.call_args
    assert isinstance(arg, Path)
    assert str(arg) == str(Path(deps.__file__))

    assert EffectsEngine.__name__ == "EffectsEngine"
    assert Config.__name__ == "Config"
    assert PowerManager.__name__ == "PowerManager"
