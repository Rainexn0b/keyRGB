from __future__ import annotations

import os

PER_KEY_MODE_POLICY_INIT_ONCE = "init_once"
PER_KEY_MODE_POLICY_REASSERT_EVERY_FRAME = "reassert_every_frame"
PER_KEY_MODE_POLICY_ENV = "KEYRGB_PER_KEY_MODE_POLICY"


def normalize_per_key_mode_policy(policy: object) -> str:
    value = str(policy or PER_KEY_MODE_POLICY_INIT_ONCE).strip().lower()
    if value == PER_KEY_MODE_POLICY_REASSERT_EVERY_FRAME:
        return PER_KEY_MODE_POLICY_REASSERT_EVERY_FRAME
    return PER_KEY_MODE_POLICY_INIT_ONCE


def per_key_mode_policy(kb: object) -> str:
    override = str(os.environ.get(PER_KEY_MODE_POLICY_ENV, "")).strip()
    if override:
        return normalize_per_key_mode_policy(override)
    return normalize_per_key_mode_policy(getattr(kb, "keyrgb_per_key_mode_policy", None))


def per_key_mode_requires_frame_reassert(kb: object) -> bool:
    return per_key_mode_policy(kb) == PER_KEY_MODE_POLICY_REASSERT_EVERY_FRAME
