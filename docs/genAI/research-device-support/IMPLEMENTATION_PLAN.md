# Keyrgb Hardware Expansion Implementation Plan

Based on Gemini Pro's comprehensive research, here is the prioritized implementation roadmap.

## Summary

The research identified **5 priority tiers** for expansion:
- **Tier 1**: 2 immediate wins (USB ID additions) - 15 minutes work
- **Tier 2**: Universal sysfs backend enhancements - 2-3 hours work
- **Tier 3**: ITE 8297 backend - 1-2 days work
- **Tier 4**: ASUS Aura backend - 2-3 days work
- **Tier 5**: MSI SteelSeries backend - 1-2 days work

**Projected Impact**: Tripling supported devices within one release cycle.

---

## Tier 1: Immediate Wins (Low Effort, High Impact)
**Estimated Time**: 15 minutes
**User Impact**: High (XMG, Tuxedo, Mechrevo 2023-2025 devices)

### Task 1.1: Add ITE 8291 USB Product IDs

**USB IDs to add:**
- `0x6008` - Generic ITE 8291 RGB Controller
- `0x600B` - Newer ITE 8291 (2023+ Tongfang iterations)

**Currently supported:**
- `0xCE00` - ITE 8291 Rev 0.03
- `0x6004` - ITE 8291 (XMG)
- `0x6006` - ITE 8291 (Tuxedo)

**Implementation:**
```python
# File: src/core/backends/ite8291r3.py
# Add to the USB PID list
SUPPORTED_PIDS = [0xce00, 0x6004, 0x6006, 0x6008, 0x600b]
```

**Rationale:** All 8291 variants use identical protocol. Only USB PID differs.

**Devices unlocked:**
- XMG Neo 15/16 (2023+ variants)
- Tuxedo Stellaris 16 Gen 6
- Eluktronics Mech series
- WootBook Ultra 2023+
- Mechrevo laptops

### Task 1.2: Update Device Documentation

**File to update:** `docs/devices/initial.md`

Add the following rows to the USB ID table:

| USB ID | Likely controller family | Notes |
|---|---|---|
| `048d:6008` | ITE 8291 (Generic) | Generic RGB controller, protocol identical to 0x6004 |
| `048d:600b` | ITE 8291 (New) | 2023+ Tongfang iterations, confirmed in hardware logs |

---

## Tier 2: Universal Sysfs Backend (Low Effort, Massive Impact)
**Estimated Time**: 2-3 hours
**User Impact**: Massive (all Tuxedo/Clevo WMI devices, HP Omen, kernel-driver ITE devices)

### Task 2.1: Add multi_intensity Support

**Target:** Tuxedo/Clevo WMI devices with RGB capability

**Sysfs pattern:**
```
/sys/class/leds/rgb:kbd_backlight/multi_intensity
```

**Format:** Space-separated RGB integers (e.g., "255 0 0" for red)

**Implementation logic:**
```python
# File: src/core/backends/sysfs_leds.py
def _supports_multicolor(self) -> bool:
    """Check if device supports multi_intensity (Tuxedo/Clevo RGB)"""
    if self._led_path is None:
        return False
    multi_intensity_path = self._led_path / "multi_intensity"
    return multi_intensity_path.exists()

def set_color(self, color, *, brightness: int):
    """Enhanced color setting with multi_intensity support"""
    if self._supports_multicolor():
        # Write "R G B" format
        r, g, b = color
        multi_intensity_path = self._led_path / "multi_intensity"
        multi_intensity_path.write_text(f"{r} {g} {b}\n")
        self.set_brightness(brightness)
    else:
        # Fallback to existing logic
        # ...
```

### Task 2.2: Add color Attribute Support

**Target:** ITE kernel driver (hid-ite8291r3)

**Sysfs pattern:**
```
/sys/class/leds/*:kbd_backlight/color
```

**Format:** Hex string (e.g., "aabbcc" for red)

**Implementation:**
```python
def _supports_color_attr(self) -> bool:
    """Check if device uses kernel driver with color attribute"""
    if self._led_path is None:
        return False
    color_path = self._led_path / "color"
    return color_path.exists()

def set_color(self, color, *, brightness: int):
    if self._supports_color_attr():
        # Write hex format
        r, g, b = color
        hex_color = f"{r:02x}{g:02x}{b:02x}"
        color_path = self._led_path / "color"
        color_path.write_text(f"{hex_color}\n")
        self.set_brightness(brightness)
```

### Task 2.3: Add zone_colors Support (HP Omen)

**Target:** HP Omen laptops with patched kernel

**Sysfs pattern:**
```
/sys/class/leds/hp_omen::kbd_backlight/zone_colors
```

**Implementation:**
```python
def set_key_colors(self, color_map, *, brightness: int, enable_user_mode: bool = True):
    """Enhanced to support zone-based devices"""
    if self._is_hp_omen_device():
        # HP Omen uses 4-zone RGB
        self._set_hp_omen_zones(color_map, brightness)
    else:
        # Existing per-key logic (which won't work, but won't crash)
        pass

def _is_hp_omen_device(self) -> bool:
    zone_colors_path = self._led_path / "zone_colors"
    return zone_colors_path.exists()
```

