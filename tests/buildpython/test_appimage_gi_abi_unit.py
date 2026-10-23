"""Reject system CPython bindings that cannot run in the bundled interpreter."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from buildpython.steps.appimage import pygobject_bundle


@pytest.fixture
def binding_manifest(tmp_path, monkeypatch):
    site = tmp_path / "host-site"
    suffix = ".cpython-311-x86_64-linux-gnu.so"
    manifest = {"extension_suffix": suffix}
    for name in ("gi", "cairo"):
        source = site / name
        source.mkdir(parents=True)
        extension = source / f"_{name}{suffix}"
        extension.write_bytes(b"native-extension")
        manifest[name] = str(source)
        manifest[f"{name}_extension"] = str(extension)
    monkeypatch.setattr(
        pygobject_bundle.subprocess,
        "run",
        lambda *_a, **_kw: SimpleNamespace(returncode=0, stdout=json.dumps(manifest)),
    )
    return manifest


@pytest.mark.parametrize("name", ["gi", "cairo"])
def test_mismatched_native_binding_is_rejected_before_replacing_either_package(tmp_path, binding_manifest, name):
    old_extension = Path(binding_manifest[f"{name}_extension"])
    wrong_extension = old_extension.with_name(f"_{name}.cpython-310-x86_64-linux-gnu.so")
    old_extension.rename(wrong_extension)
    binding_manifest[f"{name}_extension"] = str(wrong_extension)
    target = tmp_path / "target"
    (target / "gi").mkdir(parents=True)
    sentinel = target / "gi/sentinel"
    sentinel.write_text("keep", encoding="utf-8")
    with pytest.raises(SystemExit, match=f"{name} bindings do not match"):
        pygobject_bundle.bundle_pygobject(appdir=tmp_path / "AppDir", site_packages=target)
    assert sentinel.read_text(encoding="utf-8") == "keep"
    assert not (target / "cairo").exists()


def test_probe_import_failure_never_falls_back_to_distro_bindings(tmp_path, monkeypatch):
    monkeypatch.setattr(
        pygobject_bundle.subprocess,
        "run",
        lambda *_a, **_kw: SimpleNamespace(returncode=1, stderr="No module named gi._gi"),
    )
    with pytest.raises(SystemExit, match="working GI/Cairo bindings.*No module named"):
        pygobject_bundle.bundle_pygobject(appdir=tmp_path, site_packages=tmp_path / "site")


@pytest.mark.parametrize("payload", ["broken JSON", "[]", "{}", '{"extension_suffix": ""}'])
def test_invalid_binding_manifest_fails_closed(tmp_path, monkeypatch, payload):
    monkeypatch.setattr(
        pygobject_bundle.subprocess,
        "run",
        lambda *_a, **_kw: SimpleNamespace(returncode=0, stdout=payload),
    )
    with pytest.raises(SystemExit, match="Invalid AppImage GI/Cairo"):
        pygobject_bundle.bundle_pygobject(appdir=tmp_path, site_packages=tmp_path / "site")


def test_missing_typelibs_fail_packaging(tmp_path, binding_manifest, monkeypatch):
    missing = tmp_path / "missing-typelibs"
    # Preserve manifest paths; substitute only system typelib locations.
    monkeypatch.setattr(
        pygobject_bundle, "Path", lambda value: missing if str(value).startswith("/usr/lib") else Path(value)
    )
    with pytest.raises(SystemExit, match="requires GI typelibs"):
        pygobject_bundle.bundle_pygobject(appdir=tmp_path / "AppDir", site_packages=tmp_path / "target")


def test_manual_release_build_cannot_publish_or_hide_missing_assets():
    workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/release.yml").read_text(encoding="utf-8")
    publish = workflow.split("- name: Upload AppImage to GitHub Release", 1)[1].split("- name:", 1)[0]
    assert "if: github.event_name == 'push'" in publish
    assert "workflow_dispatch:" in workflow
    assert "if-no-files-found: error" in workflow
    assert "pycairo==1.25.1 PyGObject==3.50.2" in workflow
    assert "--no-binary=pycairo,PyGObject" in workflow
