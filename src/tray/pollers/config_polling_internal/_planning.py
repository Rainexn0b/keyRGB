from __future__ import annotations

from typing import TYPE_CHECKING

from ._apply_plan import classify_config_apply_plan
from ._apply_plan import ConfigApplyPlan


if TYPE_CHECKING:
    from .core import ConfigApplyState


def classify_apply_from_config(*, configured_effect: str, current: ConfigApplyState) -> ConfigApplyPlan:
    """Classify how a config snapshot should be applied.

    This seam stays pure so coordinator code can remain thin and testable.
    """

    return classify_config_apply_plan(configured_effect=configured_effect, current=current)
