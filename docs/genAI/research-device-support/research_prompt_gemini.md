# Keyrgb Hardware Expansion Research Prompt

Copy the prompt below and paste it to Gemini Pro (research mode) to conduct comprehensive research for expanding Keyrgb's hardware support.

---

## Research Prompt for Gemini Pro

**Role**: You are assisting a Linux RGB keyboard control project called Keyrgb expand its hardware support efficiently. We need to identify "big wins" - devices and controllers that can be immediately supported with minimal code changes.

## Context

Keyrgb is a Linux tray application for laptop keyboard RGB control. It currently:
- Supports ITE 8291/8291R3 controllers via USB (vendor ID 0x048d, product IDs: ce00, 6004, 6006, 600b)
- Has a sysfs LEDs backend for generic keyboard backlight control
- Targets Tongfang rebranded laptops (WootBook, Tuxedo, XMG, LaptopWithLinux, etc.)
- Uses a multi-backend architecture with auto-detection
- Is in beta (v0.5.1) and actively maintained

**GitHub**: https://github.com/Rainexn0b/keyRGB

## Research Objectives

Find hardware that can be immediately supported through:
1. **Direct compatibility** with existing backends (same controllers, different USB IDs)
2. **Minimal backend additions** (new controllers with similar protocols)
3. **High-impact targets** (popular devices with many users)

## Specific Research Tasks

### Task 1: ITE Controller Expansion
Research ITE 8291/829x/8297 controllers and identify:
- All known USB product IDs for ITE keyboard controllers (vendor 0x048d)
- Specific laptop models that use each variant
- Whether they use the same protocol as 8291R3 or need adjustments
- Matrix dimensions (rows x columns) for each variant
- Any known quirks or differences in protocol

### Task 2: Tongfang Chassis Inventory
Research Tongfang chassis families and identify:
- All major Tongfang chassis released 2023-2025
- Which brands rebrand each chassis (WootBook, Tuxedo, XMG, Schenker, etc.)
- Which chassis use ITE vs other RGB controllers
- Known RGB capabilities per chassis (per-key, zone, single-color)
- USB IDs and sysfs LED paths where available

### Task 3: Alternative "Big Win" Controllers
Research other laptop RGB controllers that would be high-impact:
- Controllers commonly used in popular Linux gaming laptops
- OpenRGB device list - identify the most requested laptop RGB devices
- Controllers with open-source drivers or documented protocols
- Prevalence by user count/popularity (not just number of device models)

### Task 4: Sysfs LED Patterns
Research sysfs-based keyboard backlight control:
- Common LED class device names for RGB backlights
- Which laptops expose keyboard via sysfs vs require USB communication
- Patterns in `/sys/class/leds/` naming (tuxedo, ideapad, asus_wmi, etc.)
- Whether sysfs provides full color control or just brightness

### Task 5: Reference Projects
Analyze existing open-source projects for device data:
- OpenRGB: Extract all ITE-based laptop entries
- ite8291r3-ctl: Check their full product ID list
- Tuxedo control center tools: Device detection patterns
- Any other Linux keyboard RGB tools with device databases

## Output Format

For each finding, provide:

1. **Controller/Family Name**
2. **USB Vendor:Product ID** (if applicable)
3. **Laptop Models** (specific brands and models confirmed)
4. **Controller Protocol** (matches ITE8291R3, similar variant, or different)
5. **Support Effort** (drop-in config change, minor backend tweak, or major new backend)
6. **User Impact** (estimated based on popularity/availability)
7. **Confidence** (confirmed in documentation, inferred, or speculative)
8. **Source Links** (where you found this information)

## Priority Framework

Rank findings by:
1. **High Impact + Low Effort** (immediate wins - same controller, new USB IDs)
2. **High Impact + Medium Effort** (similar protocol, needs new backend)
3. **Medium Impact + Low Effort** (niche but easy to add)
4. **Low Impact** (regardless of effort)

## Key Questions to Answer

1. Are there any laptop models using ITE controllers that aren't in the current 048d:ce00/6004/6006/600b list?
2. Which Tongfang chassis use non-ITE controllers that are still worth supporting?
3. What are the most common sysfs LED patterns we should add to the sysfs backend?
4. Are there any popular gaming laptops (non-Tongfang) using well-documented RGB controllers?
5. What devices do users most frequently request on OpenRGB or similar projects?

## Constraints

- Focus on laptops (not desktop keyboards)
- Prioritize Linux-compatible devices
- Prefer devices with existing open-source drivers or documentation
- Avoid proprietary/undocumented protocols
- Target devices available 2023-2025 (modern hardware)
- Ignore devices already well-supported by vendor tools (if they work on Linux)

## Final Deliverable

Provide:
1. **Ranked list** of expansion opportunities with effort/impact scores
2. **USB ID mappings** ready to drop into Keyrgb
3. **Sysfs LED patterns** to add to backend
4. **Controller families** that need new backends with protocol notes
5. **Sources** for verification (links, documentation, code repos)

We need actionable data to immediately expand support without over-engineering. Focus on confirmed, verifiable information over speculation.

---
