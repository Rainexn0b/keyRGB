from __future__ import annotations

from dataclasses import dataclass

from . import protocol

DEFAULT_INTERFACE_NUMBER = 1
_USB_SET_REPORT = 0x009
_USB_GET_REPORT = 0x001
_USB_FEATURE_VALUE = 0x300


@dataclass(frozen=True)
class UsbDeviceInfo:
    vendor_id: int
    product_id: int
    bcd_device: int | None
    bus: int | None
    address: int | None
    out_endpoint_address: int


def _load_pyusb_modules():
    import usb.core as usb_core  # type: ignore
    import usb.util as usb_util  # type: ignore

    return usb_core, usb_util


def device_bcd_device_or_none(device: object) -> int | None:
    raw = getattr(device, "bcdDevice", None)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError, OverflowError):
        return None


def _device_matches(device: object, *, product_ids: tuple[int, ...], required_bcd: int | None) -> bool:
    try:
        vendor_id = int(getattr(device, "idVendor"))
        product_id = int(getattr(device, "idProduct"))
    except (AttributeError, TypeError, ValueError, OverflowError):
        return False

    if vendor_id != int(protocol.VENDOR_ID) or product_id not in product_ids:
        return False
    if required_bcd is None:
        return True
    return device_bcd_device_or_none(device) == int(required_bcd)


def find_matching_device(
    *,
    loc: tuple[int, int] | None = None,
    product_ids: tuple[int, ...] | None = None,
    required_bcd: int | None = protocol.REV_NUMBER,
):
    usb_core, _usb_util = _load_pyusb_modules()
    supported_product_ids = tuple(int(pid) for pid in (product_ids or tuple(protocol.PRODUCT_IDS)))

    if loc is not None:
        bus, address = loc
        device = usb_core.find(bus=int(bus), address=int(address))
        if device is None:
            return None
        return device if _device_matches(device, product_ids=supported_product_ids, required_bcd=required_bcd) else None

    return usb_core.find(
        idVendor=int(protocol.VENDOR_ID),
        custom_match=lambda device: _device_matches(
            device,
            product_ids=supported_product_ids,
            required_bcd=required_bcd,
        ),
    )


def _detach_kernel_driver_if_needed(device: object, *, interface_number: int) -> None:
    is_active = getattr(device, "is_kernel_driver_active", None)
    if not callable(is_active):
        return
    try:
        active = bool(is_active(int(interface_number)))
    except (AttributeError, NotImplementedError, OSError, RuntimeError, ValueError):
        return
    if not active:
        return

    detach = getattr(device, "detach_kernel_driver", None)
    if callable(detach):
        detach(int(interface_number))


def _resolve_output_endpoint(device: object, usb_core: object, usb_util: object, *, interface_number: int) -> int:
    try:
        cfg = device.get_active_configuration()
    except getattr(usb_core, "USBError", OSError):
        set_configuration = getattr(device, "set_configuration", None)
        if callable(set_configuration):
            set_configuration()
        cfg = device.get_active_configuration()

    iface = cfg[(int(interface_number), 0)]
    endpoint = usb_util.find_descriptor(
        iface,
        custom_match=lambda ep: usb_util.endpoint_direction(ep.bEndpointAddress) == usb_util.ENDPOINT_OUT,
    )
    if endpoint is None:
        raise RuntimeError("No USB OUT endpoint found for ITE 8291r3 device")
    return int(endpoint.bEndpointAddress)


class PyUsbTransport:
    def __init__(self, *, device: object, usb_util: object, out_endpoint_address: int, interface_number: int) -> None:
        self._device = device
        self._usb_util = usb_util
        self._out_endpoint_address = int(out_endpoint_address)
        self._interface_number = int(interface_number)

    def send_control_report(self, report: bytes) -> int:
        payload = bytes(report)
        return int(
            self._device.ctrl_transfer(
                self._usb_util.build_request_type(
                    self._usb_util.CTRL_OUT,
                    self._usb_util.CTRL_TYPE_CLASS,
                    self._usb_util.CTRL_RECIPIENT_INTERFACE,
                ),
                _USB_SET_REPORT,
                _USB_FEATURE_VALUE,
                self._interface_number,
                payload,
            )
        )

    def read_control_report(self, length: int) -> bytes:
        data = self._device.ctrl_transfer(
            self._usb_util.build_request_type(
                self._usb_util.CTRL_IN,
                self._usb_util.CTRL_TYPE_CLASS,
                self._usb_util.CTRL_RECIPIENT_INTERFACE,
            ),
            _USB_GET_REPORT,
            _USB_FEATURE_VALUE,
            self._interface_number,
            int(length),
        )
        return bytes(data)

    def write_data(self, payload: bytes) -> int:
        return int(self._device.write(self._out_endpoint_address, bytes(payload)))


def open_matching_transport(
    *,
    loc: tuple[int, int] | None = None,
    product_ids: tuple[int, ...] | None = None,
    required_bcd: int | None = protocol.REV_NUMBER,
    interface_number: int = DEFAULT_INTERFACE_NUMBER,
) -> tuple[PyUsbTransport, UsbDeviceInfo]:
    usb_core, usb_util = _load_pyusb_modules()
    device = find_matching_device(loc=loc, product_ids=product_ids, required_bcd=required_bcd)
    if device is None:
        raise FileNotFoundError("no suitable device found")

    _detach_kernel_driver_if_needed(device, interface_number=int(interface_number))
    out_endpoint = _resolve_output_endpoint(device, usb_core, usb_util, interface_number=int(interface_number))
    info = UsbDeviceInfo(
        vendor_id=int(getattr(device, "idVendor", protocol.VENDOR_ID)),
        product_id=int(getattr(device, "idProduct")),
        bcd_device=device_bcd_device_or_none(device),
        bus=int(getattr(device, "bus", 0) or 0) or None,
        address=int(getattr(device, "address", 0) or 0) or None,
        out_endpoint_address=int(out_endpoint),
    )
    return (
        PyUsbTransport(
            device=device,
            usb_util=usb_util,
            out_endpoint_address=int(out_endpoint),
            interface_number=int(interface_number),
        ),
        info,
    )