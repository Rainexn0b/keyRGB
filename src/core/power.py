#!/usr/bin/env python3
"""
Power Management Module
Handles lid close/open, suspend/resume events to control keyboard backlight
"""

from __future__ import annotations

"""Compatibility wrapper for power management.

The implementation now lives in `src.core.power_management`.
"""

from .power_management.manager import PowerManager

__all__ = ["PowerManager"]
from .monitoring.login1_monitoring import monitor_prepare_for_sleep
