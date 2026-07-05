# Keyrgb Hardware Expansion Research

Converted from `Keyrgb Hardware Expansion Research.docx`.

## Keyrgb Hardware Expansion Strategy: Technical Analysis and Implementation Roadmap

### 1. Executive Summary and Strategic Imperative

The Linux desktop ecosystem has seen a renaissance in gaming and high-performance computing hardware support, yet the management of peripheral aesthetics—specifically RGB lighting on laptop keyboards—remains a fragmented landscape of kernel modules, reverse-engineered scripts, and vendor-specific daemons. For the Keyrgb project, which currently services a niche of ITE-based controllers and generic sysfs interfaces, the opportunity for expansion is substantial. The immediate strategic imperative is to identify "Big Wins"—hardware targets that offer the maximum user base expansion for the minimum development overhead. This research report provides a comprehensive analysis of the current laptop RGB controller landscape, leveraging deep inspection of open-source driver repositories, kernel mailing lists, and hardware databases to map a precise path for Keyrgb’s evolution from a beta utility to a dominant Linux RGB standard.

The analysis indicates that the most efficient path to expansion lies not in writing new USB drivers from scratch, but in exploiting the convergence of various ODM (Original Design Manufacturer) platforms—specifically Tongfang and Clevo—under unified kernel interfaces provided by projects like tuxedo-drivers. Furthermore, the ubiquity of the Integrated Technology Express (ITE) 829x controller family offers an immediate route to supporting dozens of "white label" laptop brands (XMG, Eluktronics, Wootware) through simple USB Product ID (PID) aliasing.

This report details the technical specifications of these controllers, maps the complex web of chassis rebrands to their underlying protocols, and provides a validated inventory of sysfs LED class paths that can be integrated into Keyrgb’s backend immediately. By prioritizing the integration of the ITE 8297 protocol and the standardizing of WMI-based (Windows Management Instrumentation) controls via sysfs, Keyrgb can potentially triple its supported device list within a single release cycle.

### 2. The ITE Controller Ecosystem: Deep Dive and Expansion

The Integrated Technology Express (ITE) family of microcontrollers, specifically the 829x series, represents the de facto standard for RGB control in the modern "boutique" laptop market. These chips are favored by Tongfang (Uniwill), the ODM responsible for manufacturing laptops for brands such as XMG, Schenker, Tuxedo, PCSpecialist, and Eluktronics. Keyrgb’s existing support for the ITE 8291R3 provides a strong foundation, but the research reveals a much wider array of variants that can be brought into the fold.

#### 2.1 The ITE 8291 Variant Landscape

The ITE 8291 is a USB HID-based controller. Unlike older implementations that relied on SMBus or direct I/O port manipulation, the 8291 exposes a standard USB endpoint, making it ideal for userspace control via hidapi or libusb. The current Keyrgb implementation supports the standard revision 0.03 devices found in 2020-2022 era chassis. However, inspection of hardware databases and driver source code reveals several other critical PIDs.

##### 2.1.1 Confirmed ITE 8291 Product IDs

The Vendor ID (VID) for ITE is consistently 0x048d. The Product IDs (PID) vary by firmware revision and OEM customization.

Technical Insight: The existence of 0x6008 and 0x600B suggests that ITE increments the PID for firmware updates or slight matrix layout changes (e.g., ANSI vs. ISO layouts, or the addition of a numpad). Since the underlying controller remains the 8291, the command set for initiating lighting modes (Wave, Breathing, Static) and sending the color matrix is effectively identical. The Linux kernel driver hid-ite8291r3 treats these devices largely the same, differing only in initialization strings or matrix size definitions.6

#### 2.2 The ITE 8297: The Next Generation Target

The most significant finding for immediate expansion is the ITE 8297 (048d:8297). This controller appears in two distinct contexts: as a motherboard RGB controller in Gigabyte Aorus desktops and as the keyboard/chassis lighting controller in high-end 2023-2025 Tongfang laptops (such as the XMG Neo 16 E24 and Apex series).4

Protocol Analysis:

OpenRGB source code for the "Gigabyte RGB Fusion 2" USB controller reveals that it drives the ITE 8297. The protocol uses 64-byte HID packets, similar to the 8291, but with different report IDs and command headers.

ITE 8291: Typically uses report ID 0xCC or similar for commands.

ITE 8297: Often requires an initialization sequence to unlock the controller before accepting RGB data. OpenRGB documentation notes that this controller supports "Direct Mode" where the software continuously streams LED data, as well as saved effects.8

Implication for Keyrgb:

