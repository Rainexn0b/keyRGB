#!/usr/bin/env python3
"""
KeyRGB System Tray Application
Minimal RGB keyboard controller with system tray interface
"""

import sys
import subprocess
from io import BytesIO
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item
from effects import EffectsEngine
from config import Config

# PyQt6 for slider dialogs
try:
    from PyQt6.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QSlider, QPushButton
    from PyQt6.QtCore import Qt, QPoint
    from PyQt6.QtGui import QCursor, QScreen
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    print("PyQt6 not available - sliders disabled")


class KeyRGBTray:
    """System tray application for KeyRGB"""
    
    def __init__(self):
        """Initialize tray application"""
        self.config = Config()
        self.engine = EffectsEngine()
        self.icon = None
        self.is_off = False
        
        # Start last effect on launch
        if self.config.autostart and not self.is_off:
            self._start_current_effect()
    
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
    
    def _start_current_effect(self):
        """Start effect from config"""
        try:
            # Skip if effect is 'none'
            if self.config.effect == 'none':
                return
            
            self.engine.start_effect(
                self.config.effect,
                speed=self.config.speed,
                brightness=self.config.brightness,
                color=self.config.color
            )
            self.is_off = False
        except Exception as e:
            print(f"Error starting effect: {e}")
    
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
            # Convert 0-10 scale to 5-50 hardware scale (multiply by 5)
            self.config.brightness = brightness * 5 if brightness > 0 else 5
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
        
        # If last effect was 'none', set a static color instead of nothing
        if self.config.effect == 'none':
            self.engine.kb.set_color(self.config.color, brightness=self.config.brightness)
        else:
            self._start_current_effect()
        
        self._update_icon()
        self._update_menu()
    
    def _on_perkey_clicked(self, icon, item):
        """Open per-key editor window"""
        import os
        editor_path = os.path.dirname(os.path.abspath(__file__))
        try:
            subprocess.Popen([sys.executable, 'keyrgb-editor-qt.py'], cwd=editor_path)
        except FileNotFoundError:
            subprocess.Popen([sys.executable, 'keyrgb-editor.py'], cwd=editor_path)
    
    def _on_tuxedo_gui_clicked(self, icon, item):
        """Launch uniform color GUI"""
        import os
        gui_path = os.path.dirname(__file__)
        subprocess.Popen([sys.executable, 'src/gui_uniform.py'], cwd=gui_path)
    
    def _on_quit_clicked(self, icon, item):
        """Quit application"""
        self.engine.stop()
        icon.stop()
    
    def _update_icon(self):
        """Update icon based on state"""
        if self.icon:
            if self.is_off:
                color = (64, 64, 64)   # Gray when off
            else:
                color = (255, 0, 128)  # Pink/magenta when on
            self.icon.icon = self._create_icon(color)
    
    def _update_menu(self):
        """Rebuild menu to update checkmarks"""
        if self.icon:
            self.icon.menu = self._build_menu()
    
    def _build_menu(self):
        """Build system tray menu"""
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
        
        return pystray.Menu(*menu_items)
    
    def run(self):
        """Run the tray application"""
        self.icon = pystray.Icon(
            'keyrgb',
            self._create_icon(),
            'KeyRGB',
            self._build_menu()
        )
        
        print("KeyRGB tray app started")
        print(f"Current effect: {self.config.effect}")
        print(f"Speed: {self.config.speed}, Brightness: {self.config.brightness}")
        
        self.icon.run()


def main():
    """Main entry point"""
    try:
        app = KeyRGBTray()
        app.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
