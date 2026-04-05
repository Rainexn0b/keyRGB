from __future__ import annotations

from dataclasses import dataclass


BUILT_IN_PROFILE_ID_PREFIX = "".join(("_", "_", "legacy", "_"))


@dataclass(frozen=True)
class TccProfile:
    id: str
    name: str
    description: str = ""


def is_builtin_profile_id(profile_id: object) -> bool:
    return isinstance(profile_id, str) and profile_id.startswith(BUILT_IN_PROFILE_ID_PREFIX)


class TccProfileWriteError(RuntimeError):
    pass