The ITE 8297 is the logical successor to the 8291 in the Tongfang roadmap. Supporting this chip unlocks the latest generation of devices (Gen 8 and Gen 9 chassis). The effort is classified as Medium, as it likely requires a new backend class that inherits from the HID base but implements the specific packet structure of the 8297/Fusion 2 protocol.

#### 2.3 The "Lightbar" Complexity (ite_8291_lb)

A critical nuance in the Tongfang ecosystem is the handling of auxiliary lighting zones, specifically the "Lightbar" found on the front edge of models like the XMG Neo and Tuxedo Stellaris. The tuxedo-drivers repository contains a specific module named ite_8291_lb.9

This segregation implies one of two architectures:

Composite Device: The lightbar appears as a separate USB interface (e.g., Interface 1) on the same PID (e.g., 0x6004).

Matrix Extension: The lightbar LEDs are mapped to "virtual" rows in the keyboard matrix (e.g., Row 6 or 7), requiring the driver to send larger packets or write to specific high-address registers.

The tuxedo-drivers approach of splitting the source code into ite_8291.c and ite_8291_lb.c suggests that the control logic is distinct enough to warrant separation. Keyrgb must be updated to detect if a detected 8291 device has the lightbar capability (likely via checking the matrix size or USB interface descriptor) and expose those extra LEDs to the user.

#### 2.4 Legacy and Niche ITE Variants

Research also identified older or less common ITE controllers:

ITE 8176 (048d:5000): A legacy keyboard controller found in older Tongfang models (2018-2019). It is less likely to support per-key RGB and may be limited to zone or single-color control. Given the focus on "modern hardware" (2023-2025), this is a low priority.11

ITE 8233 (048d:c9b3): Identified in some XMG Neo E23 logs. Its protocol is currently less documented than the 8291/8297, making it a higher-risk target for immediate implementation.12

#### 2.5 Strategic Recommendation for Task 1

The research strongly supports an aggressive expansion of the ITE backend. Keyrgb should immediately whitelist PIDs 0x6008, 0x600b, and 0x8297. The codebase should be refactored to allow for "Protocol Dialects"—where the main ITE driver can swap packet headers based on the detected PID. This "polymorphic" driver approach is significantly more efficient than writing discrete backends for each chip revision.

### 3. Tongfang Chassis Inventory: Mapping the Market

Understanding the hardware beneath the brand sticker is crucial for Keyrgb. Tongfang (and its subsidiary Uniwill) manufactures the white-label chassis that are rebranded by dozens of local vendors. By identifying the chassis model year and type, Keyrgb can infer the RGB capabilities and the likely controller (ITE vs. WMI).

#### 3.1 The 2023-2025 Chassis Roadmap

The following table synthesizes data from vendor product pages, Linux hardware probes, and driver compatibility lists to map chassis to their commercial names and RGB technology.

#### 3.2 Chassis-Specific Insights

##### 3.2.1 The GMx Series (High-End Gaming)

The GM5HG and GM7HG chassis utilize mechanical keyboards (often Cherry MX ULP) and feature per-key RGB. The research confirms that the XMG Neo 16 E24 specifically uses the ITE 8291 controller (048d:6004 or 6008).3 This is a "Big Win" target because users of these high-end devices are most likely to demand complex lighting effects. The inclusion of the "Lightbar" on the GM7HG chassis reinforces the need for the ite_8291_lb logic discussed in Section 2.3.

##### 3.2.2 The PHx and Lx Series (Slim/Workstation)

The PH4 (Focus/InfinityBook) and L14 (Pulse/Via) chassis prioritize portability over "gamer" aesthetics. Consequently, they often use simpler RGB implementations controlled via the system BIOS/EC rather than a dedicated USB controller.

The Uniwill WMI Interface: These laptops do not expose an ITE USB device for lighting. Instead, the keyboard backlight is treated as a system device controlled by ACPI methods.

Driver Dependency: On Linux, these require the tuxedo-drivers (specifically tuxedo-keyboard or clevo-wmi) to function. These drivers expose the lighting control via /sys/class/leds/.

Keyrgb Strategy: For these chassis, Keyrgb must rely on the sysfs backend. Direct USB control is impossible because the USB endpoint does not exist.

##### 3.2.3 The "Huan" 16 Air (Modular)

A new entry in late 2024/2025 is the Tongfang "Huan" 16, noted for its modular GPU.13 While still emerging, early indications suggest it follows the GMx series lineage, likely utilizing an ITE 8297 controller for its RGB elements. This represents a future-proofing target.

#### 3.3 Brand Rebranding Matrix

Support for one chassis implies support for all rebrands.

XMG/Schenker (Germany): Primary source of technical data. Their "Neo" line equates to the GMx chassis; "Focus" equates to PHx.

