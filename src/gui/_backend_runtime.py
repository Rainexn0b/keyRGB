from __future__ import annotations

from src.core.backends.base import KeyboardBackend
from src.core.backends.registry import select_backend as _select_backend


def select_backend(*, requested: str | None = None) -> KeyboardBackend | None:
    return _select_backend(requested=requested)
