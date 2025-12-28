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

from .acpi_monitoring import monitor_acpi_events
from .lid_monitoring import start_sysfs_lid_monitoring
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
        self._saved_state = None

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
        
    def stop_monitoring(self):
        """Stop monitoring power events"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
            
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