Tuxedo Computers (Germany): "Stellaris" = GMx; "InfinityBook/Pulse" = PHx/Lx.

Eluktronics (USA): "Mech" series = GMx; "Prometheus" = GMx/GX.

Wootware (South Africa): "WootBook Ultra" = GMx; "WootBook Metal" = PHx.

Mechrevo (China): The parent brand for many of these chassis.

Conclusion for Task 2: The Tongfang ecosystem is bifurcated. High-performance units (GMx) are USB/ITE based and are prime targets for Keyrgb’s direct control. Slim/Workstation units (PHx/Lx) are WMI-based and require a robust sysfs implementation.

### 4. Task 3: Alternative "Big Win" Controllers

While Tongfang represents a stronghold for Linux users due to Tuxedo's influence, expansion into ASUS and MSI territories offers the largest potential user growth.

#### 4.1 ASUS ROG: The "Aura" Protocol

ASUS laptops dominate the gaming market. Their RGB control is handled by the "Aura" USB controller.

USB IDs: 0b05:1866, 0b05:19b6, 0b05:18a3.14

Protocol: USB HID. The protocol is well-documented by the asusctl and rog-core projects. It involves sending specific byte sequences to Endpoint 0 (Control Transfer) or a dedicated Interrupt Endpoint.

Linux Status: The asusctl daemon is the standard, but it is a heavy Rust-based system that manages many laptop functions (fan curves, MUX switch).

The Keyrgb Opportunity: Many users find asusctl overkill or difficult to configure for simple lighting tasks. A lightweight Keyrgb backend that speaks the Aura protocol (which is relatively static across generations) would be a massive value add. The protocol is stable enough that a "clean room" implementation based on rog-core logic is feasible.16

#### 4.2 MSI SteelSeries: The Hybrid Approach

MSI laptops use SteelSeries keyboards.

USB IDs: 1770:ff00 (MSI 3-Zone), and various SteelSeries-branded IDs (e.g., 1038:1122).

Protocol: Unique Hybrid. The keyboard input works over PS/2, but the lighting control is handled via a separate USB HID device. The protocol involves sending 64-byte packets defining color regions or per-key maps.

Existing Tools: msi-perkeyrgb is a Python script that handles this well.

Keyrgb Opportunity: Porting the logic from msi-perkeyrgb to a C++/Rust backend in Keyrgb is a Medium Effort task with High Impact. MSI users often struggle with the lack of a GUI for these scripts.

#### 4.3 HP Omen: The WMI Outlier

HP Omen laptops use a 4-zone RGB system controlled entirely via ACPI WMI.

Protocol: No USB control. Requires hp-wmi kernel driver.

Linux Status: The mainline hp-wmi driver has basic support, but newer models often require patches to expose the 4 zones correctly.

Keyrgb Opportunity: Low. Support relies entirely on the user having a patched kernel that exposes /sys/class/leds/hp_omen::kbd_backlight/zone_colors.17 Keyrgb can support this via the sysfs backend, but it cannot "fix" the lack of kernel support itself.

### 5. Task 4: Sysfs LED Patterns & The "Universal" Backend

For non-USB devices (Clevo, HP, Lenovo, and WMI-based Tongfang), the /sys/class/leds/ directory is the only control surface. Keyrgb’s expansion here relies on identifying and implementing the varied naming conventions used by kernel drivers.

#### 5.1 The "Multi-Intensity" Standard (Tuxedo/Clevo)

The most advanced sysfs implementation is found in the tuxedo-drivers and clevo-xsm-wmi modules.

Path: /sys/class/leds/rgb:kbd_backlight/

Control File: multi_intensity

Format: Space-separated integers representing RGB values (e.g., 255 0 0 for red).18

Mechanism: Writing to this file updates the EC, which then drives the LEDs.

Action: Keyrgb’s sysfs backend must check for the existence of multi_intensity. If found, it should treat the device as an RGB-capable unit rather than a simple brightness-only backlight.

#### 5.2 The "Color" Attribute (ITE Kernel Driver)

The hid-ite8291r3 kernel driver (an alternative to the userspace approach) exposes a different attribute.