### Task 2.4: Expand Sysfs LED Pattern Matching

**Patterns to add:**
```python
# Existing: kbd, keyboard
# Add:
LED_PATTERNS = [
    "kbd",           # Existing
    "keyboard",      # Existing
    "rgb:kbd",       # Tuxedo/Clevo multicolor
    "tuxedo::kbd",   # Tuxedo WMI
    "ite_8291_lb",   # ITE lightbar
    "hp_omen::kbd",  # HP Omen
    "dell::kbd",     # Dell (brightness only)
    "tpacpi::kbd",   # ThinkPad (brightness only)
    "asus::kbd",     # ASUS WMI (brightness only)
    "system76::kbd", # System76
]
```

**Devices unlocked:**
- Tuxedo InfinityBook/Pulse series (all WMI-based devices)
- Clevo laptops with tuxedo-drivers installed
- HP Omen with patched kernels
- Dell, Lenovo, ASUS single-zone devices (brightness control only)

---

## Tier 3: ITE 8297 Backend (Medium Effort, High Impact)
**Estimated Time**: 1-2 days
**User Impact**: High (2024/2025 flagship devices)

### Task 3.1: Create ITE 8297 Backend

**USB ID:** `0x8297` (also reported as `0x5702` for Gigabyte)

**Protocol:** Gigabyte RGB Fusion 2

