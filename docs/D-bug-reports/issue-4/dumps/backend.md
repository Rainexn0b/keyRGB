{
  "candidates": [
    {
      "device_type": "keyboard",
      "hidraw_descriptor_sizes": [],
      "hidraw_nodes": [
        "/dev/hidraw6"
      ],
      "manufacturer": "ITE Tech. Inc.",
      "probe_names": [
        "ite8910"
      ],
      "probe_selection_reasons": [],
      "probe_stabilities": [
        "validated"
      ],
      "product": "ITE Device(829x)",
      "recommended_action": "Handled by an available backend.",
      "status": "supported",
      "usb_pid": "0x8910",
      "usb_vid": "0x048d"
    },
    {
      "device_type": "unknown",
      "hidraw_descriptor_sizes": [],
      "hidraw_nodes": [
        "/dev/hidraw4"
      ],
      "manufacturer": "ITE Tech. Inc.",
      "probe_names": [],
      "probe_selection_reasons": [],
      "probe_stabilities": [],
      "product": "ITE Device(8911)",
      "recommended_action": "Unrecognized ITE-class device. Capture a safe dump and open a support issue.",
      "status": "unrecognized_ite",
      "usb_pid": "0x8911",
      "usb_vid": "0x048d"
    }
  ],
  "hidraw_devices": [
    {
      "access": {
        "read": false,
        "write": false
      },
      "devnode": "/dev/hidraw0",
      "hid_id": "0018:00002808:00000102",
      "hid_name": "FTCS1000:01 2808:0102",
      "hidraw_name": "hidraw0",
      "product_id": "0x0102",
      "sysfs_dir": "/sys/class/hidraw/hidraw0",
      "vendor_id": "0x2808"
    },
    {
      "access": {
        "read": false,
        "write": false
      },
      "devnode": "/dev/hidraw1",
      "hid_id": "0003:0000046D:0000C31C",
      "hid_name": "Logitech USB Keyboard",
      "hidraw_name": "hidraw1",
      "product_id": "0xc31c",
      "sysfs_dir": "/sys/class/hidraw/hidraw1",
      "vendor_id": "0x046d"
    },
    {
      "access": {
        "read": false,
        "write": false
      },
      "devnode": "/dev/hidraw2",
      "hid_id": "0003:0000046D:0000C31C",
      "hid_name": "Logitech USB Keyboard",
      "hidraw_name": "hidraw2",
      "product_id": "0xc31c",
      "sysfs_dir": "/sys/class/hidraw/hidraw2",
      "vendor_id": "0x046d"
    },
    {
      "access": {
        "read": false,
        "write": false
      },
      "devnode": "/dev/hidraw3",
      "hid_id": "0003:0000046D:0000C077",
      "hid_name": "Logitech USB Optical Mouse",
      "hidraw_name": "hidraw3",
      "product_id": "0xc077",
      "sysfs_dir": "/sys/class/hidraw/hidraw3",
      "vendor_id": "0x046d"
    },
    {
      "access": {
        "read": false,
        "write": false
      },
      "devnode": "/dev/hidraw4",
      "hid_id": "0003:0000048D:00008911",
      "hid_name": "ITE Tech. Inc. ITE Device(8911)",
      "hidraw_name": "hidraw4",
      "product_id": "0x8911",
      "sysfs_dir": "/sys/class/hidraw/hidraw4",
      "vendor_id": "0x048d"
    },
    {
      "access": {
        "read": false,
        "write": false
      },
      "devnode": "/dev/hidraw5",
      "hid_id": "0003:000004F2:0000B865",
      "hid_name": "Generic Chicony USB2.0 Camera",
      "hidraw_name": "hidraw5",
      "product_id": "0xb865",
      "sysfs_dir": "/sys/class/hidraw/hidraw5",
      "vendor_id": "0x04f2"
    },
    {
      "access": {
        "read": true,
        "write": true
      },
      "devnode": "/dev/hidraw6",
      "hid_id": "0003:0000048D:00008910",
      "hid_name": "ITE Tech. Inc. ITE Device(829x)",
      "hidraw_name": "hidraw6",
      "product_id": "0x8910",
      "report_descriptor_error": "[Errno 22] Invalid argument",
      "sysfs_dir": "/sys/class/hidraw/hidraw6",
      "vendor_id": "0x048d"
    }
  ],
  "selected_backend": "ite8910",
  "summary": {
    "attention_count": 1,
    "candidate_count": 2,
    "supported_count": 1
  },
  "support_actions": {
    "next_steps": [
      "Run diagnostics and discovery from the tray, then attach the saved support bundle to a hardware-support issue.",
      "Include KEYRGB_DEBUG=1 logs if the tray starts but the keyboard does not respond.",
      "If permissions allow, rerun the scan after fixing hidraw access so the report can capture the HID descriptor."
    ],
    "optional_capture_commands": [
      "lsusb -v -d 048d:8911",
      "sudo usbhid-dump -d 048d:8911 -e descriptor"
    ],
    "primary_candidate": {
      "status": "unrecognized_ite",
      "usb_pid": "0x8911",
      "usb_vid": "0x048d"
    },
    "recommended_issue_template": "hardware-support",
    "recommended_issue_url": "https://github.com/Rainexn0b/keyRGB/issues/new?template=hardware-support.yml"
  },
  "usb_ids": [
    "046d:c077",
    "046d:c31c",
    "048d:8910",
    "048d:8911",
    "04f2:b865",
    "1d6b:0002",
    "1d6b:0003",
    "8087:0036"
  ]
}