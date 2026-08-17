from __future__ import annotations

import pytest

from src.core.effects.engine import EffectsEngine
from src.core.effects.engine_support._contracts import assert_engine_support_contract


def test_effects_engine_satisfies_shared_mixin_contract() -> None:
    engine = EffectsEngine()

    assert_engine_support_contract(engine)
    assert engine._permission_error_cb is None


def test_effects_engine_contract_fails_with_named_missing_dependency() -> None:
    engine = EffectsEngine()
    del engine._brightness_fade_lock

    with pytest.raises(TypeError, match="_brightness_fade_lock"):
        assert_engine_support_contract(engine)
