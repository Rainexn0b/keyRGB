from __future__ import annotations

from typing import Iterable


def bool_prop(key: str, *, default: bool) -> property:
    def _get(self) -> bool:
        try:
            return bool(self._settings.get(key, default))
        except Exception:
            return bool(default)

    def _set(self, value: bool) -> None:
        self._settings[key] = bool(value)
        self._save()

    return property(_get, _set)


def int_prop(key: str, *, default: int, min_v: int | None = None, max_v: int | None = None) -> property:
    def _get(self) -> int:
        try:
            v = int(self._settings.get(key, default) or 0)
        except Exception:
            v = int(default)
        if min_v is not None:
            v = max(int(min_v), v)
        if max_v is not None:
            v = min(int(max_v), v)
        return v

    def _set(self, value: int) -> None:
        try:
            v = int(value)
        except Exception:
            v = int(default)
        if min_v is not None:
            v = max(int(min_v), v)
        if max_v is not None:
            v = min(int(max_v), v)
        self._settings[key] = v
        self._save()

    return property(_get, _set)


def enum_prop(key: str, *, default: str, allowed: Iterable[str]) -> property:
    allowed_set = {str(x).strip().lower() for x in allowed}
    default_norm = str(default or "").strip().lower()
    if default_norm not in allowed_set:
        default_norm = next(iter(allowed_set)) if allowed_set else ""

    def _get(self) -> str:
        v = str(self._settings.get(key, default_norm) or default_norm).strip().lower()
        return v if v in allowed_set else default_norm

    def _set(self, value: str) -> None:
        v = str(value or default_norm).strip().lower()
        self._settings[key] = v if v in allowed_set else default_norm
        self._save()

    return property(_get, _set)


def optional_brightness_prop(key: str) -> property:
    def _get(self) -> int | None:
        v = self._settings.get(key, None)
        if v is None:
            return None
        try:
            return self._normalize_brightness_value(v)
        except Exception:
            return None

    def _set(self, value: int | None) -> None:
        if value is None:
            self._settings[key] = None
        else:
            self._settings[key] = self._normalize_brightness_value(value)
        self._save()

    return property(_get, _set)
