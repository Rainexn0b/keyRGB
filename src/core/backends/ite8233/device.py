from __future__ import annotations

from collections.abc import Callable, Sequence

from . import protocol

FeatureReportWriter = Callable[[bytes], int]


class Ite8233LightbarDevice:
    """Minimal single-zone lightbar device for the supported ITE lightbar HID paths."""

    keyrgb_hw_speed_policy = "inverted"

    def __init__(
        self,
        send_feature_report: FeatureReportWriter,
        *,
        product_id: int = protocol.DEFAULT_PRODUCT_ID,
        current_brightness: int = 50,
    ) -> None:
        if not callable(send_feature_report):
            raise TypeError("send_feature_report must be callable")

        self._send_feature_report = send_feature_report
        self._product_id = protocol.normalize_product_id(product_id)
        self._brightness = protocol.clamp_ui_brightness(current_brightness)
        self._current_color = (255, 255, 255)
        self._is_off = self._brightness <= 0

    def _write_report(self, report: bytes) -> None:
        result = self._send_feature_report(bytes(report))
        if int(result) < 0:
            raise OSError("Could not send ITE 8233 feature report")

    def _write_reports(self, reports: Sequence[bytes]) -> None:
        for report in reports:
            self._write_report(report)

    def _raise_unimplemented(self) -> None:
        raise RuntimeError(
            "ITE 8233 lightbar protocol is not implemented yet; collect protocol dumps before enabling this backend"
        )

    def _normalize_effect_name(self, effect_data) -> str:
        if isinstance(effect_data, str):
            return effect_data.strip().lower().replace(" ", "_")
        if isinstance(effect_data, dict):
            name = effect_data.get("name") or effect_data.get("effect")
            return str(name or "").strip().lower().replace(" ", "_")
        return ""

    def turn_off(self) -> None:
        self._write_reports(protocol.build_turn_off_reports(product_id=self._product_id))
        self._is_off = True
        self._brightness = 0

    def is_off(self) -> bool:
        return bool(self._is_off)

    def get_brightness(self) -> int:
        return int(self._brightness)

    def set_brightness(self, brightness: int) -> None:
        level = protocol.clamp_ui_brightness(brightness)
        if level <= 0:
            self.turn_off()
            return

        self._write_report(
            protocol.build_brightness_report(protocol.raw_brightness_from_ui(level), product_id=self._product_id)
        )
        self._brightness = level
        self._is_off = False

    def set_color(self, color, *, brightness: int):
        scaled = protocol.scale_color_for_brightness(color, brightness)
        level = protocol.clamp_ui_brightness(brightness)
        if level <= 0:
            self.turn_off()
            return

        self._write_report(protocol.build_uniform_color_report(scaled, product_id=self._product_id))
        self._write_report(
            protocol.build_brightness_report(protocol.raw_brightness_from_ui(level), product_id=self._product_id)
        )
        self._current_color = tuple(int(channel) for channel in color)  # type: ignore[assignment]
        self._brightness = level
        self._is_off = False

    def set_key_colors(self, color_map, *, brightness: int, enable_user_mode: bool = True):
        del color_map, brightness, enable_user_mode
        self._raise_unimplemented()

    def set_effect(self, effect_data) -> None:
        effect_name = self._normalize_effect_name(effect_data)
        if effect_name not in {"breathing", "breathing_color", "breathe", "wave", "bounce", "clash", "catchup", "catch_up", "flash"}:
            self._raise_unimplemented()

        effect_dict = effect_data if isinstance(effect_data, dict) else {}
        brightness = protocol.clamp_ui_brightness(effect_dict.get("brightness", self._brightness))
        speed = protocol.raw_speed_from_ui(effect_dict.get("speed", protocol.RAW_SPEED_MAX))
        if brightness <= 0:
            self.turn_off()
            return

        if effect_name == "wave":
            if not protocol.wave_supported(self._product_id):
                raise RuntimeError(f"ITE lightbar wave is not supported for product 0x{self._product_id:04x}")

            self._write_report(
                protocol.build_wave_report(
                    brightness=protocol.raw_brightness_from_ui(brightness),
                    speed=speed,
                    product_id=self._product_id,
                )
            )
            self._brightness = brightness
            self._is_off = False
            return

        if effect_name in {"bounce", "clash"}:
            if not protocol.bounce_supported(self._product_id):
                raise RuntimeError(f"ITE lightbar bounce is not supported for product 0x{self._product_id:04x}")

            self._write_report(
                protocol.build_bounce_report(
                    brightness=protocol.raw_brightness_from_ui(brightness),
                    speed=speed,
                    product_id=self._product_id,
                )
            )
            self._brightness = brightness
            self._is_off = False
            return

        if effect_name in {"catchup", "catch_up"}:
            if not protocol.catchup_supported(self._product_id):
                raise RuntimeError(f"ITE lightbar catchup is not supported for product 0x{self._product_id:04x}")

            self._write_report(
                protocol.build_catchup_report(
                    brightness=protocol.raw_brightness_from_ui(brightness),
                    speed=speed,
                    product_id=self._product_id,
                )
            )
            self._brightness = brightness
            self._is_off = False
            return

        if effect_name == "flash":
            if not protocol.flash_supported(self._product_id):
                raise RuntimeError(f"ITE lightbar flash is not supported for product 0x{self._product_id:04x}")

            dir_input = effect_dict.get("direction", None)
            if dir_input in {"right", 1, protocol.FLASH_DIRECTION_RIGHT}:
                direction = protocol.FLASH_DIRECTION_RIGHT
            elif dir_input in {"left", 2, protocol.FLASH_DIRECTION_LEFT}:
                direction = protocol.FLASH_DIRECTION_LEFT
            else:
                direction = protocol.FLASH_DIRECTION_NONE

            color = effect_dict.get("color", self._current_color)
            flash_reports = protocol.build_flash_reports(
                color,
                brightness=protocol.raw_brightness_from_ui(brightness),
                speed=speed,
                direction=direction,
                product_id=self._product_id,
            )
            self._write_reports(flash_reports)
            self._current_color = tuple(int(ch) for ch in color)  # type: ignore[assignment]
            self._brightness = brightness
            self._is_off = False
            return

        if not protocol.breathing_supported(self._product_id):
            raise RuntimeError(
                f"ITE lightbar breathing is not supported for product 0x{self._product_id:04x}"
            )

        color = effect_dict.get("color", self._current_color)

        reports = protocol.build_breathing_reports(
            color,
            brightness=protocol.raw_brightness_from_ui(brightness),
            speed=speed,
            product_id=self._product_id,
        )
        self._write_reports(reports)
        self._current_color = tuple(int(channel) for channel in color)  # type: ignore[assignment]
        self._brightness = brightness
        self._is_off = False
