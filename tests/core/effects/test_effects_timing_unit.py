from __future__ import annotations


class TestGetInterval:
    def test_speed_0(self):
        from src.core.effects.timing import get_interval

        # speed=0 → speed_factor = max(1, min(11, 11-0)) = 11
        result = get_interval(100, speed=0)
        assert abs(result - (100 * 11 * 0.8) / 1000.0) < 1e-9

    def test_speed_5(self):
        from src.core.effects.timing import get_interval

        # speed=5 → speed_factor = max(1, min(11, 11-5)) = 6
        result = get_interval(100, speed=5)
        assert abs(result - (100 * 6 * 0.8) / 1000.0) < 1e-9

    def test_speed_10(self):
        from src.core.effects.timing import get_interval

        # speed=10 → speed_factor = max(1, min(11, 11-10)) = 1
        result = get_interval(100, speed=10)
        assert abs(result - (100 * 1 * 0.8) / 1000.0) < 1e-9

    def test_speed_below_0_clamps(self):
        from src.core.effects.timing import get_interval

        # speed=-5 → 11-(-5)=16 → clamped to 11
        result_neg = get_interval(100, speed=-5)
        result_zero = get_interval(100, speed=0)
        assert abs(result_neg - result_zero) < 1e-9

    def test_speed_above_10_clamps(self):
        from src.core.effects.timing import get_interval

        # speed=20 → 11-20=-9 → clamped to 1 (same as speed=10)
        result_high = get_interval(100, speed=20)
        result_ten = get_interval(100, speed=10)
        assert abs(result_high - result_ten) < 1e-9

    def test_custom_slowdown(self):
        from src.core.effects.timing import get_interval

        result = get_interval(100, speed=5, slowdown=1.0)
        assert abs(result - (100 * 6 * 1.0) / 1000.0) < 1e-9


class TestClampedInterval:
    def test_returns_min_when_interval_below(self):
        from src.core.effects.timing import clamped_interval

        # speed=10 → interval = (100*1*0.8)/1000 = 0.08; min_s=0.5 → clamped to 0.5
        result = clamped_interval(100, speed=10, min_s=0.5)
        assert abs(result - 0.5) < 1e-9

    def test_returns_interval_when_above_min(self):
        from src.core.effects.timing import clamped_interval

        # speed=0 → interval = (100*11*0.8)/1000 = 0.88; min_s=0.1 → returns 0.88
        result = clamped_interval(100, speed=0, min_s=0.1)
        assert abs(result - (100 * 11 * 0.8) / 1000.0) < 1e-9


class TestBrightnessFactor:
    def test_zero(self):
        from src.core.effects.timing import brightness_factor

        assert brightness_factor(0) == 0.0

    def test_half(self):
        from src.core.effects.timing import brightness_factor

        assert abs(brightness_factor(25) - 0.5) < 1e-9

    def test_full(self):
        from src.core.effects.timing import brightness_factor

        assert abs(brightness_factor(50) - 1.0) < 1e-9
