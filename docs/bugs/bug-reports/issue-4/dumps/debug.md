{
  "app": {
    "dist": "keyrgb",
    "version": "0.21.4",
    "version_source": "dist"
  },
  "backends": {
    "candidates_sorted": [
      {
        "confidence": 88,
        "experimental_evidence": null,
        "identifiers": {
          "hid_name": "ITE Tech. Inc. ITE Device(829x)",
          "hidraw": "/dev/hidraw6",
          "usb_pid": "0x8910",
          "usb_vid": "0x048d"
        },
        "name": "ite8910",
        "priority": 94,
        "provider": "usb-userspace",
        "reason": "hidraw device present (/dev/hidraw6)",
        "stability": "validated",
        "tier": 2
      }
    ],
    "guided_speed_probes": [
      {
        "backend": "ite8910",
        "effect_name": "spectrum_cycle",
        "expectation": "Higher UI speed values should look faster on ite8910.",
        "instructions": [
          "Switch the keyboard to the hardware effect entry, not the software effect with the same title.",
          "In the tray, use Spectrum Cycle from Hardware Effects; the forced selection key is hw:spectrum_cycle.",
          "Apply the listed UI speed values in order and watch whether each step is visually distinct.",
          "If multiple speeds appear identical or bunched together, record which values looked too close."
        ],
        "key": "ite8910_speed",
        "label": "ITE8910 hardware speed probe",
        "observation_prompt": "Which speed steps looked identical, too close together, or clearly distinct?",
        "requested_ui_speeds": [
          1,
          3,
          5,
          7,
          10
        ],
        "samples": [
          {
            "payload_speed": 1,
            "raw_speed": 1,
            "raw_speed_hex": "0x01",
            "ui_speed": 1
          },
          {
            "payload_speed": 3,
            "raw_speed": 3,
            "raw_speed_hex": "0x03",
            "ui_speed": 3
          },
          {
            "payload_speed": 5,
            "raw_speed": 5,
            "raw_speed_hex": "0x05",
            "ui_speed": 5
          },
          {
            "payload_speed": 7,
            "raw_speed": 7,
            "raw_speed_hex": "0x07",
            "ui_speed": 7
          },
          {
            "payload_speed": 10,
            "raw_speed": 10,
            "raw_speed_hex": "0x0a",
            "ui_speed": 10
          }
        ],
        "selection_effect_name": "hw:spectrum_cycle",
        "selection_menu_path": "Hardware Effects -> Spectrum Cycle"
      }
    ],
    "probes": [
      {
        "available": false,
        "confidence": 0,
        "name": "asusctl-aura",
        "priority": 120,
        "reason": "asusctl not found",
        "selection_enabled": true,
        "stability": "validated"
      },
      {
        "available": false,
        "confidence": 0,
        "name": "ite8291r3",
        "priority": 100,
        "provider": "usb-userspace",
        "reason": "no matching usb device",
        "selection_enabled": true,
        "stability": "validated",
        "tier": 2
      },
      {
        "available": false,
        "confidence": 0,
        "experimental_evidence": "reverse_engineered",
        "identifiers": {
          "usb_pid": "0x6004/0x6008/0x600b/0xce00",
          "usb_vid": "0x048d"
        },
        "name": "ite8291",
        "priority": 97,
        "provider": "usb-userspace",
        "reason": "no matching hidraw device for experimental ITE 8291 IDs: 0x048d:0x6004, 0x048d:0x6008, 0x048d:0x600b, 0x048d:0xce00",
        "selection_enabled": false,
        "selection_reason": "experimental backend disabled (enable Experimental backends in Settings or set KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1)",
        "stability": "experimental",
        "tier": 2
      },
      {
        "available": false,
        "confidence": 0,
        "experimental_evidence": "reverse_engineered",
        "identifiers": {
          "usb_pid": "0xc195",
          "usb_vid": "0x048d"
        },
        "name": "ite8258",
        "priority": 98,
        "provider": "usb-userspace",
        "reason": "no matching hidraw device",
        "selection_enabled": false,
        "selection_reason": "experimental backend disabled (enable Experimental backends in Settings or set KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1)",
        "stability": "experimental",
        "tier": 2
      },
      {
        "available": false,
        "confidence": 0,
        "experimental_evidence": "reverse_engineered",
        "identifiers": {
          "feature_report_size": "33",
          "usage": "0x00cc",
          "usage_page": "0xff89",
          "usb_pid": "0xc963",
          "usb_vid": "0x048d"
        },
        "name": "ite8295-zones",
        "priority": 97,
        "provider": "usb-userspace",
        "reason": "no matching hidraw device for Lenovo 4-zone ITE 8295 path",
        "selection_enabled": false,
        "selection_reason": "experimental backend disabled (enable Experimental backends in Settings or set KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1)",
        "stability": "experimental",
        "tier": 2
      },
      {
        "available": false,
        "confidence": 0,
        "experimental_evidence": "reverse_engineered",
        "identifiers": {
          "usb_bcd_device": "0x0002",
          "usb_pid": "0xce00",
          "usb_vid": "0x048d"
        },
        "name": "ite8291-zones",
        "priority": 96,
        "provider": "usb-userspace",
        "reason": "no matching hidraw device for experimental ITE 8291 4-zone firmware (0x048d:0xce00, bcdDevice 0x0002)",
        "selection_enabled": false,
        "selection_reason": "experimental backend disabled (enable Experimental backends in Settings or set KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1)",
        "stability": "experimental",
        "tier": 2
      },
      {
        "available": false,
        "confidence": 0,
        "experimental_evidence": "reverse_engineered",
        "identifiers": {
          "feature_report_id": "0x5a",
          "feature_report_size": "16",
          "usage_page": "0xff89",
          "usb_pid": "0x6010/0x7000/0x7001",
          "usb_vid": "0x048d"
        },
        "name": "ite8233",
        "priority": 96,
        "provider": "usb-userspace",
        "reason": "no matching hidraw device for speculative ITE lightbar IDs: 0x048d:0x6010, 0x048d:0x7000, 0x048d:0x7001",
        "selection_enabled": false,
        "selection_reason": "experimental backend disabled (enable Experimental backends in Settings or set KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1)",
        "stability": "experimental",
        "tier": 2
      },
      {
        "available": true,
        "confidence": 88,
        "identifiers": {
          "hid_name": "ITE Tech. Inc. ITE Device(829x)",
          "hidraw": "/dev/hidraw6",
          "usb_pid": "0x8910",
          "usb_vid": "0x048d"
        },
        "name": "ite8910",
        "priority": 94,
        "provider": "usb-userspace",
        "reason": "hidraw device present (/dev/hidraw6)",
        "selection_enabled": true,
        "stability": "validated",
        "tier": 2
      },
      {
        "available": false,
        "confidence": 0,
        "experimental_evidence": "reverse_engineered",
        "name": "ite8297",
        "priority": 95,
        "provider": "usb-userspace",
        "reason": "no matching hidraw device",
        "selection_enabled": false,
        "selection_reason": "experimental backend disabled (enable Experimental backends in Settings or set KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1)",
        "stability": "experimental",
        "tier": 2
      },
      {
        "available": false,
        "confidence": 0,
        "name": "sysfs-leds",
        "priority": 150,
        "provider": "kernel-sysfs",
        "reason": "no matching sysfs LED",
        "selection_enabled": true,
        "stability": "validated",
        "tier": 1
      },
      {
        "available": false,
        "confidence": 0,
        "experimental_evidence": "speculative",
        "name": "sysfs-mouse",
        "priority": 10,
        "provider": "kernel-sysfs",
        "reason": "no matching sysfs mouse LED",
        "selection_enabled": false,
        "selection_reason": "experimental backend disabled (enable Experimental backends in Settings or set KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1)",
        "stability": "experimental",
        "tier": 1
      }
    ],
    "requested": "auto",
    "selected": "ite8910",
    "selection": {
      "blocked": false,
      "blocked_reason": null,
      "disable_usb_scan": false,
      "experimental_backends_enabled": false,
      "policy": "highest confidence wins; priority is tie-breaker",
      "requested_effective": "auto"
    },
    "sysfs_led_candidates": {
      "candidates_count": 0,
      "exists": true,
      "pkexec_in_path": true,
      "pkexec_path": "/usr/bin/pkexec",
      "power_helper": {
        "executable": true,
        "exists": true,
        "gid": 0,
        "mode": "0755",
        "path": "/usr/local/bin/keyrgb-power-helper",
        "supports_led_apply": true,
        "uid": 0
      },
      "root": "/sys/class/leds",
      "root_is_sysfs": true,
      "sudo_in_path": true,
      "sudo_path": "/usr/bin/sudo",
      "top": [],
      "zones": {
        "groups": [],
        "inferred_zone_count": 0,
        "kbd_backlight_leds": []
      }
    },
    "sysfs_mouse_candidates": {
      "candidates_count": 16,
      "eligible_count": 0,
      "exists": true,
      "matched_count": 0,
      "root": "/sys/class/leds",
      "root_is_sysfs": true,
      "top": [
        {
          "brightness_readable": true,
          "brightness_writable": false,
          "color_capable": false,
          "eligible": false,
          "has_brightness": true,
          "has_max_brightness": true,
          "matched": false,
          "metadata": "",
          "mouse_tokens": [],
          "name": "igc-08300-led0",
          "path": "/sys/class/leds/igc-08300-led0",
          "reasons": [
            "no mouse/pointer evidence in LED name or device metadata"
          ],
          "score": 0,
          "vendor_tokens": []
        },
        {
          "brightness_readable": true,
          "brightness_writable": false,
          "color_capable": false,
          "eligible": false,
          "has_brightness": true,
          "has_max_brightness": true,
          "matched": false,
          "metadata": "",
          "mouse_tokens": [],
          "name": "igc-08300-led1",
          "path": "/sys/class/leds/igc-08300-led1",
          "reasons": [
            "no mouse/pointer evidence in LED name or device metadata"
          ],
          "score": 0,
          "vendor_tokens": []
        },
        {
          "brightness_readable": true,
          "brightness_writable": false,
          "color_capable": false,
          "eligible": false,
          "has_brightness": true,
          "has_max_brightness": true,
          "matched": false,
          "metadata": "",
          "mouse_tokens": [],
          "name": "igc-08300-led2",
          "path": "/sys/class/leds/igc-08300-led2",
          "reasons": [
            "no mouse/pointer evidence in LED name or device metadata"
          ],
          "score": 0,
          "vendor_tokens": []
        },
        {
          "brightness_readable": true,
          "brightness_writable": false,
          "color_capable": false,
          "eligible": false,
          "has_brightness": true,
          "has_max_brightness": true,
          "matched": false,
          "metadata": "",
          "mouse_tokens": [],
          "name": "igc-0d600-led0",
          "path": "/sys/class/leds/igc-0d600-led0",
          "reasons": [
            "no mouse/pointer evidence in LED name or device metadata"
          ],
          "score": 0,
          "vendor_tokens": []
        },
        {
          "brightness_readable": true,
          "brightness_writable": false,
          "color_capable": false,
          "eligible": false,
          "has_brightness": true,
          "has_max_brightness": true,
          "matched": false,
          "metadata": "",
          "mouse_tokens": [],
          "name": "igc-0d600-led1",
          "path": "/sys/class/leds/igc-0d600-led1",
          "reasons": [
            "no mouse/pointer evidence in LED name or device metadata"
          ],
          "score": 0,
          "vendor_tokens": []
        },
        {
          "brightness_readable": true,
          "brightness_writable": false,
          "color_capable": false,
          "eligible": false,
          "has_brightness": true,
          "has_max_brightness": true,
          "matched": false,
          "metadata": "",
          "mouse_tokens": [],
          "name": "igc-0d600-led2",
          "path": "/sys/class/leds/igc-0d600-led2",
          "reasons": [
            "no mouse/pointer evidence in LED name or device metadata"
          ],
          "score": 0,
          "vendor_tokens": []
        },
        {
          "brightness_readable": true,
          "brightness_writable": false,
          "color_capable": false,
          "eligible": false,
          "has_brightness": true,
          "has_max_brightness": true,
          "matched": false,
          "metadata": "logitech usb keyboard input:b0003v046dpc31ce0110-e0,1,4,11,14,k71,72,73,74,75,77,79,7a,7b,7c,7d,7e,7f,80,81,82,83,84,85,86,87,88,89,8a,8c,8e,96,98,9e,9f,a1,a3,a4,a5,a6,ad,b0,b1,b2,b3,b4,b7,b8,b9,ba,bb,bc,bd,be,bf,c0,c1,c2,f0,ram4,l0,1,2,3,4,sfw",
          "mouse_tokens": [],
          "name": "input13::capslock",
          "path": "/sys/class/leds/input13::capslock",
          "reasons": [
            "excluded by noisy token(s): capslock, keyboard"
          ],
          "score": 0,
          "vendor_tokens": [
            "logitech"
          ]
        },
        {
          "brightness_readable": true,
          "brightness_writable": false,
          "color_capable": false,
          "eligible": false,
          "has_brightness": true,
          "has_max_brightness": true,
          "matched": false,
          "metadata": "logitech usb keyboard input:b0003v046dpc31ce0110-e0,1,4,11,14,k71,72,73,74,75,77,79,7a,7b,7c,7d,7e,7f,80,81,82,83,84,85,86,87,88,89,8a,8c,8e,96,98,9e,9f,a1,a3,a4,a5,a6,ad,b0,b1,b2,b3,b4,b7,b8,b9,ba,bb,bc,bd,be,bf,c0,c1,c2,f0,ram4,l0,1,2,3,4,sfw",
          "mouse_tokens": [],
          "name": "input13::compose",
          "path": "/sys/class/leds/input13::compose",
          "reasons": [
            "excluded by noisy token(s): keyboard"
          ],
          "score": 0,
          "vendor_tokens": [
            "logitech"
          ]
        }
      ]
    }
  },
  "config": {
    "mtime": 1775671685,
    "per_key_colors_count": 120,
    "present": true,
    "settings": {
      "ac_lighting_brightness": 25,
      "ac_lighting_enabled": true,
      "autostart": true,
      "battery_lighting_brightness": 25,
      "battery_lighting_enabled": true,
      "battery_saver_brightness": 25,
      "battery_saver_enabled": false,
      "brightness": 25,
      "color": [
        255,
        251,
        0
      ],
      "effect": "perkey",
      "os_autostart": true,
      "power_management_enabled": true,
      "power_off_on_lid_close": true,
      "power_off_on_suspend": true,
      "power_restore_on_lid_open": true,
      "power_restore_on_resume": true,
      "speed": 5
    }
  },
  "dmi": {
    "bios_date": "07/31/2025",
    "bios_vendor": "INSYDE Corp.",
    "bios_version": "1.07.08",
    "board_name": "X58xWNx",
    "board_vendor": "Notebook",
    "board_version": "Not Applicable",
    "product_family": "Not Applicable",
    "product_name": "X58xWNx",
    "product_version": "Not Applicable",
    "sys_vendor": "Notebook"
  },
  "env": {
    "DESKTOP_SESSION": "cinnamon",
    "XDG_CURRENT_DESKTOP": "X-Cinnamon"
  },
  "hints": {
    "modules": [
      "snd_soc_acpi_intel_match",
      "snd_soc_acpi_intel_sdca_quirks",
      "snd_soc_acpi",
      "snd_intel_sdw_acpi",
      "snd_rawmidi",
      "hid_sensor_prox",
      "hid_sensor_trigger",
      "hid_sensor_iio_common",
      "wmi_bmof",
      "nvidia_wmi_ec_backlight",
      "mxm_wmi",
      "intel_hid",
      "acpi_thermal_rel",
      "acpi_pad",
      "mac_hid",
      "hid_sensor_hub",
      "usbhid",
      "hid_multitouch",
      "hid_generic",
      "ucsi_acpi",
      "i2c_hid_acpi",
      "i2c_hid",
      "hid",
      "wmi"
    ]
  },
  "leds": [],
  "power_supply": {
    "AC": {
      "online": "1",
      "type": "Mains"
    },
    "BAT0": {
      "capacity": "100",
      "charge_now": "6161000",
      "status": "Full",
      "type": "Battery"
    },
    "ucsi-source-psy-USBC000:001": {
      "online": "0",
      "type": "USB"
    },
    "ucsi-source-psy-USBC000:002": {
      "online": "0",
      "type": "USB"
    }
  },
  "process": {
    "egid": 1000,
    "euid": 1000,
    "groups": [
      4,
      24,
      27,
      30,
      46,
      100,
      105,
      125,
      1000
    ],
    "pid": 12573
  },
  "sysfs_leds": [
    {
      "brightness": "0",
      "max_brightness": "1",
      "name": "igc-08300-led0",
      "path": "/sys/class/leds/igc-08300-led0",
      "trigger": "[none] usb-gadget usb-host rfkill-any rfkill-none kbd-scrolllock kbd-numlock kbd-capslock kbd-kanalock kbd-shiftlock kbd-altgrlock kbd-ctrllock kbd-altlock kbd-shiftllock kbd-shiftrlock kbd-ctrlllock kbd-ctrlrlock disk-activity disk-read disk-write mtd nand-disk cpu cpu0 cpu1 cpu2 cpu3 cpu4 cpu5 cpu6 cpu7 panic AC-online BAT0-charging-or-full BAT0-charging BAT0-full BAT0-charging-blink-full-solid BAT0-charging-orange-full-green mmc0 ucsi-source-psy-USBC000:001-online ucsi-source-psy-USBC000:002-online rc-feedback bluetooth-power hci0-power rfkill0 phy0rx phy0tx phy0assoc phy0radio rfkill1"
    },
    {
      "brightness": "0",
      "max_brightness": "1",
      "name": "igc-08300-led1",
      "path": "/sys/class/leds/igc-08300-led1",
      "trigger": "[none] usb-gadget usb-host rfkill-any rfkill-none kbd-scrolllock kbd-numlock kbd-capslock kbd-kanalock kbd-shiftlock kbd-altgrlock kbd-ctrllock kbd-altlock kbd-shiftllock kbd-shiftrlock kbd-ctrlllock kbd-ctrlrlock disk-activity disk-read disk-write mtd nand-disk cpu cpu0 cpu1 cpu2 cpu3 cpu4 cpu5 cpu6 cpu7 panic AC-online BAT0-charging-or-full BAT0-charging BAT0-full BAT0-charging-blink-full-solid BAT0-charging-orange-full-green mmc0 ucsi-source-psy-USBC000:001-online ucsi-source-psy-USBC000:002-online rc-feedback bluetooth-power hci0-power rfkill0 phy0rx phy0tx phy0assoc phy0radio rfkill1"
    },
    {
      "brightness": "0",
      "max_brightness": "1",
      "name": "igc-08300-led2",
      "path": "/sys/class/leds/igc-08300-led2",
      "trigger": "[none] usb-gadget usb-host rfkill-any rfkill-none kbd-scrolllock kbd-numlock kbd-capslock kbd-kanalock kbd-shiftlock kbd-altgrlock kbd-ctrllock kbd-altlock kbd-shiftllock kbd-shiftrlock kbd-ctrlllock kbd-ctrlrlock disk-activity disk-read disk-write mtd nand-disk cpu cpu0 cpu1 cpu2 cpu3 cpu4 cpu5 cpu6 cpu7 panic AC-online BAT0-charging-or-full BAT0-charging BAT0-full BAT0-charging-blink-full-solid BAT0-charging-orange-full-green mmc0 ucsi-source-psy-USBC000:001-online ucsi-source-psy-USBC000:002-online rc-feedback bluetooth-power hci0-power rfkill0 phy0rx phy0tx phy0assoc phy0radio rfkill1"
    },
    {
      "brightness": "0",
      "max_brightness": "1",
      "name": "igc-0d600-led0",
      "path": "/sys/class/leds/igc-0d600-led0",
      "trigger": "[none] usb-gadget usb-host rfkill-any rfkill-none kbd-scrolllock kbd-numlock kbd-capslock kbd-kanalock kbd-shiftlock kbd-altgrlock kbd-ctrllock kbd-altlock kbd-shiftllock kbd-shiftrlock kbd-ctrlllock kbd-ctrlrlock disk-activity disk-read disk-write mtd nand-disk cpu cpu0 cpu1 cpu2 cpu3 cpu4 cpu5 cpu6 cpu7 panic AC-online BAT0-charging-or-full BAT0-charging BAT0-full BAT0-charging-blink-full-solid BAT0-charging-orange-full-green mmc0 ucsi-source-psy-USBC000:001-online ucsi-source-psy-USBC000:002-online rc-feedback bluetooth-power hci0-power rfkill0 phy0rx phy0tx phy0assoc phy0radio rfkill1"
    },
    {
      "brightness": "0",
      "max_brightness": "1",
      "name": "igc-0d600-led1",
      "path": "/sys/class/leds/igc-0d600-led1",
      "trigger": "[none] usb-gadget usb-host rfkill-any rfkill-none kbd-scrolllock kbd-numlock kbd-capslock kbd-kanalock kbd-shiftlock kbd-altgrlock kbd-ctrllock kbd-altlock kbd-shiftllock kbd-shiftrlock kbd-ctrlllock kbd-ctrlrlock disk-activity disk-read disk-write mtd nand-disk cpu cpu0 cpu1 cpu2 cpu3 cpu4 cpu5 cpu6 cpu7 panic AC-online BAT0-charging-or-full BAT0-charging BAT0-full BAT0-charging-blink-full-solid BAT0-charging-orange-full-green mmc0 ucsi-source-psy-USBC000:001-online ucsi-source-psy-USBC000:002-online rc-feedback bluetooth-power hci0-power rfkill0 phy0rx phy0tx phy0assoc phy0radio rfkill1"
    },
    {
      "brightness": "0",
      "max_brightness": "1",
      "name": "igc-0d600-led2",
      "path": "/sys/class/leds/igc-0d600-led2",
      "trigger": "[none] usb-gadget usb-host rfkill-any rfkill-none kbd-scrolllock kbd-numlock kbd-capslock kbd-kanalock kbd-shiftlock kbd-altgrlock kbd-ctrllock kbd-altlock kbd-shiftllock kbd-shiftrlock kbd-ctrlllock kbd-ctrlrlock disk-activity disk-read disk-write mtd nand-disk cpu cpu0 cpu1 cpu2 cpu3 cpu4 cpu5 cpu6 cpu7 panic AC-online BAT0-charging-or-full BAT0-charging BAT0-full BAT0-charging-blink-full-solid BAT0-charging-orange-full-green mmc0 ucsi-source-psy-USBC000:001-online ucsi-source-psy-USBC000:002-online rc-feedback bluetooth-power hci0-power rfkill0 phy0rx phy0tx phy0assoc phy0radio rfkill1"
    },
    {
      "brightness": "0",
      "max_brightness": "1",
      "name": "input13::capslock",
      "path": "/sys/class/leds/input13::capslock",
      "trigger": "none default usb-gadget usb-host rfkill-any rfkill-none kbd-scrolllock kbd-numlock [kbd-capslock] kbd-kanalock kbd-shiftlock kbd-altgrlock kbd-ctrllock kbd-altlock kbd-shiftllock kbd-shiftrlock kbd-ctrlllock kbd-ctrlrlock disk-activity disk-read disk-write mtd nand-disk cpu cpu0 cpu1 cpu2 cpu3 cpu4 cpu5 cpu6 cpu7 panic AC-online BAT0-charging-or-full BAT0-charging BAT0-full BAT0-charging-blink-full-solid BAT0-charging-orange-full-green mmc0 ucsi-source-psy-USBC000:001-online ucsi-source-psy-USBC000:002-online rc-feedback bluetooth-power hci0-power rfkill0 phy0rx phy0tx phy0assoc phy0radio rfkill1"
    },
    {
      "brightness": "0",
      "max_brightness": "1",
      "name": "input13::compose",
      "path": "/sys/class/leds/input13::compose",
      "trigger": "[none] usb-gadget usb-host rfkill-any rfkill-none kbd-scrolllock kbd-numlock kbd-capslock kbd-kanalock kbd-shiftlock kbd-altgrlock kbd-ctrllock kbd-altlock kbd-shiftllock kbd-shiftrlock kbd-ctrlllock kbd-ctrlrlock disk-activity disk-read disk-write mtd nand-disk cpu cpu0 cpu1 cpu2 cpu3 cpu4 cpu5 cpu6 cpu7 panic AC-online BAT0-charging-or-full BAT0-charging BAT0-full BAT0-charging-blink-full-solid BAT0-charging-orange-full-green mmc0 ucsi-source-psy-USBC000:001-online ucsi-source-psy-USBC000:002-online rc-feedback bluetooth-power hci0-power rfkill0 phy0rx phy0tx phy0assoc phy0radio rfkill1"
    },
    {
      "brightness": "0",
      "max_brightness": "1",
      "name": "input13::kana",
      "path": "/sys/class/leds/input13::kana",
      "trigger": "none default usb-gadget usb-host rfkill-any rfkill-none kbd-scrolllock kbd-numlock kbd-capslock [kbd-kanalock] kbd-shiftlock kbd-altgrlock kbd-ctrllock kbd-altlock kbd-shiftllock kbd-shiftrlock kbd-ctrlllock kbd-ctrlrlock disk-activity disk-read disk-write mtd nand-disk cpu cpu0 cpu1 cpu2 cpu3 cpu4 cpu5 cpu6 cpu7 panic AC-online BAT0-charging-or-full BAT0-charging BAT0-full BAT0-charging-blink-full-solid BAT0-charging-orange-full-green mmc0 ucsi-source-psy-USBC000:001-online ucsi-source-psy-USBC000:002-online rc-feedback bluetooth-power hci0-power rfkill0 phy0rx phy0tx phy0assoc phy0radio rfkill1"
    },
    {
      "brightness": "1",
      "max_brightness": "1",
      "name": "input13::numlock",
      "path": "/sys/class/leds/input13::numlock",
      "trigger": "none default usb-gadget usb-host rfkill-any rfkill-none kbd-scrolllock [kbd-numlock] kbd-capslock kbd-kanalock kbd-shiftlock kbd-altgrlock kbd-ctrllock kbd-altlock kbd-shiftllock kbd-shiftrlock kbd-ctrlllock kbd-ctrlrlock disk-activity disk-read disk-write mtd nand-disk cpu cpu0 cpu1 cpu2 cpu3 cpu4 cpu5 cpu6 cpu7 panic AC-online BAT0-charging-or-full BAT0-charging BAT0-full BAT0-charging-blink-full-solid BAT0-charging-orange-full-green mmc0 ucsi-source-psy-USBC000:001-online ucsi-source-psy-USBC000:002-online rc-feedback bluetooth-power hci0-power rfkill0 phy0rx phy0tx phy0assoc phy0radio rfkill1"
    },
    {
      "brightness": "0",
      "max_brightness": "1",
      "name": "input13::scrolllock",
      "path": "/sys/class/leds/input13::scrolllock",
      "trigger": "none default usb-gadget usb-host rfkill-any rfkill-none [kbd-scrolllock] kbd-numlock kbd-capslock kbd-kanalock kbd-shiftlock kbd-altgrlock kbd-ctrllock kbd-altlock kbd-shiftllock kbd-shiftrlock kbd-ctrlllock kbd-ctrlrlock disk-activity disk-read disk-write mtd nand-disk cpu cpu0 cpu1 cpu2 cpu3 cpu4 cpu5 cpu6 cpu7 panic AC-online BAT0-charging-or-full BAT0-charging BAT0-full BAT0-charging-blink-full-solid BAT0-charging-orange-full-green mmc0 ucsi-source-psy-USBC000:001-online ucsi-source-psy-USBC000:002-online rc-feedback bluetooth-power hci0-power rfkill0 phy0rx phy0tx phy0assoc phy0radio rfkill1"
    },
    {
      "brightness": "0",
      "max_brightness": "1",
      "name": "input4::capslock",
      "path": "/sys/class/leds/input4::capslock",
      "trigger": "none default usb-gadget usb-host rfkill-any rfkill-none kbd-scrolllock kbd-numlock [kbd-capslock] kbd-kanalock kbd-shiftlock kbd-altgrlock kbd-ctrllock kbd-altlock kbd-shiftllock kbd-shiftrlock kbd-ctrlllock kbd-ctrlrlock disk-activity disk-read disk-write mtd nand-disk cpu cpu0 cpu1 cpu2 cpu3 cpu4 cpu5 cpu6 cpu7 panic AC-online BAT0-charging-or-full BAT0-charging BAT0-full BAT0-charging-blink-full-solid BAT0-charging-orange-full-green mmc0 ucsi-source-psy-USBC000:001-online ucsi-source-psy-USBC000:002-online rc-feedback bluetooth-power hci0-power rfkill0 phy0rx phy0tx phy0assoc phy0radio rfkill1"
    },
    {
      "brightness": "1",
      "max_brightness": "1",
      "name": "input4::numlock",
      "path": "/sys/class/leds/input4::numlock",
      "trigger": "none default usb-gadget usb-host rfkill-any rfkill-none kbd-scrolllock [kbd-numlock] kbd-capslock kbd-kanalock kbd-shiftlock kbd-altgrlock kbd-ctrllock kbd-altlock kbd-shiftllock kbd-shiftrlock kbd-ctrlllock kbd-ctrlrlock disk-activity disk-read disk-write mtd nand-disk cpu cpu0 cpu1 cpu2 cpu3 cpu4 cpu5 cpu6 cpu7 panic AC-online BAT0-charging-or-full BAT0-charging BAT0-full BAT0-charging-blink-full-solid BAT0-charging-orange-full-green mmc0 ucsi-source-psy-USBC000:001-online ucsi-source-psy-USBC000:002-online rc-feedback bluetooth-power hci0-power rfkill0 phy0rx phy0tx phy0assoc phy0radio rfkill1"
    },
    {
      "brightness": "0",
      "max_brightness": "1",
      "name": "input4::scrolllock",
      "path": "/sys/class/leds/input4::scrolllock",
      "trigger": "none default usb-gadget usb-host rfkill-any rfkill-none [kbd-scrolllock] kbd-numlock kbd-capslock kbd-kanalock kbd-shiftlock kbd-altgrlock kbd-ctrllock kbd-altlock kbd-shiftllock kbd-shiftrlock kbd-ctrlllock kbd-ctrlrlock disk-activity disk-read disk-write mtd nand-disk cpu cpu0 cpu1 cpu2 cpu3 cpu4 cpu5 cpu6 cpu7 panic AC-online BAT0-charging-or-full BAT0-charging BAT0-full BAT0-charging-blink-full-solid BAT0-charging-orange-full-green mmc0 ucsi-source-psy-USBC000:001-online ucsi-source-psy-USBC000:002-online rc-feedback bluetooth-power hci0-power rfkill0 phy0rx phy0tx phy0assoc phy0radio rfkill1"
    },
    {
      "brightness": "0",
      "max_brightness": "255",
      "name": "mmc0::",
      "path": "/sys/class/leds/mmc0::",
      "trigger": "none default usb-gadget usb-host rfkill-any rfkill-none kbd-scrolllock kbd-numlock kbd-capslock kbd-kanalock kbd-shiftlock kbd-altgrlock kbd-ctrllock kbd-altlock kbd-shiftllock kbd-shiftrlock kbd-ctrlllock kbd-ctrlrlock disk-activity disk-read disk-write mtd nand-disk cpu cpu0 cpu1 cpu2 cpu3 cpu4 cpu5 cpu6 cpu7 panic AC-online BAT0-charging-or-full BAT0-charging BAT0-full BAT0-charging-blink-full-solid BAT0-charging-orange-full-green [mmc0] ucsi-source-psy-USBC000:001-online ucsi-source-psy-USBC000:002-online rc-feedback bluetooth-power hci0-power rfkill0 phy0rx phy0tx phy0assoc phy0radio rfkill1"
    },
    {
      "brightness": "1",
      "max_brightness": "1",
      "name": "phy0-led",
      "path": "/sys/class/leds/phy0-led",
      "trigger": "none default usb-gadget usb-host rfkill-any rfkill-none kbd-scrolllock kbd-numlock kbd-capslock kbd-kanalock kbd-shiftlock kbd-altgrlock kbd-ctrllock kbd-altlock kbd-shiftllock kbd-shiftrlock kbd-ctrlllock kbd-ctrlrlock disk-activity disk-read disk-write mtd nand-disk cpu cpu0 cpu1 cpu2 cpu3 cpu4 cpu5 cpu6 cpu7 panic AC-online BAT0-charging-or-full BAT0-charging BAT0-full BAT0-charging-blink-full-solid BAT0-charging-orange-full-green mmc0 ucsi-source-psy-USBC000:001-online ucsi-source-psy-USBC000:002-online rc-feedback bluetooth-power hci0-power rfkill0 phy0rx phy0tx phy0assoc [phy0radio] rfkill1"
    }
  ],
  "system": {
    "kernel_release": "6.17.0-20-generic",
    "machine": "x86_64",
    "os_release": {
      "ID": "linuxmint",
      "NAME": "Linux Mint",
      "PRETTY_NAME": "Linux Mint 22.3",
      "VERSION_ID": "22.3"
    },
    "power_mode": {
      "identifiers": {
        "boost_enabled": "true",
        "can_apply": "true",
        "cpufreq_root": "/sys/devices/system/cpu/cpufreq",
        "helper_present": "true",
        "policies": "24",
        "sysfs_writable": "false"
      },
      "mode": "balanced",
      "reason": "ok",
      "supported": true
    },
    "python": "3.12.13"
  },
  "usb_devices": [
    {
      "bcdDevice": "0001",
      "busnum": "1",
      "devnode": "/dev/bus/usb/001/006",
      "devnode_access": {
        "read": true,
        "write": false
      },
      "devnode_gid": 0,
      "devnode_mode": "0o664",
      "devnode_uid": 0,
      "devnum": "6",
      "driver": "usb",
      "idProduct": "0x8910",
      "idVendor": "0x048d",
      "manufacturer": "ITE Tech. Inc.",
      "product": "ITE Device(829x)",
      "speed": "12",
      "sysfs_path": "/sys/bus/usb/devices/1-7"
    }
  ],
  "usb_ids": [
    "046d:c077",
    "046d:c31c",
    "048d:8910",
    "048d:8911",
    "04f2:b865",
    "1d6b:0002",
    "1d6b:0003",
    "8087:0036"
  ],
  "virt": {
    "systemd_detect_virt": "none"
  }
}