"""Unit tests for safe attribute access helpers."""

from __future__ import annotations

from types import SimpleNamespace

from src.core.utils.safe_attrs import (
    safe_int_attr,
    safe_bool_attr,
    safe_float_attr,
    safe_str_attr,
    safe_optional_int_attr,
)


class TestSafeIntAttr:
    def test_returns_value_when_present(self) -> None:
        obj = SimpleNamespace(brightness=42)
        assert safe_int_attr(obj, "brightness") == 42

    def test_returns_default_when_missing(self) -> None:
        obj = SimpleNamespace()
        assert safe_int_attr(obj, "brightness", default=25) == 25

    def test_returns_default_when_none(self) -> None:
        obj = SimpleNamespace(brightness=None)
        assert safe_int_attr(obj, "brightness", default=10) == 10

    def test_converts_string_to_int(self) -> None:
        obj = SimpleNamespace(brightness="50")
        assert safe_int_attr(obj, "brightness") == 50

    def test_converts_float_string_to_int(self) -> None:
        obj = SimpleNamespace(brightness="25.9")
        assert safe_int_attr(obj, "brightness") == 25

    def test_clamps_to_min(self) -> None:
        obj = SimpleNamespace(brightness=-10)
        assert safe_int_attr(obj, "brightness", min_v=0) == 0

    def test_clamps_to_max(self) -> None:
        obj = SimpleNamespace(brightness=100)
        assert safe_int_attr(obj, "brightness", max_v=50) == 50

    def test_clamps_to_range(self) -> None:
        obj = SimpleNamespace(brightness=5)
        assert safe_int_attr(obj, "brightness", min_v=10, max_v=50) == 10


class TestSafeBoolAttr:
    def test_returns_true_when_truthy(self) -> None:
        obj = SimpleNamespace(enabled=True)
        assert safe_bool_attr(obj, "enabled") is True

    def test_returns_false_when_falsy(self) -> None:
        obj = SimpleNamespace(enabled=False)
        assert safe_bool_attr(obj, "enabled") is False

    def test_returns_default_when_missing(self) -> None:
        obj = SimpleNamespace()
        assert safe_bool_attr(obj, "enabled", default=True) is True

    def test_returns_default_when_none(self) -> None:
        obj = SimpleNamespace(enabled=None)
        assert safe_bool_attr(obj, "enabled", default=True) is True

    def test_coerces_truthy_values(self) -> None:
        obj = SimpleNamespace(enabled=1)
        assert safe_bool_attr(obj, "enabled") is True


class TestSafeFloatAttr:
    def test_returns_value_when_present(self) -> None:
        obj = SimpleNamespace(speed=3.5)
        assert safe_float_attr(obj, "speed") == 3.5

    def test_returns_default_when_missing(self) -> None:
        obj = SimpleNamespace()
        assert safe_float_attr(obj, "speed", default=1.0) == 1.0

    def test_clamps_to_range(self) -> None:
        obj = SimpleNamespace(speed=15.0)
        assert safe_float_attr(obj, "speed", max_v=10.0) == 10.0


class TestSafeStrAttr:
    def test_returns_value_when_present(self) -> None:
        obj = SimpleNamespace(effect="rainbow")
        assert safe_str_attr(obj, "effect") == "rainbow"

    def test_returns_default_when_missing(self) -> None:
        obj = SimpleNamespace()
        assert safe_str_attr(obj, "effect", default="none") == "none"

    def test_converts_non_string_to_string(self) -> None:
        obj = SimpleNamespace(effect=42)
        assert safe_str_attr(obj, "effect") == "42"


class TestSafeOptionalIntAttr:
    def test_returns_value_when_present(self) -> None:
        obj = SimpleNamespace(override=30)
        assert safe_optional_int_attr(obj, "override") == 30

    def test_returns_none_when_missing(self) -> None:
        obj = SimpleNamespace()
        assert safe_optional_int_attr(obj, "override") is None

    def test_returns_none_when_none(self) -> None:
        obj = SimpleNamespace(override=None)
        assert safe_optional_int_attr(obj, "override") is None

    def test_clamps_when_present(self) -> None:
        obj = SimpleNamespace(override=100)
        assert safe_optional_int_attr(obj, "override", max_v=50) == 50


class TestEdgeCases:
    def test_handles_getattr_exception(self) -> None:
        class BadObj:
            def __getattr__(self, _name):
                raise RuntimeError("boom")

        obj = BadObj()
        assert safe_int_attr(obj, "anything", default=99) == 99

    def test_handles_zero_correctly(self) -> None:
        # This is the key bug the old pattern had: `or 0` treats 0 as falsy
        obj = SimpleNamespace(brightness=0)
        assert safe_int_attr(obj, "brightness", default=25) == 0  # NOT 25!

    def test_handles_empty_string(self) -> None:
        obj = SimpleNamespace(value="")
        # Empty string is falsy but should fail conversion, giving default
        assert safe_int_attr(obj, "value", default=5) == 5
