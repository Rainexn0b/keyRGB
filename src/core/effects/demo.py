from __future__ import annotations

import time
from typing import Protocol


class _EngineFactory(Protocol):
    def __call__(self) -> object: ...


def run_demo(engine_factory: _EngineFactory) -> None:
    """Run the legacy effects-engine test mode.

    This was previously embedded in `src.core.effects.engine` under `__main__`.
    """

    print("KeyRGB Effects Test Mode")
    print("Press Ctrl+C to exit")

    engine = engine_factory()

    try:
        print("\nTesting hardware effects...")
        for effect in ["rainbow", "breathing", "wave"]:
            print(f"  {effect}")
            engine.start_effect(effect, speed=5, brightness=25)
            time.sleep(4)

        print("\nTesting software effects...")
        for effect in ["static", "pulse", "fire"]:
            print(f"  {effect}")
            engine.start_effect(effect, speed=5, brightness=25, color=(255, 0, 0))
            time.sleep(4)

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        engine.stop()
        engine.turn_off()
        print("Done!")


def main() -> None:
    from src.core.effects.engine import EffectsEngine

    run_demo(EffectsEngine)
