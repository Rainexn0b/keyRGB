from __future__ import annotations

import threading
import time


def start_hardware_polling(tray) -> None:
    """Poll keyboard hardware state to detect physical button changes."""

    def poll_hardware():
        last_brightness = None
        last_off_state = None

        while True:
            try:
                with tray.engine.kb_lock:
                    current_brightness = tray.engine.kb.get_brightness()
                    current_off = tray.engine.kb.is_off()

                if current_brightness > 0:
                    tray._last_brightness = current_brightness

                if current_brightness == 0:
                    current_off = True

                if last_brightness is not None and current_brightness != last_brightness:
                    if tray._power_forced_off and current_brightness == 0:
                        last_brightness = current_brightness
                        last_off_state = current_off
                        continue

                    tray.config.brightness = current_brightness

                    if current_brightness == 0:
                        tray.is_off = True
                    elif last_brightness == 0:
                        tray.is_off = False

                    tray._update_icon()
                    tray._update_menu()

                elif last_off_state is not None and current_off != last_off_state:
                    if tray._power_forced_off and current_off:
                        last_brightness = current_brightness
                        last_off_state = current_off
                        continue

                    tray.is_off = current_off
                    tray._update_icon()
                    tray._update_menu()

                last_brightness = current_brightness
                last_off_state = current_off

            except Exception:
                pass

            time.sleep(2)

    threading.Thread(target=poll_hardware, daemon=True).start()
