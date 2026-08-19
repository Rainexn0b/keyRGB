from __future__ import annotations

# Compatibility re-export: detection lives in core so tray can use it without
# importing gui (see D13 / 0.30.1 CQ1).
from keyrgb.core.theme.detect import detect_system_prefers_dark

__all__ = ["detect_system_prefers_dark"]
