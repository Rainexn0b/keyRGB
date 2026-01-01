# Tier 3: ITE 8297 Backend Assessment & Recommendation

**Date**: 2026-01-01
**Status**: Needs Decision - Upstream vs Custom Implementation

---

## Current Situation

- ✅ **Tier 1** (USB ID additions) - Released in v0.6.0
- ✅ **Tier 2** (Sysfs enhancements) - Released in v0.6.0
- 🔄 **Tier 3** (ITE 8297 backend) - Assessment phase

---

## Research Findings from Gemini Pro

### Device Information
- **USB IDs**: `0x048d:0x8297` (primary), `0x048d:0x5702` (Gigabyte variant)
- **Protocol**: Gigabyte RGB Fusion 2
- **Key differences from 8291**:
  - Requires initialization/unlock sequence
  - Different report IDs and command headers
  - 64-byte HID packets
  - Supports "Direct Mode" and saved effects

### Target Devices (High Impact)
- XMG Neo 16 E24 (2024)
- XMG Apex 15/17 (2024)
- Tuxedo Stellaris 16 Gen 6
- Eluktronics Hydroc 16 (2024)
- Gigabyte Aorus desktop motherboards

---

## Implementation Strategy Options

### Option A: Use Upstream Library (Preferred)

**Pros:**
- ✅ Follows established pattern (like ite8291r3-ctl)
- ✅ Minimal maintenance burden
- ✅ Leverages existing testing and bug fixes
- ✅ Easy to update when upstream adds features

**Cons:**
- ❌ Need to find suitable upstream library
- ❌ May need patches for device IDs not yet upstream

**Candidate Libraries:**

1. **liquidctl** (liquidctl.org)
   - Purpose: Liquid cooling and RGB controller control
   - Language: Python
   - Status: Popular, well-maintained
   - ITE 8297 support: **Unknown** - needs verification
   - Integration: Add to install.sh with pip install
   - Patching: Similar approach to ite8291r3-ctl

2. **OpenRGB** (openrgb.org)
   - Purpose: Comprehensive RGB control
   - Language: C++ (not Python)
   - Status: Most comprehensive
   - ITE 8297 support: ✅ Yes (Gigabyte controller)
   - Integration: NOT suitable (wrong language, library approach)

3. **ite8291r3-ctl** (pobrn/ite8291r3-ctl)
   - Purpose: ITE 8291/8297 controller control
   - Language: Python
   - Status: Actively maintained
   - ITE 8297 support: **Unknown** - needs verification
   - Integration: Already used! Just check if 8297 supported

### Option B: Custom Implementation (Fallback)

**Pros:**
- ✅ Full control over implementation
- ✅ Can optimize specifically for Keyrgb's needs
- ✅ No dependency on upstream release cycle

**Cons:**
- ❌ High maintenance burden
- ❌ Protocol reverse-engineering required
- ❌ No community testing/bug fixes
- ❌ Violates project's preference for upstream

---

## Recommended Approach

### Phase 1: Investigate Upstream Options (1-2 hours)

**Task 1.1: Check ite8291r3-ctl for 8297 support**
```bash
# Check if upstream already supports 0x8297
git clone https://github.com/pobrn/ite8291r3-ctl.git /tmp/ite8297-check
grep -r "0x8297\|0x5702" /tmp/ite8297-check
```

**If supported:**
- Simply add PIDs to existing backend (like Tier 1)
- No new backend needed
- Estimated time: **15 minutes**

**If not supported:**
- Check if there's an open PR/issue for 8297
- Consider contributing to upstream
- Decide between custom implementation vs. wait

**Task 1.2: Check liquidctl for 8297 support**
```bash
pip install liquidctl
python3 -c "import liquidctl; print(dir(liquidctl))"
# Check if any ITE 8297 controllers are listed
```

**If supported:**
- Add liquidctl to requirements.txt
- Create wrapper backend (like ite8291r3.py)
- Patch device IDs in install.sh if needed
- Estimated time: **4-6 hours**

**If not supported:**
- Consider contributing to liquidctl
- Proceed to custom implementation

### Phase 2: Decision Point

#### Path A: Upstream Available (Quick Win)
1. **If ite8291r3-ctl supports 8297:**
   - Add 0x8297 to `_FALLBACK_USB_IDS`
   - Update documentation
   - Test with device (if available)
   - Release v0.6.1

2. **If liquidctl supports 8297:**
   - Create `src/core/backends/ite8297.py` wrapper
   - Add liquidctl to install.sh
   - Update requirements.txt
   - Test with device (if available)
   - Release v0.6.1

#### Path B: Custom Implementation (Medium Effort)
1. **Create `src/core/backends/ite8297_custom.py`:**
   - Base on ite8291r3.py structure
   - Implement Gigabyte RGB Fusion 2 protocol
   - Reference OpenRGB source code for packet structure
   - Estimated time: **1-2 days**

2. **Add to backend registry:**
   - Register with appropriate priority
   - Probe for USB IDs 0x8297, 0x5702

3. **Testing:**
   - Unit tests for packet construction
   - Integration tests with mock USB devices
   - User testing with real devices

4. **Documentation:**
   - Update device mapping
   - Add implementation notes
   - Create troubleshooting guide

---

## Implementation Details (If Custom)

### File Structure