**Key differences from 8291:**
- Requires initialization/unlock sequence
- Different report IDs and command headers
- Supports "Direct Mode" (continuous streaming) and saved effects
- 64-byte HID packets (vs 8291's potentially different size)

**Implementation approach:**

1. **Create new backend file:** `src/core/backends/ite8297.py`
2. **Base on ite8291r3.py structure** but with protocol changes
3. **Protocol dialect pattern:** Use a "polymorphic" driver approach

```python
# File: src/core/backends/ite8297.py

class Ite8297Backend(KeyboardBackend):
    """ITE 8297 RGB Controller (Gigabyte RGB Fusion 2 protocol)"""
    
    VENDOR_ID = 0x048d
    PRODUCT_IDS = [0x8297, 0x5702]
    
    def _init_device(self):
        """Unlock sequence required for 8297"""
        # Send initialization bytes to unlock controller
        init_sequence = bytes([0xXX, 0xXX, ...])  # From OpenRGB source
        self._dev.write(init_sequence)
    
    def set_color(self, color, *, brightness: int):
        """Fusion 2 packet structure"""
        # Construct 64-byte packet with specific header
        packet = self._build_fusion2_packet(color, brightness)
        self._dev.write(packet)
    
    def _build_fusion2_packet(self, color, brightness):
        """Build Fusion 2 protocol packet"""
        # Implementation based on OpenRGB's Gigabyte controller
        pass
```

### Task 3.2: Add Lightbar Support

**USB Interface:** Often appears as separate interface on same PID

**Detection:** Check USB interface descriptors for lightbar capability

**Implementation:**
```python
def _detect_lightbar(self):
    """Check if device has auxiliary lightbar"""
    # Examine USB interfaces
    # Interface 0: Main keyboard
    # Interface 1: Lightbar (if present)
    interfaces = self._dev.get_interfaces()
    return len(interfaces) > 1

class Ite8297Device(KeyboardDevice):
    def set_key_colors(self, color_map, *, brightness: int, enable_user_mode: bool = True):
        """Support keyboard matrix"""
        # ... keyboard RGB logic
        
    def set_lightbar_color(self, color, *, brightness: int):
        """Support lightbar if present"""
        if not self._has_lightbar:
            return
        # ... lightbar RGB logic
```

**Devices unlocked:**
- XMG Neo 16 E24 (2024)
- XMG Apex 15/17 (2024)
- Tuxedo Stellaris 16 Gen 6
- Eluktronics Hydroc 16 (2024)
- Gigabyte Aorus desktop motherboards

---

## Tier 4: ASUS Aura Backend (Medium Effort, Very High Impact)
**Estimated Time**: 2-3 days
**User Impact**: Very High (largest Linux gaming laptop user base)

### Task 4.1: Create ASUS Aura Backend

**USB IDs:** `0x0b05:1866`, `0x0b05:19b6`, `0x0b05:18a3`

**Protocol:** ASUS Aura (well-documented via rog-core)

**Implementation:**

1. **Create new backend:** `src/core/backends/asus_aura.py`
2. **Reference implementations:**
   - `flukejones/rog-core` (Rust)
   - `asusctl` (daemon)
   - OpenRGB ASUS controller

```python
# File: src/core/backends/asus_aura.py

class AsusAuraBackend(KeyboardBackend):
    """ASUS Aura RGB Controller"""
    
    VENDOR_ID = 0x0b05
    PRODUCT_IDS = [0x1866, 0x19b6, 0x18a3]
    
    def set_color(self, color, *, brightness: int):
        """ASUS Aura packet structure"""
        # Uses control transfers to endpoint 0
        # or dedicated interrupt endpoint
        packet = self._build_aura_packet(color, brightness)
        self._dev.ctrl_transfer(0x21, 0x09, 0x0300, 0x00, packet)
    
    def _build_aura_packet(self, color, brightness):
        """Build Aura protocol packet"""
        # Based on rog-core implementation
        pass
```

**Devices unlocked:**
- ASUS ROG laptops (2020-2025)
- ASUS TUF laptops (if they support Aura)
- Any ASUS laptop with Aura RGB control

**Note:** ASUS laptops may have both USB and WMI controls. USB is preferred for per-key, WMI for zone control.

---

## Tier 5: MSI SteelSeries Backend (Medium Effort, High Impact)
**Estimated Time**: 1-2 days
**User Impact:** High (MSI gaming laptop users)

### Task 5.1: Create MSI SteelSeries Backend

**USB ID:** `0x1770:ff00` (3-Zone), `0x1038:1122` (SteelSeries)

**Protocol:** Hybrid (PS/2 input + USB HID lighting)

**Implementation approach:**

1. **Create new backend:** `src/core/backends/msi_steelseries.py`
2. **Port from:** `Askannz/msi-perkeyrgb` (Python script)
3. **Key differences:**
   - Lighting control via separate USB HID device
   - 64-byte packets defining color regions or per-key maps

```python
# File: src/core/backends/msi_steelseries.py

class MsiSteelSeriesBackend(KeyboardBackend):
    """MSI SteelSeries RGB Controller"""
    
    VENDOR_ID = 0x1770
    PRODUCT_IDS = [0xff00]
    
    def set_color(self, color, *, brightness: int):
        """3-zone or per-key depending on device"""
        # Detect device capabilities
        if self._supports_perkey():
            self._set_perkey_color(color_map)
        else:
            self._set_zone_colors(color)
    
    def _supports_perkey(self):
        """Check if device supports per-key RGB"""
        # MSI has both 3-zone and per-key variants
        pass
```

**Devices unlocked:**
- MSI gaming laptops (2020-2025)
- MSI Creator/Bravo laptops with SteelSeries keyboards

---

## Testing Strategy

### Unit Tests
- Backend detection and selection
- USB ID matching
- Sysfs pattern matching
- Protocol packet construction

### Integration Tests
- **Hardware tests** (opt-in via `KEYRGB_HW_TESTS=1`)
- Mock USB devices for protocol testing
- Mock sysfs interfaces for LED pattern testing

### User Testing
- Request feedback from existing users with newly-supported devices
- GitHub issues for device-specific quirks
- Diagnostic data collection

---

## Implementation Order

**Week 1:**
1. ✅ Tier 1: USB ID additions (15 min)
2. ✅ Tier 2.1: multi_intensity support (1 hour)
3. ✅ Tier 2.2: color attribute support (30 min)
4. ✅ Tier 2.4: Expand sysfs patterns (30 min)
5. ✅ Update documentation (30 min)

**Week 2:**
6. ✅ Tier 2.3: HP Omen zone_colors (1 hour)
7. ✅ Testing and bug fixes (4 hours)
8. ✅ Release v0.6.0 with expanded support

**Week 3-4:**
9. ✅ Tier 3: ITE 8297 backend (2 days)
10. ✅ Testing and refinement (2 days)
11. ✅ Release v0.7.0 with 8297 support

**Week 5-6:**
12. ✅ Tier 4: ASUS Aura backend (3 days)
13. ✅ Testing (2 days)
14. ✅ Release v0.8.0 with ASUS support

**Week 7:**
15. ✅ Tier 5: MSI SteelSeries backend (2 days)
16. ✅ Testing (1 day)
17. ✅ Release v0.9.0 with MSI support

---

## Metrics to Track

1. **Supported Device Count**: Before vs after each tier
2. **GitHub Issues**: Hardware support requests (should decrease)
3. **User Feedback**: Positive confirmations of new devices working
4. **Bug Reports**: Device-specific issues requiring quirks
5. **Performance Impact**: Backend detection time, system resource usage

---

## Risk Mitigation

### Protocol Uncertainty
- **Risk**: New controllers have undocumented quirks
- **Mitigation**: Request diagnostic data from users, start with conservative feature set

### Breaking Changes
- **Risk**: New backend affects existing device support
- **Mitigation**: Keep existing backends unchanged, add new ones, test regression

### User Confusion
- **Risk**: Users don't know if their device is supported
- **Mitigation**: Improve `keyrgb-diagnostics` output, add device to README table

### Over-engineering
- **Risk**: Adding too many backends creates maintenance burden
- **Mitigation**: Stick to verified, well-documented protocols, prioritize quality over quantity

---

## Conclusion

This implementation plan follows the research's priority framework:
1. **Immediate wins** first (Tier 1-2) - maximize impact with minimal effort
2. **Strategic additions** next (Tier 3-4) - expand to high-value ecosystems
3. **Niche support** last (Tier 5) - complete coverage of major vendors

By following this roadmap, Keyrgb can evolve from a beta utility to a comprehensive Linux RGB management tool within 7 weeks, potentially supporting 3-5x more devices.
