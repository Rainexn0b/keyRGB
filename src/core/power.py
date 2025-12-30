#!/usr/bin/env python3
"""
Power Management Module
Handles lid close/open, suspend/resume events to control keyboard backlight
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Optional

from .acpi_monitoring import monitor_acpi_events
from .lid_monitoring import start_sysfs_lid_monitoring
from .power_supply_sysfs import read_on_ac_power
from .power_source_policy import compute_power_source_policy
from src.legacy.config import Config

logger = logging.getLogger(__name__)


class PowerManager:
    """Monitor system power events and control keyboard accordingly"""
    
    def __init__(self, keyboard_controller, *, config: Config | None = None):
        """
        Initialize power manager.
        
        Args:
            keyboard_controller: The keyboard controller instance (should have turn_off/restore methods)
        """
        self.kb_controller = keyboard_controller
        self._config = config or Config()
        self.monitoring = False
        self.monitor_thread = None
        self._battery_thread = None
        self._saved_state = None
        self._battery_policy = BatterySaverPolicy()

    def _is_enabled(self) -> bool:
        try:
            self._config.reload()
            return bool(getattr(self._config, "power_management_enabled", True))
        except Exception:
            return True

    def _flag(self, name: str, default: bool = True) -> bool:
        try:
            self._config.reload()
            return bool(getattr(self._config, name, default))
        except Exception:
            return default
        
    def start_monitoring(self):
        """Start monitoring power events in background thread"""
        if self.monitoring:
            return

        # Still start monitoring even if disabled, so enabling it later in config works.
        # Actual actions are gated in the event handlers.
            
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

        self._battery_thread = threading.Thread(target=self._battery_saver_loop, daemon=True)
        self._battery_thread.start()
        
    def stop_monitoring(self):
        """Stop monitoring power events"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        if self._battery_thread:
            self._battery_thread.join(timeout=2)

    # ---- battery saver (dim on AC unplug)

    def _battery_saver_loop(self) -> None:
        """Poll AC online state and apply a simple dim/restore policy.

        Requirements:
        - no root required
        - debounce rapid toggling
        - don't fight manual brightness changes while on battery
        """

        poll_interval_s = 2.0
        last_on_ac: Optional[bool] = None
        last_change_ts: float = 0.0
        debounce_s: float = 3.0

        last_desired_enabled: Optional[bool] = None
        last_desired_brightness: Optional[int] = None

        while self.monitoring:
            try:
                on_ac = read_on_ac_power()
                if on_ac is None:
                    time.sleep(poll_interval_s)
                    continue

                now_mono = time.monotonic()

                # Debounce rapid toggling.
                if last_on_ac is not None and bool(on_ac) != bool(last_on_ac):
                    if float(now_mono) - float(last_change_ts) < float(debounce_s):
                        time.sleep(poll_interval_s)
                        continue
                    last_on_ac = bool(on_ac)
                    last_change_ts = float(now_mono)
                elif last_on_ac is None:
                    last_on_ac = bool(on_ac)
                    last_change_ts = float(now_mono)

                # Update config every tick so toggling works without restart.
                self._config.reload()

                # Treat all power-source behavior as part of "power management".
                if not bool(getattr(self._config, "power_management_enabled", True)):
                    time.sleep(poll_interval_s)
                    continue

                # Determine current brightness and whether user explicitly turned off.
                try:
                    current_brightness = int(getattr(self._config, "brightness", 0) or 0)
                except Exception:
                    current_brightness = 0

                is_off = bool(getattr(self.kb_controller, "is_off", False))

                # Per power-source desired state.
                ac_enabled = bool(getattr(self._config, "ac_lighting_enabled", True))
                batt_enabled = bool(getattr(self._config, "battery_lighting_enabled", True))

                ac_brightness_override = getattr(self._config, "ac_lighting_brightness", None)
                batt_brightness_override = getattr(self._config, "battery_lighting_brightness", None)

                desired_enabled, desired_brightness = compute_power_source_policy(
                    on_ac=bool(on_ac),
                    ac_enabled=ac_enabled,
                    battery_enabled=batt_enabled,
                    ac_brightness_override=ac_brightness_override,
                    battery_brightness_override=batt_brightness_override,
                )

                # Apply on/off on transitions (or when the desired enabled flag changes).
                if last_desired_enabled is None or bool(desired_enabled) != bool(last_desired_enabled):
                    try:
                        if not bool(desired_enabled):
                            # Power-policy forced off (tray restore() will only undo if forced).
                            if hasattr(self.kb_controller, "turn_off"):
                                self.kb_controller.turn_off()
                        else:
                            if hasattr(self.kb_controller, "restore"):
                                self.kb_controller.restore()
                    except Exception:
                        pass
                    last_desired_enabled = bool(desired_enabled)

                # If disabled in this power state, do not apply brightness policies.
                if not bool(desired_enabled):
                    time.sleep(poll_interval_s)
                    continue

                if desired_brightness is not None:
                    # Apply only when it actually changes.
                    if last_desired_brightness is None or int(desired_brightness) != int(last_desired_brightness):
                        if not is_off:
                            self._apply_brightness_policy(int(desired_brightness))
                        last_desired_brightness = int(desired_brightness)
                    time.sleep(poll_interval_s)
                    continue

                # Legacy battery saver policy (dim on AC unplug, restore on replug)
                # when no explicit battery brightness override is configured.
                enabled = bool(getattr(self._config, "battery_saver_enabled", False))
                target = int(getattr(self._config, "battery_saver_brightness", 25) or 0)
                self._battery_policy.configure(enabled=enabled, target_brightness=int(target))

                action = self._battery_policy.update(
                    on_ac=bool(on_ac),
                    current_brightness=current_brightness,
                    is_off=is_off,
                    now=now_mono,
                )

                if action is not None and last_on_ac is not None:
                    self._apply_brightness_policy(action)

                last_on_ac = bool(on_ac)

            except Exception as exc:
                logger.exception("Battery saver monitoring error: %s", exc)

            time.sleep(poll_interval_s)

    def _apply_brightness_policy(self, brightness: int) -> None:
        """Best-effort brightness change driven by power policy."""

        if brightness < 0:
            return

        try:
            # Prefer a dedicated hook on the controller if present.
            apply_fn = getattr(self.kb_controller, "apply_brightness_from_power_policy", None)
            if callable(apply_fn):
                apply_fn(int(brightness))
                return

            # Fallback: try a few known patterns.
            if hasattr(self.kb_controller, "engine"):
                try:
                    self._config.brightness = int(brightness)
                except Exception:
                    pass
                self.kb_controller.engine.set_brightness(int(brightness))
        except Exception as exc:
            logger.exception("Battery saver brightness apply failed: %s", exc)

    # ---- lid/suspend monitoring

    def _monitor_loop(self):
        """Main monitoring loop - watches for lid and suspend events"""
        # Use dbus-monitor to watch systemd-logind signals
        try:
            # Monitor both PrepareForSleep (suspend/resume) and Lid switch
            cmd = [
                'dbus-monitor',
                '--system',
                "type='signal',interface='org.freedesktop.login1.Manager',member='PrepareForSleep'",
            ]

            logger.info("Power monitoring started using dbus-monitor")

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )

            # For type-checkers: stdout is only None if stdout=DEVNULL/None.
            assert process.stdout is not None

            # Also monitor lid switch using a separate method
            self._start_lid_monitor()

            while self.monitoring:
                line = process.stdout.readline()
                if not line:
                    break

                # Detect prepare for sleep (suspend)
                if 'PrepareForSleep' in line:
                    # Read the next line to see if it's true (going to sleep) or false (waking up)
                    next_line = process.stdout.readline()
                    if 'boolean true' in next_line:
                        logger.info("Detected: System suspending")
                        self._on_suspend()
                    elif 'boolean false' in next_line:
                        logger.info("Detected: System resuming")
                        self._on_resume()

        except FileNotFoundError:
            logger.warning("dbus-monitor not available, trying alternative method")
            self._monitor_acpi_events()
        except Exception as e:
            logger.exception("Power monitoring error: %s", e)

    def _start_lid_monitor(self):
        """Start a separate thread to monitor lid switch via sysfs"""
        start_sysfs_lid_monitoring(
            is_running=lambda: self.monitoring,
            on_lid_close=self._on_lid_close,
            on_lid_open=self._on_lid_open,
            logger=logger,
        )

    def _monitor_acpi_events(self):
        """Fallback method using acpi_listen for lid events"""
        monitor_acpi_events(
            is_running=lambda: self.monitoring,
            on_lid_close=self._on_lid_close,
            on_lid_open=self._on_lid_open,
            logger=logger,
        )

    def _on_suspend(self):
        """Called when system is about to suspend"""
        if not self._is_enabled():
            return
        if not self._flag("power_off_on_suspend", True):
            return
        logger.info("System suspending - turning off keyboard backlight")
        self._save_and_turn_off()

    def _on_resume(self):
        """Called when system resumes from suspend"""
        if not self._is_enabled():
            return
        if not self._flag("power_restore_on_resume", True):
            return
        logger.info("System resumed - restoring keyboard backlight")
        time.sleep(0.5)  # Give hardware time to wake up
        self._restore()

    def _on_lid_close(self):
        """Called when lid is closed"""
        if not self._is_enabled():
            return
        if not self._flag("power_off_on_lid_close", True):
            return
        logger.info("Lid closed - turning off keyboard backlight")
        self._save_and_turn_off()

    def _on_lid_open(self):
        """Called when lid is opened"""
        if not self._is_enabled():
            return
        if not self._flag("power_restore_on_lid_open", True):
            return
        logger.info("Lid opened - restoring keyboard backlight")
        self._restore()

    def _save_and_turn_off(self):
        """Save current state and turn off keyboard"""
        try:
            # Save current state if not already saved
            if self._saved_state is None:
                # Save whether keyboard was already off
                if hasattr(self.kb_controller, 'is_off'):
                    self._saved_state = {'was_off': self.kb_controller.is_off}
                else:
                    self._saved_state = {'was_off': False}
                logger.debug("Saved state: %s", self._saved_state)

            # Turn off keyboard
            if hasattr(self.kb_controller, 'turn_off'):
                self.kb_controller.turn_off()
            elif hasattr(self.kb_controller, 'kb'):
                self.kb_controller.kb.turn_off()
        except Exception as e:
            logger.exception("Error turning off keyboard: %s", e)

    def _restore(self):
        """Restore keyboard to previous state"""
        try:
            # Only restore if keyboard wasn't already off before lid close
            if self._saved_state is not None:
                logger.debug("Restoring from state: %s", self._saved_state)
                if not self._saved_state.get('was_off', False):
                    if hasattr(self.kb_controller, 'restore'):
                        self.kb_controller.restore()
                    logger.info("Keyboard restored")
                else:
                    logger.info("Keyboard was off before lid close, keeping it off")
                self._saved_state = None
        except Exception as e:
            logger.exception("Error restoring keyboard: %s", e)