```
src/core/backends/ite8297_custom.py
├── Ite8297Backend (KeyboardBackend wrapper)
│   ├── name: "ite8297-custom"
│   ├── priority: 95 (lower than 8291's 100)
│   ├── is_available()
│   ├── probe()
│   ├── get_device()
│   ├── dimensions()
│   ├── effects()
│   └── colors()
└── Ite8297Device (KeyboardDevice)
    ├── set_color()
    ├── set_key_colors()
    ├── set_brightness()
    └── set_effect()
```

### Protocol Implementation (Based on OpenRGB)

**Reference:** OpenRGB's `KeyboardITE8297Controller.cpp`

**Key Packet Structure:**
```python
# Gigabyte RGB Fusion 2 packet format
HEADER = bytes([0x...])  # Specific header bytes
REPORT_ID = 0x...  # Report ID for commands
PACKET_SIZE = 64  # 64-byte packets

def _build_fusion2_packet(self, command, data):
    """Build 64-byte Fusion 2 packet"""
    packet = bytearray(PACKET_SIZE)
    packet[0] = REPORT_ID
    packet[1] = command
    # Add data...
    return bytes(packet)
```

**Initialization Sequence:**
```python
def _init_device(self):
    """Send unlock sequence to 8297"""
    init_bytes = bytes([0x..., 0x..., ...])  # From OpenRGB
    self._dev.write(init_bytes, timeout=1000)
    # May need to wait for response
```

---

## Install.sh Integration

### Pattern Follows ite8291r3-ctl Approach

```bash
# If using liquidctl:
echo "📦 Installing liquidctl library (upstream)..."
pip3 install --user liquidctl

# If using custom implementation:
# No install.sh changes needed (backend is part of Keyrgb)
# But may need to add USB device permissions to udev rules
```

### Udev Rules Update

If ITE 8297 requires different udev rules:
```bash
# Add to udev/99-ite8291-wootbook.rules
# For 0x8297:
SUBSYSTEM=="usb", ATTR{idVendor}=="048d", ATTR{idProduct}=="8297", MODE="0666"
```

---

## Timeline Recommendation

### Week 1 (Immediate)
- **Day 1-2**: Investigate upstream options (ite8291r3-ctl, liquidctl)
- **Day 3**: Make decision on implementation path
- **Day 4-5**: Implement chosen approach

### Week 2 (Testing & Release)
- **Day 1-2**: Testing (unit, integration, user if possible)
- **Day 3**: Bug fixes and refinement
- **Day 4**: Documentation updates
- **Day 5**: Release v0.6.1 or v0.7.0

---

## Risk Assessment

### High Risk Areas
1. **Protocol Uncertainty**
   - Risk: Undocumented quirks in Fusion 2 protocol
   - Mitigation: Reference OpenRGB implementation, conservative feature set

2. **Hardware Availability**
   - Risk: No device for testing
   - Mitigation: Mock USB devices for testing, request user feedback

3. **Upstream Dependency**
   - Risk: Upstream doesn't support 8297 yet
   - Mitigation: Custom implementation as fallback

### Low Risk Areas
1. **Integration with existing architecture**
   - Risk: Breaking existing functionality
   - Mitigation: New backend, separate from existing

2. **Install.sh modifications**
   - Risk: Breaking installation
   - Mitigation: Follow existing patterns, test on clean install

---

## Decision Matrix

| Factor | Upstream (ite8291r3-ctl) | Upstream (liquidctl) | Custom |
|---|---|---|---|
| **Effort** | 15 min | 4-6 hours | 1-2 days |
| **Maintenance** | Low (upstream) | Low (upstream) | High (custom) |
| **Testing** | Upstream-tested | Upstream-tested | Requires user testing |
| **Upstream Support** | TBD | TBD | N/A |
| **Protocol Knowledge** | High (ITE focused) | Medium (general RGB) | Medium (reverse-engineer) |
| **Integration** | Trivial (already used) | Easy (pip install) | Medium (new code) |

---

## Recommendation

### Primary Path: Check ite8291r3-ctl First

**Rationale:**
1. Already integrated with Keyrgb
2. Maintained by same developer (pobrn)
3. Likely to add 8297 support eventually
4. If supported, 15-minute implementation
5. If not supported, can contribute back

### Fallback Path: liquidctl

**Rationale:**
1. Python-based (fits Keyrgb stack)
2. Well-maintained project
3. Supports many RGB controllers
4. May already have ITE 8297

### Last Resort: Custom Implementation

**Rationale:**
1. Only if neither upstream option works
2. High maintenance burden
3. Better to contribute to upstream instead

---

## Next Steps

1. **Investigate ite8291r3-ctl** for 8297 support
2. **Check liquidctl** for ITE 8297
3. **Make decision** based on findings
4. **Implement** chosen approach
5. **Test** thoroughly
6. **Document** clearly
7. **Release** with clear notes

---

## Conclusion

Tier 3 (ITE 8297 backend) should proceed with:
1. **Upstream-first approach** (follows project philosophy)
2. **Custom implementation as fallback** (ensures completion)
3. **Focus on maintainability** (reduces long-term burden)
4. **Clear documentation** (helps future contributors)

The 15-minute implementation (if ite8291r3-ctl supports 8297) is ideal. The 1-2 day custom implementation is acceptable as a last resort.

**Estimated Impact**: High (supports 2024/2025 flagship devices)
**Estimated User Growth**: 20-40% increase in device coverage
**Recommended Release**: v0.6.1 (quick win) or v0.7.0 (custom implementation)
