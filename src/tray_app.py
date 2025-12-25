#!/usr/bin/env python3
"""
KeyRGB System Tray Application
Minimal RGB keyboard controller with system tray interface
"""

import sys
import os
import subprocess
import threading
import time
import colorsys
from pathlib import Path
from io import BytesIO
import logging
from contextlib import suppress

from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item

logger = logging.getLogger(__name__)


_instance_lock_fh = None


def _acquire_single_instance_lock() -> bool:
    """Ensure only one KeyRGB tray app controls the USB device.

    Prevents confusing failures like `[Errno 16] Resource busy` when a second
    instance starts while the first is still running.
    """

    global _instance_lock_fh

    try:
        import fcntl  # Linux/Unix
    except Exception:
        return True

    lock_dir = Path.home() / ".config" / "keyrgb"
    with suppress(Exception):
        lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / "keyrgb.lock"

    try:
        _instance_lock_fh = open(lock_path, "a+")
        fcntl.flock(_instance_lock_fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        _instance_lock_fh.seek(0)
        _instance_lock_fh.truncate()
        _instance_lock_fh.write(f"pid={os.getpid()}\n")
        _instance_lock_fh.flush()
        return True
    except OSError:
        return False

try:
    from .effects_legacy import EffectsEngine
    from .config_legacy import Config
    from .power_manager import PowerManager
except Exception:
    # Fallback for direct execution (e.g. `python src/tray_app.py`).
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from src.effects_legacy import EffectsEngine
    from src.config_legacy import Config
    from src.power_manager import PowerManager

try:
    # Prefer vendored dependency when running from repo (matches EffectsEngine).
    repo_root = Path(__file__).resolve().parent.parent
    vendored = repo_root / "ite8291r3-ctl"
    if vendored.exists() and os.environ.get("KEYRGB_USE_INSTALLED_ITE") != "1":
        sys.path.insert(0, str(vendored))

    from ite8291r3_ctl.ite8291r3 import NUM_ROWS as ITE_NUM_ROWS, NUM_COLS as ITE_NUM_COLS
except Exception:
    ITE_NUM_ROWS, ITE_NUM_COLS = 6, 21

# PyQt6 for slider dialogs
try:
    from PyQt6.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QSlider, QPushButton
    from PyQt6.QtCore import Qt, QPoint
    from PyQt6.QtGui import QCursor, QScreen
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    logger.debug("PyQt6 not available - sliders disabled")


class KeyRGBTray:
    """System tray application for KeyRGB"""
    
    def __init__(self):
        """Initialize tray application"""
        self.config = Config()
        self.engine = EffectsEngine()
        self.icon = None
        self.is_off = False
        self._power_forced_off = False
        self._last_brightness = 25  # Remember last non-zero brightness (default 50% = 25 on 0-50 scale)
        
        # Initialize power manager
        self.power_manager = PowerManager(self)
        self.power_manager.start_monitoring()
        
        # Start hardware state polling for sync with physical buttons
        self._start_hardware_polling()

        # Start config polling so external tools (e.g. uniform GUI) can apply changes
        self._start_config_polling()

        # Keep tray icon color roughly in sync with dynamic effects (e.g. rainbow)
        self._start_icon_color_polling()
        
        # Start last effect on launch
        if self.config.autostart and not self.is_off:
            self._start_current_effect()
    
    def _start_hardware_polling(self):
        """Start polling keyboard hardware state to detect physical button changes"""
        import threading
        
        def poll_hardware():
            import time
            last_brightness = None
            last_off_state = None
            
            while True:
                try:
                    # Query hardware state
                    with self.engine.kb_lock:
                        current_brightness = self.engine.kb.get_brightness()
                        current_off = self.engine.kb.is_off()
                    
                    # Remember last non-zero brightness from hardware
                    if current_brightness > 0:
                        self._last_brightness = current_brightness
                    
                    # Treat brightness 0 as "off" state
                    if current_brightness == 0:
                        current_off = True
                    
                    # Detect brightness changes from hardware buttons
                    if last_brightness is not None and current_brightness != last_brightness:
                        # If we turned the keyboard off due to a lid/suspend event,
                        # don't treat the forced-off brightness=0 as a user action
                        # and don't persist it into config.
                        if self._power_forced_off and current_brightness == 0:
                            last_brightness = current_brightness
                            last_off_state = current_off
                            continue

                        # Hardware button changed brightness - sync config
                        self.config.brightness = current_brightness
                        
                        # Update off state based on brightness
                        if current_brightness == 0:
                            self.is_off = True
                        elif last_brightness == 0:
                            # Brightness went from 0 to something - turn on
                            self.is_off = False
                        
                        self._update_icon()
                        self._update_menu()
                    
                    # Detect off state changes from hardware buttons
                    elif last_off_state is not None and current_off != last_off_state:
                        # Same idea: ignore forced-off transitions triggered by power events.
                        if self._power_forced_off and current_off:
                            last_brightness = current_brightness
                            last_off_state = current_off
                            continue

                        self.is_off = current_off
                        self._update_icon()
                        self._update_menu()
                    
                    last_brightness = current_brightness
                    last_off_state = current_off
                    
                except Exception as e:
                    # Ignore transient errors (keyboard might be busy)
                    pass
                
                time.sleep(2)  # Poll every 2 seconds
        
        poll_thread = threading.Thread(target=poll_hardware, daemon=True)
        poll_thread.start()
    
    def _create_icon(self, color=(255, 0, 128)):
        """Create tray icon image"""
        # Create a 64x64 icon with keyboard symbol
        img = Image.new('RGB', (64, 64), color=(0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Draw simple keyboard icon (rectangle with grid)
        draw.rectangle([8, 20, 56, 44], outline=color, width=2)
        # Keys
        for row in range(2):
            for col in range(6):
                x = 12 + col * 7
                y = 24 + row * 8
                draw.rectangle([x, y, x+4, y+4], fill=color)
        
        return img

    def _start_icon_color_polling(self):
        """Update tray icon color periodically for dynamic effects.

        Some effects (e.g. rainbow) are multi-color and change over time.
        The icon color is updated at a low rate to roughly track them.
        """

        def poll_icon_color():
            last_sig = None
            while True:
                try:
                    # Signature: (off, effect, speed, brightness, color)
                    sig = (
                        bool(self.is_off),
                        str(getattr(self.config, "effect", "")),
                        int(getattr(self.config, "speed", 0) or 0),
                        int(getattr(self.config, "brightness", 0) or 0),
                        tuple(getattr(self.config, "color", (0, 0, 0)) or (0, 0, 0)),
                    )

                    dynamic = sig[1] in {"rainbow", "random", "aurora", "fireworks", "wave", "marquee"}

                    if dynamic or sig != last_sig:
                        self._update_icon()
                        last_sig = sig
                except Exception:
                    pass

                time.sleep(0.8)

        t = threading.Thread(target=poll_icon_color, daemon=True)
        t.start()

    def _representative_color(self) -> tuple[int, int, int]:
        """Pick an RGB color representative of the currently applied state."""

        # Off state
        if self.is_off or getattr(self.config, "brightness", 0) == 0:
            return (64, 64, 64)

        effect = str(getattr(self.config, "effect", "none") or "none")
        brightness = int(getattr(self.config, "brightness", 25) or 25)

        # Per-key: average of configured colors (roughly matches the visible theme)
        if effect == "perkey":
            try:
                values = list(getattr(self.config, "per_key_colors", {}).values())
            except Exception:
                values = []

            if values:
                r = int(round(sum(c[0] for c in values) / len(values)))
                g = int(round(sum(c[1] for c in values) / len(values)))
                b = int(round(sum(c[2] for c in values) / len(values)))
                base = (r, g, b)
            else:
                base = tuple(getattr(self.config, "color", (255, 0, 128)) or (255, 0, 128))
        # Multi-color effects: cycle a hue so the icon changes as the keyboard does.
        elif effect in {"rainbow", "random", "aurora", "fireworks", "wave", "marquee"}:
            speed = int(getattr(self.config, "speed", 5) or 5)
            # Convert speed 0..10 into a cycle rate.
            rate = 0.05 + 0.10 * (max(0, min(10, speed)) / 10.0)
            hue = (time.time() * rate) % 1.0
            rr, gg, bb = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
            base = (int(rr * 255), int(gg * 255), int(bb * 255))
        else:
            base = tuple(getattr(self.config, "color", (255, 0, 128)) or (255, 0, 128))

        # Scale by brightness (0..50). Keep a minimum so the icon stays visible.
        scale = max(0.25, min(1.0, brightness / 50.0))
        return (
            int(max(0, min(255, base[0] * scale))),
            int(max(0, min(255, base[1] * scale))),
            int(max(0, min(255, base[2] * scale))),
        )
    
    def _start_current_effect(self):
        """Start effect from config"""
        try:
            # Per-key mode: apply per-key color map
            if self.config.effect == 'perkey':
                self.engine.stop()
                if self.config.brightness == 0:
                    self.engine.turn_off()
                    self.is_off = True
                    return

                color_map = self.config.per_key_colors
                with self.engine.kb_lock:
                    self.engine.kb.set_key_colors(color_map, brightness=self.config.brightness, enable_user_mode=True)
                self.is_off = False
                return

            # Treat 'none' as "no animation" but still apply the configured color.
            if self.config.effect == 'none':
                self.engine.stop()
                if self.config.brightness == 0:
                    self.engine.turn_off()
                    self.is_off = True
                    return

                with self.engine.kb_lock:
                    self.engine.kb.set_color(self.config.color, brightness=self.config.brightness)
                self.is_off = False
                return
            
            self.engine.start_effect(
                self.config.effect,
                speed=self.config.speed,
                brightness=self.config.brightness,
                color=self.config.color
            )
            self.is_off = False
        except Exception as e:
            logger.exception("Error starting effect: %s", e)

    def _start_config_polling(self):
        """Poll config file for external changes and apply them."""

        config_path = Path(self.config.CONFIG_FILE)
        last_mtime = None
        last_applied = None

        def apply_from_config():
            nonlocal last_applied

            perkey_sig = None
            if self.config.effect == 'perkey':
                # Include the per-key map in the change signature so edits apply.
                # Sorting provides stability for comparison.
                try:
                    perkey_sig = tuple(sorted(self.config.per_key_colors.items()))
                except Exception:
                    perkey_sig = None

            # Snapshot settings after reload
            current = (
                self.config.effect,
                self.config.speed,
                self.config.brightness,
                tuple(self.config.color),
                perkey_sig,
            )

            if current == last_applied:
                return

            # Respect explicit off state (don't turn on LEDs behind user's back)
            if self.is_off:
                last_applied = current
                self._update_menu()
                return

            # If brightness is 0, treat as off.
            if self.config.brightness == 0:
                try:
                    self.engine.turn_off()
                except Exception:
                    pass
                self.is_off = True
                last_applied = current
                self._update_icon()
                self._update_menu()
                return

            # Remember last non-zero brightness for restore
            if self.config.brightness > 0:
                self._last_brightness = self.config.brightness

            # Apply effect/color
            try:
                if self.config.effect == 'perkey':
                    self.engine.stop()
                    color_map = dict(self.config.per_key_colors)

                    # If map is partial, fill missing keys with the base color so
                    # changing one key doesn't blank the rest of the keyboard.
                    if 0 < len(color_map) < (ITE_NUM_ROWS * ITE_NUM_COLS):
                        base = tuple(self.config.color)
                        for r in range(ITE_NUM_ROWS):
                            for c in range(ITE_NUM_COLS):
                                color_map.setdefault((r, c), base)

                    with self.engine.kb_lock:
                        self.engine.kb.set_key_colors(color_map, brightness=self.config.brightness, enable_user_mode=True)
                elif self.config.effect == 'none':
                    self.engine.stop()
                    with self.engine.kb_lock:
                        self.engine.kb.set_color(self.config.color, brightness=self.config.brightness)
                else:
                    self._start_current_effect()
            except Exception as e:
                logger.exception("Error applying config change: %s", e)

            last_applied = current
            self._update_icon()
            self._update_menu()

        def poll_config():
            nonlocal last_mtime

            # Initialize mtime/applied snapshot
            try:
                last_mtime = config_path.stat().st_mtime
            except FileNotFoundError:
                last_mtime = None

            # Apply once at startup so 'none' behaves like static color
            try:
                self.config.reload()
                apply_from_config()
            except Exception:
                pass

            while True:
                try:
                    mtime = config_path.stat().st_mtime
                except FileNotFoundError:
                    mtime = None

                if mtime != last_mtime:
                    last_mtime = mtime
                    try:
                        self.config.reload()
                        apply_from_config()
                    except Exception as e:
                        logger.exception("Error reloading config: %s", e)

                time.sleep(0.1)

        t = threading.Thread(target=poll_config, daemon=True)
        t.start()
    
    def _on_effect_clicked(self, icon, item):
        """Handle effect selection"""
        effect_name = str(item).lower()
        # Remove emoji prefix if present
        for emoji in ['🌈', '💨', '🌊', '💧', '✨', '🌧️', '🌌', '🎆', '⚫', '💗', '⚡', '🔥', '🎲', '⏹️']:
            effect_name = effect_name.replace(emoji, '').strip()
        
        if effect_name == 'none' or effect_name == 'stop':
            # Stop all effects and set to static current color
            self.engine.stop()
            # Set static color to last known color to stop animations
            with self.engine.kb_lock:
                self.engine.kb.set_color(self.config.color, brightness=self.config.brightness)
            self.config.effect = 'none'
            self.is_off = False
        else:
            self.config.effect = effect_name
            self._start_current_effect()
        
        self._update_icon()
        self._update_menu()
    
    def _on_speed_clicked(self, icon, item):
        """Handle speed change"""
        speed_str = str(item).replace('🔘', '').replace('⚪', '').strip()
        try:
            speed = int(speed_str)
            self.config.speed = speed
            if not self.is_off:
                self._start_current_effect()
            self._update_menu()
        except ValueError:
            pass
    
    def _on_brightness_clicked(self, icon, item):
        """Handle brightness change"""
        brightness_str = str(item).replace('🔘', '').replace('⚪', '').strip()
        try:
            brightness = int(brightness_str)
            # Convert 0-10 scale to 0-50 hardware scale (multiply by 5)
            brightness_hw = brightness * 5
            
            # Remember last non-zero brightness
            if brightness_hw > 0:
                self._last_brightness = brightness_hw
            
            self.config.brightness = brightness_hw
            self.engine.set_brightness(self.config.brightness)
            if not self.is_off:
                self._start_current_effect()
            self._update_menu()
        except ValueError:
            pass
    
    def _on_open_kde_brightness(self, icon, item):
        """Open KDE System Settings to Display and Monitor > Brightness"""
        subprocess.Popen(['qdbus', 'org.kde.plasmashell', '/PlasmaShell', 
                         'org.kde.PlasmaShell.evaluateScript', 
                         'panels().forEach(panel => panel.widgets().forEach(widget => { if (widget.type == "org.kde.plasma.systemtray") widget.action("configure").trigger(); }))'])
    
    def _on_off_clicked(self, icon, item):
        """Turn off keyboard lighting"""
        self.engine.turn_off()
        self.is_off = True
        self._update_icon()
        self._update_menu()
    
    def _on_turn_on_clicked(self, icon, item):
        """Turn on keyboard lighting"""
        self.is_off = False
        
        # If brightness is 0, restore to last known brightness or default
        if self.config.brightness == 0:
            self.config.brightness = self._last_brightness if self._last_brightness > 0 else 25
        
        # If last effect was 'none', set a static color instead of nothing
        if self.config.effect == 'none':
            with self.engine.kb_lock:
                self.engine.kb.set_color(self.config.color, brightness=self.config.brightness)
        else:
            self._start_current_effect()
        
        self._update_icon()
        self._update_menu()
    
    def _on_perkey_clicked(self, icon, item):
        """Open per-key editor window"""
        parent_path = os.path.dirname(os.path.dirname(__file__))
        try:
            subprocess.Popen([sys.executable, '-m', 'src.gui_perkey'], cwd=parent_path)
        except FileNotFoundError:
            subprocess.Popen([sys.executable, '-m', 'src.gui_perkey_legacy'], cwd=parent_path)
    
    def _on_tuxedo_gui_clicked(self, icon, item):
        """Launch uniform color GUI"""
        parent_path = os.path.dirname(os.path.dirname(__file__))
        subprocess.Popen([sys.executable, '-m', 'src.gui_uniform'], cwd=parent_path)
    
    def _on_quit_clicked(self, icon, item):
        """Quit application"""
        self.power_manager.stop_monitoring()
        self.engine.stop()
        icon.stop()
    
    def turn_off(self):
        """Turn off keyboard (called by power manager)"""
        # Mark as power-forced so restore can safely bring it back even if
        # hardware polling observes brightness 0 and sets is_off.
        self._power_forced_off = True
        self.is_off = True
        self.engine.turn_off()
        self._update_icon()
        self._update_menu()
        
    def restore(self):
        """Restore keyboard state (called by power manager)"""
        # If we turned it off due to lid/suspend, restore regardless of the
        # current is_off flag (which may have been set by hardware polling).
        if self._power_forced_off:
            self._power_forced_off = False
            self.is_off = False

            # Hardware polling may have persisted brightness=0 during the off
            # window (or observed it). Ensure we restore a sane brightness.
            if self.config.brightness == 0:
                self.config.brightness = self._last_brightness if self._last_brightness > 0 else 25

            self._start_current_effect()
            self._update_icon()
            self._update_menu()
            return

        if not self.is_off:
            self._start_current_effect()
    
    def _update_icon(self):
        """Update icon based on state"""
        if self.icon:
            self.icon.icon = self._create_icon(self._representative_color())
    
    def _update_menu(self):
        """Rebuild menu to update checkmarks"""
        if self.icon:
            # Reload config from disk to sync with any external changes
            self.config.reload()
            self.icon.menu = self._build_menu()
    
    def _on_menu_open(self):
        """Called when menu is about to be shown - refresh state"""
        self.config.reload()
        self._update_menu()
    
    def _build_menu_items(self):
        """Build menu items list - for dynamic menu updates"""
        
        # Effect emojis for visual distinction
        hw_effect_icons = {
            'rainbow': '🌈',
            'breathing': '💨',
            'wave': '🌊',
            'ripple': '💧',
            'marquee': '✨',
            'raindrop': '🌧️',
            'aurora': '🌌',
            'fireworks': '🎆'
        }
        
        sw_effect_icons = {
            'static': '⚫',
            'pulse': '💗',
            'strobe': '⚡',
            'fire': '🔥',
            'random': '🎲'
        }
        
        # Submenu for hardware effects
        hw_effects_menu = pystray.Menu(
            item(
                "⏹️ None",
                self._on_effect_clicked,
                checked=lambda item: self.config.effect == 'none' and not self.is_off,
                radio=True
            ),
            pystray.Menu.SEPARATOR,
            *[item(
                f"{hw_effect_icons.get(effect, '•')} {effect.capitalize()}",
                self._on_effect_clicked,
                checked=lambda item, e=effect: self.config.effect == e and not self.is_off,
                radio=True
            ) for effect in ['rainbow', 'breathing', 'wave', 'ripple', 'marquee', 'raindrop', 'aurora', 'fireworks']]
        )
        
        # Submenu for software effects
        sw_effects_menu = pystray.Menu(
            item(
                "⏹️ None",
                self._on_effect_clicked,
                checked=lambda item: self.config.effect == 'none' and not self.is_off,
                radio=True
            ),
            pystray.Menu.SEPARATOR,
            *[item(
                f"{sw_effect_icons.get(effect, '•')} {effect.capitalize()}",
                self._on_effect_clicked,
                checked=lambda item, e=effect: self.config.effect == e and not self.is_off,
                radio=True
            ) for effect in ['static', 'pulse', 'strobe', 'fire', 'random']]
        )
        
        # Speed submenu (0-10)
        speed_menu = pystray.Menu(
            *[item(
                f"{'🔘' if self.config.speed == speed else '⚪'} {speed}",
                self._on_speed_clicked,
                checked=lambda item, s=speed: self.config.speed == s,
                radio=True
            ) for speed in range(0, 11)]
        )
        
        # Brightness submenu (0-10, converted to 0-50 internally)
        brightness_menu = pystray.Menu(
            *[item(
                f"{'🔘' if self.config.brightness == brightness * 5 else '⚪'} {brightness}",
                self._on_brightness_clicked,
                checked=lambda item, b=brightness: self.config.brightness == b * 5,
                radio=True
            ) for brightness in range(0, 11)]
        )
        
        # Build menu items
        menu_items = [
            # Effects submenus
            item('🎨 Hardware Effects', hw_effects_menu),
            item('💫 Software Effects', sw_effects_menu),
            pystray.Menu.SEPARATOR,
            # Speed and brightness submenus
            item('⚡ Speed', speed_menu),
            item('💡 Brightness', brightness_menu),
            pystray.Menu.SEPARATOR,
            # GUI Tools
            item('🎹 Per-Key Colors', self._on_perkey_clicked),
            item('🌈 Uniform Color', self._on_tuxedo_gui_clicked),
            pystray.Menu.SEPARATOR,
            # Power control
            item('🔌 Off' if not self.is_off else '✅ Turn On', 
                 self._on_off_clicked if not self.is_off else self._on_turn_on_clicked,
                 checked=lambda item: self.is_off),
            item('❌ Quit', self._on_quit_clicked)
        ]
        
        return menu_items
    
    def _build_menu(self):
        """Build system tray menu - returns pystray.Menu object"""
        # Reload config before building to ensure up-to-date state
        self.config.reload()
        return pystray.Menu(*self._build_menu_items())
    
    def run(self):
        """Run the tray application"""
        logger.info("Creating tray icon...")
        self.icon = pystray.Icon(
            'keyrgb',
            self._create_icon(self._representative_color()),
            'KeyRGB',
            menu=self._build_menu()  # Pass Menu object directly
        )
        
        logger.info("KeyRGB tray app started")
        logger.info("Current effect: %s", self.config.effect)
        logger.info("Speed: %s, Brightness: %s", self.config.speed, self.config.brightness)
        logger.debug("Running icon.run()...")
        self.icon.run()


def main():
    """Main entry point"""
    try:
        if not logging.getLogger().handlers:
            level = logging.DEBUG if os.environ.get('KEYRGB_DEBUG') else logging.INFO
            logging.basicConfig(level=level, format='%(levelname)s %(name)s: %(message)s')

        if not _acquire_single_instance_lock():
            logger.error("KeyRGB is already running (lock held). Not starting a second instance.")
            sys.exit(0)

        app = KeyRGBTray()
        app.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.exception("Unhandled error: %s", e)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
