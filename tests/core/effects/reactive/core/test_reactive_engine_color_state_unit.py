from __future__ import annotations


class TestGetEngineManualReactiveColor:
    def test_returns_none_when_flag_false(self):
        from src.core.effects.reactive._engine_color_state import get_engine_manual_reactive_color

        class Engine:
            reactive_use_manual_color = False
            reactive_color = (100, 150, 200)

        assert get_engine_manual_reactive_color(Engine()) is None

    def test_returns_none_when_flag_missing(self):
        from src.core.effects.reactive._engine_color_state import get_engine_manual_reactive_color

        assert get_engine_manual_reactive_color(object()) is None

    def test_returns_none_when_color_is_none(self):
        from src.core.effects.reactive._engine_color_state import get_engine_manual_reactive_color

        class Engine:
            reactive_use_manual_color = True
            reactive_color = None

        assert get_engine_manual_reactive_color(Engine()) is None

    def test_returns_tuple_when_valid_color(self):
        from src.core.effects.reactive._engine_color_state import get_engine_manual_reactive_color

        class Engine:
            reactive_use_manual_color = True
            reactive_color = (100, 150, 200)

        result = get_engine_manual_reactive_color(Engine())
        assert result == (100, 150, 200)

    def test_returns_none_on_index_error(self):
        from src.core.effects.reactive._engine_color_state import get_engine_manual_reactive_color

        class Engine:
            reactive_use_manual_color = True
            reactive_color = ()  # too short → IndexError

        assert get_engine_manual_reactive_color(Engine()) is None

    def test_returns_none_on_type_error(self):
        from src.core.effects.reactive._engine_color_state import get_engine_manual_reactive_color

        class Engine:
            reactive_use_manual_color = True
            reactive_color = ("x", "y", "z")  # int("x") raises ValueError

        assert get_engine_manual_reactive_color(Engine()) is None


class TestGetEngineReactiveColor:
    def test_returns_manual_when_available(self):
        from src.core.effects.reactive._engine_color_state import get_engine_reactive_color

        class Engine:
            reactive_use_manual_color = True
            reactive_color = (10, 20, 30)

        assert get_engine_reactive_color(Engine()) == (10, 20, 30)

    def test_returns_current_color_when_no_manual(self):
        from src.core.effects.reactive._engine_color_state import get_engine_reactive_color

        class Engine:
            reactive_use_manual_color = False
            current_color = (50, 60, 70)

        assert get_engine_reactive_color(Engine()) == (50, 60, 70)

    def test_returns_white_when_no_manual_no_current_color(self):
        from src.core.effects.reactive._engine_color_state import get_engine_reactive_color

        assert get_engine_reactive_color(object()) == (255, 255, 255)