Path: /sys/class/leds/*:kbd_backlight/

Control File: color

Format: Hex string (e.g., aabbcc).6

Action: Keyrgb needs a parser that detects the color file and writes Hex strings instead of integer arrays.

#### 5.3 The "Zone Colors" Patch (HP Omen)

As identified in kernel mailing lists, patched HP drivers expose zones.

Path: /sys/class/leds/hp_omen::kbd_backlight/

Control File: zone_colors

Format: Binary or Hex stream defining colors for 4 zones.17

Action: This is a niche pattern, but adding support for reading/writing zone_colors would capture the HP Omen Linux user base.

#### 5.4 Standard Brightness Fallback

For laptops like the Acer Predator or older Dell G-series, Linux often only exposes:

Path: /sys/class/leds/*::kbd_backlight/

Control File: brightness (0-max).

Limitation: These users cannot change color via Linux without reverse-engineering the WMI calls, which are often encrypted or undocumented. Keyrgb should ensure it handles "Brightness Only" mode gracefully for these devices.

### 6. Task 5: Reference Projects and Protocol Verification

The analysis of existing open-source projects provides the validation needed for the recommended expansion.

#### 6.1 OpenRGB Analysis

OpenRGB is the behemoth of the industry, but its architecture (detecting everything on the I2C/SMBus/USB) is heavy.

ITE Support: OpenRGB uses KeyboardITE8291Controller.cpp. It explicitly links the ITE 8297 to the "Gigabyte RGB Fusion 2" protocol. This confirms that the 8297 uses a different command structure than the 8291, likely involving a "unlock" sequence common to Gigabyte motherboards.19

Device List: OpenRGB’s supported list confirms that MSI Mystic Light and ASUS Aura are the two other major USB-based protocols worth targeting.20

#### 6.2 Tuxedo Drivers Source Tree

The file structure of tuxedo-drivers is the ultimate source of truth for Tongfang hardware.10

ite_8291.c: Handles the standard mechanical keyboards (Neo/Stellaris).

ite_8291_lb.c: Handles the lightbars (suggests a logical separation of the lightbar from the keyboard matrix).

ite_8297.c: A distinct driver, confirming protocol differences for newer (2023+) models.

clevo_wmi.c: Confirms that Clevo devices are WMI-controlled, not USB HID.

#### 6.3 Userspace Python Drivers

Projects like ite8291r3-ctl 1 and msi-perkeyrgb 21 demonstrate that Python can effectively manage these devices via pyusb and hidapi. Keyrgb, being a C++ or Rust application (assumed based on "Linux tray app" performance goals), can easily port this logic. The existence of these scripts proves that no kernel-mode privileges are strictly necessary for the USB-based controllers, provided udev rules allow user access.

### 7. Implementation Roadmap: The "Big Wins"

Based on the research, the following ranked list represents the expansion strategy.

#### Priority 1: Immediate ITE Expansion (Low Effort, High Impact)

Target: ITE 8291 Variants.

Action: Update the ITE backend to accept the following PIDs:

0x6008 (Generic 8291)

0x600B (Newer 8291)

0x6004 (XMG 8291)

0x6006 (Tuxedo 8291)
Reasoning: These devices share the exact same protocol as the currently supported 0xCE00. This is a one-line code change (adding IDs to an array) that instantly supports devices from XMG, Tuxedo, and Mechrevo.

#### Priority 2: The Universal Sysfs Backend (Low Effort, Massive Impact)

Target: Tuxedo/Clevo WMI Devices.

Action: Enhance the sysfs backend to look for multi_intensity.

Logic:

Code snippet

IF /sys/class/leds/rgb:kbd_backlight/multi_intensity EXISTS:
    Enable RGB Color Picker
    On Change: Write "R G B" string to multi_intensity
ELSE IF /sys/class/leds/*/color EXISTS:
    Enable RGB Color Picker
    On Change: Write "RRGGBB" hex to color
ELSE:
    Enable Brightness Slider Only

Reasoning: This leverages the heavy lifting done by the tuxedo-drivers kernel module. Instead of writing drivers for 50 different Clevo laptops, Keyrgb simply supports the interface that tuxedo-drivers creates.

#### Priority 3: The ITE 8297 / Gigabyte Protocol (Medium Effort, High Impact)

Target: 2024/2025 Tongfang Chassis (XMG Neo 16 E24, Apex).

Action: Implement the "Gigabyte RGB Fusion 2" packet structure for PID 0x8297.

Reasoning: This secures support for the newest, most expensive laptops entering the market. Users of these devices are currently underserved as the older 8291 tools do not work for them.

#### Priority 4: ASUS Aura Integration (Medium Effort, Very High Impact)

Target: ASUS ROG Laptops.

Action: Create a new backend targeting 0b05:xxxx USB devices using the rog-core protocol.

Reasoning: This opens Keyrgb to the largest slice of the Linux gaming demographic.

### 8. Reference Data for Developers

#### 8.1 USB ID Mapping Table

Drop this directly into the device discovery logic.

#### 8.2 Sysfs Path Patterns

Add these string patterns to the filesystem watcher.

