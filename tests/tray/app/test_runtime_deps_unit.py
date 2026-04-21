from types import ModuleType

from src.tray.app import _runtime_deps


def test_lazy_module_ref_imports_once_and_forwards_attributes(monkeypatch):
    calls: list[str] = []
    fake_module = ModuleType("fake.runtime.module")
    fake_module.answer = object()

    def fake_import(module_path: str) -> ModuleType:
        calls.append(module_path)
        return fake_module

    monkeypatch.setattr(_runtime_deps, "import_module", fake_import)

    lazy_ref = _runtime_deps.LazyModuleRef("fake.runtime.module")

    assert calls == []
    assert lazy_ref.answer is fake_module.answer
    assert calls == ["fake.runtime.module"]
    assert lazy_ref.answer is fake_module.answer
    assert calls == ["fake.runtime.module"]