@dataclass
class BatterySaverPolicy:
    """State machine for dim-on-battery and restore-on-AC.

    This is designed to be unit-testable (no threads, no IO).
    """

    enabled: bool = False
    target_brightness: int = 25
    debounce_seconds: float = 3.0

    _last_state: Optional[bool] = None
    _last_change_ts: float = 0.0
    _saved_ac_brightness: Optional[int] = None
    _applied_battery_brightness: Optional[int] = None
    _manual_override_on_battery: bool = False

    def configure(self, *, enabled: bool, target_brightness: int) -> None:
        self.enabled = bool(enabled)
        self.target_brightness = int(target_brightness)

    def update(self, *, on_ac: bool, current_brightness: int, is_off: bool, now: float) -> Optional[int]:
        """Process current inputs and return a brightness to apply, if any."""

        on_ac = bool(on_ac)
        current_brightness = int(current_brightness)

        # Track manual overrides while on battery (user brightness differs from what we set).
        if self._last_state is False and self._applied_battery_brightness is not None:
            if current_brightness != int(self._applied_battery_brightness):
                self._manual_override_on_battery = True

        if self._last_state is None:
            self._last_state = on_ac
            self._last_change_ts = float(now)
            return None

        if on_ac == self._last_state:
            return None

        # Debounce flapping.
        if float(now) - float(self._last_change_ts) < float(self.debounce_seconds):
            return None

        self._last_state = on_ac
        self._last_change_ts = float(now)

        if not self.enabled:
            # Clear any pending restore state to avoid surprise restores later.
            self._saved_ac_brightness = None
            self._applied_battery_brightness = None
            self._manual_override_on_battery = False
            return None

        if is_off:
            # User explicitly turned the keyboard off; do not fight it.
            return None

        if not on_ac:
            # AC -> Battery: dim.
            target = max(0, int(self.target_brightness))
            if current_brightness <= 0:
                return None

            # Only act if we would actually reduce brightness.
            if 0 < target < current_brightness:
                self._saved_ac_brightness = current_brightness
                self._applied_battery_brightness = target
                self._manual_override_on_battery = False
                return target
            return None

        # Battery -> AC: restore.
        restore = self._saved_ac_brightness
        self._saved_ac_brightness = None
        self._applied_battery_brightness = None
        self._manual_override_on_battery = False
        if restore is None:
            return None
        return int(restore)


if __name__ == '__main__':
    # Test power manager
    class DummyController:
        def turn_off(self):
            logger.info("KEYBOARD OFF")
        def restore(self):
            logger.info("KEYBOARD ON")
            
    pm = PowerManager(DummyController())
    pm.start_monitoring()
    
    try:
        logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')
        logger.info("Monitoring power events... Press Ctrl+C to stop")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pm.stop_monitoring()
        logger.info("Stopped")