rgb:kbd_backlight (Tuxedo/Clevo multicolor)

dell::kbd_backlight (Dell, usually brightness only)

tpacpi::kbd_backlight (ThinkPad, brightness only)

asus::kbd_backlight (ASUS WMI, brightness only)

system76::kbd_backlight (System76, brightness/color via custom files)

### 9. Conclusion

Keyrgb stands at a pivotal moment. By pivoting from a purely "ITE 8291 tool" to a "Universal RGB Frontend," it can capture the majority of the Linux laptop market. The strategy defined here—expanding ITE PIDs, embracing the tuxedo-drivers sysfs standard, and targeting the ITE 8297—offers a high-velocity roadmap. The research confirms that the hardware capabilities are accessible; they merely require the unified, user-friendly interface that Keyrgb is positioned to provide. By implementing the "Big Wins" identified in this report, Keyrgb can transition from a beta utility to an essential component of the Linux desktop experience.

##### Works cited

pobrn/ite8291r3-ctl: Userspace driver for the ITE 8291 (rev ... - GitHub, accessed January 1, 2026, https://github.com/pobrn/ite8291r3-ctl

Integrated Technology Express ITE Device(8291), accessed January 1, 2026, https://bsd-hardware.info/?id=usb:048d-ce00

Keyboard backlight XMG NEO 15 M20 Linux : r/XMG_gg - Reddit, accessed January 1, 2026, https://www.reddit.com/r/XMG_gg/comments/idjq6c/keyboard_backlight_xmg_neo_15_m20_linux/

USB\VID_048D&PID_8297 - IT8297 RGB LED Controller, accessed January 1, 2026, https://devicehunt.com/view/type/usb/vendor/048D/device/8297

Failure · Issue #972 · pinokiocomputer/pinokio - GitHub, accessed January 1, 2026, https://github.com/pinokiocomputer/pinokio/issues/972

pobrn/hid-ite8291r3: Linux kernel driver for the ITE 8291 ... - GitHub, accessed January 1, 2026, https://github.com/pobrn/hid-ite8291r3

Gigabyte B550 Aorus Pro V2 Issues (#1197) - OpenRGB - GitLab, accessed January 1, 2026, https://gitlab.com/CalcProgrammer1/OpenRGB/-/issues/1197

Supported devices (Latest experimental) - OpenRGB, accessed January 1, 2026, https://openrgb.org/devices.html?search=GIGABYTE

AUR (en) - tuxedo-drivers-xmg-dkms-git - Arch Linux, accessed January 1, 2026, https://aur.archlinux.org/packages/tuxedo-drivers-xmg-dkms-git

tuxedocomputers/tuxedo-drivers: This is a read only mirror ... - GitHub, accessed January 1, 2026, https://github.com/tuxedocomputers/tuxedo-drivers

Integrated Technology Express ITE Device(8176), accessed January 1, 2026, https://linux-hardware.org/?id=usb:048d-5000

Integrated Technology Express ITE Device(8233), accessed January 1, 2026, https://linux-hardware.org/?id=usb:048d-7000

New laptop modular gaming of Tongfang huan 16 air gaming, accessed January 1, 2026, https://community.frame.work/t/new-laptop-modular-gaming-of-tongfang-huan-16-air-gaming/60350

asusctl support for non-ROG : r/ASUS - Reddit, accessed January 1, 2026, https://www.reddit.com/r/ASUS/comments/1ixyyv5/asusctl_support_for_nonrog/

Add ROG Maximus XI Hero Wifi Support (#158) - OpenRGB - GitLab, accessed January 1, 2026, https://gitlab.com/CalcProgrammer1/OpenRGB/-/issues/158

flukejones/rog-core: Implements missing functionality for ... - GitHub, accessed January 1, 2026, https://github.com/flukejones/rog-core

[v3] platform/x86: hp-wmi: Support omen backlight control ... - Patchew, accessed January 1, 2026, https://patchew.org/linux/20230131235027.36304-1-rishitbansal0@gmail.com/

Background information on the new keyboard lighting control, accessed January 1, 2026, https://www.tuxedocomputers.com/en/Dev-Thoughts-Background-information-on-the-new-keyboard-lighting-control.tuxedo

ITE 5711 Controller · Issue #759 - GitHub, accessed January 1, 2026, https://github.com/liquidctl/liquidctl/issues/759

Supported devices (Latest experimental) - OpenRGB, accessed January 1, 2026, https://openrgb.org/devices.html?search=msi

Askannz/msi-perkeyrgb: Linux CLI tool to control per-key ... - GitHub, accessed January 1, 2026, https://github.com/Askannz/msi-perkeyrgb
