from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_json_atomic(path: Path, payload: Any, *, indent: int = 2, sort_keys: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=indent, sort_keys=sort_keys), encoding="utf-8")
    tmp.replace(path)
