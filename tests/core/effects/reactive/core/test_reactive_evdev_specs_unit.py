from __future__ import annotations
import types


def _make_evdev() -> object:
    """Return a minimal evdev stub with an ecodes namespace."""
    ecodes = types.SimpleNamespace(
        KEY_A=30,
        KEY_B=48,
        KEY_C=46,
        KEY_D=32,
        KEY_E=18,
        KEY_F=33,
        KEY_G=34,
        KEY_H=35,
        KEY_I=23,
        KEY_J=36,
        KEY_K=37,
        KEY_L=38,
        KEY_M=50,
        KEY_N=49,
        KEY_O=24,
        KEY_P=25,
        KEY_Q=16,
        KEY_R=19,
        KEY_S=31,
        KEY_T=20,
        KEY_U=22,
        KEY_V=47,
        KEY_W=17,
        KEY_X=45,
        KEY_Y=21,
        KEY_Z=44,
        KEY_SPACE=57,
        KEY_ENTER=28,
        KEY_TAB=15,
        KEY_BACKSPACE=14,
        KEY_LEFTSHIFT=42,
        KEY_RIGHTSHIFT=54,
    )
    return types.SimpleNamespace(ecodes=ecodes)


class TestKeyboardLetterKeys:
    def test_returns_set_of_26_keys(self):
        from src.core.effects.reactive._evdev_specs import keyboard_letter_keys

        evdev = _make_evdev()
        result = keyboard_letter_keys(evdev)
        assert isinstance(result, set)
        assert len(result) == 26

    def test_contains_key_a_and_key_z(self):
        from src.core.effects.reactive._evdev_specs import keyboard_letter_keys

        evdev = _make_evdev()
        result = keyboard_letter_keys(evdev)
        assert 30 in result  # KEY_A
        assert 44 in result  # KEY_Z


class TestKeyboardControlKeys:
    def test_returns_set(self):
        from src.core.effects.reactive._evdev_specs import keyboard_control_keys

        evdev = _make_evdev()
        result = keyboard_control_keys(evdev)
        assert isinstance(result, set)
        assert len(result) > 0

    def test_contains_space_and_enter(self):
        from src.core.effects.reactive._evdev_specs import keyboard_control_keys

        evdev = _make_evdev()
        result = keyboard_control_keys(evdev)
        assert 57 in result  # KEY_SPACE
        assert 28 in result  # KEY_ENTER


class TestSpecialKeyNames:
    def test_dict_is_present_and_has_entries(self):
        from src.core.effects.reactive._evdev_specs import SPECIAL_KEY_NAMES

        assert isinstance(SPECIAL_KEY_NAMES, dict)
        assert len(SPECIAL_KEY_NAMES) > 0

    def test_known_entries(self):
        from src.core.effects.reactive._evdev_specs import SPECIAL_KEY_NAMES

        # Spot-check a couple of entries that should always be present
        assert "PRINT" in SPECIAL_KEY_NAMES or any("prtsc" in v for v in SPECIAL_KEY_NAMES.values())
