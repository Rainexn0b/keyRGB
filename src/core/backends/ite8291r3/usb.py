from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, SupportsIndex, SupportsInt, cast

from . import protocol

DEFAULT_INTERFACE_NUMBER = 1
_USB_SET_REPORT = 0x009
_USB_GET_REPORT = 0x001
_USB_FEATURE_VALUE = 0x300

IntCoercible = SupportsInt | SupportsIndex | str | bytes | bytearray


class _UsbEndpointProtocol(Protocol):
    bEndpointAddress: int


class _UsbInterfaceProtocol(Protocol):
    pass


class _UsbConfigurationProtocol(Protocol):
    def __getitem__(self, key: tuple[int, int]) -> _UsbInterfaceProtocol: ...


class _UsbDeviceProtocol(Protocol):
    idVendor: object
    idProduct: object
    bcdDevice: object
    bus: object
    address: object

    def get_active_configuration(self) -> _UsbConfigurationProtocol: ...

    def set_configuration(self) -> object: ...

    def ctrl_transfer(
        self, bm_request_type: int, b_request: int, w_value: int, w_index: int, data_or_w_length: bytes | int
    ) -> object: ...

    def write(self, endpoint: int, data: bytes) -> int: ...

    def is_kernel_driver_active(self, interface_number: int) -> bool: ...

    def detach_kernel_driver(self, interface_number: int) -> object: ...


class _UsbCoreModuleProtocol(Protocol):
    USBError: type[BaseException]

    def find(self, **kwargs: object) -> _UsbDeviceProtocol | None: ...


class _UsbUtilModuleProtocol(Protocol):
    ENDPOINT_OUT: int
    CTRL_OUT: int
    CTRL_TYPE_CLASS: int
    CTRL_RECIPIENT_INTERFACE: int
    CTRL_IN: int

    def find_descriptor(
        self,
        interface: _UsbInterfaceProtocol,
        *,
        custom_match: Callable[[_UsbEndpointProtocol], bool],
    ) -> _UsbEndpointProtocol | None: ...

    def endpoint_direction(self, address: int) -> int: ...

    def build_request_type(self, direction: int, request_type: int, recipient: int) -> int: ...


def _coerce_int(value: object) -> int:
    return int(cast(IntCoercible, value))


def _coerce_optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return _coerce_int(value)
    except (TypeError, ValueError, OverflowError):
        return None


@dataclass(frozen=True)
class UsbDeviceInfo:
    vendor_id: int
    product_id: int
    bcd_device: int | None
    bus: int | None
    address: int | None
    out_endpoint_address: int


def _load_pyusb_modules() -> tuple[_UsbCoreModuleProtocol, _UsbUtilModuleProtocol]:
    import usb.core as usb_core  # type: ignore[import-not-found]
    import usb.util as usb_util  # type: ignore[import-not-found]

    return cast(_UsbCoreModuleProtocol, usb_core), cast(_UsbUtilModuleProtocol, usb_util)


def device_bcd_device_or_none(device: _UsbDeviceProtocol) -> int | None:
    try:
        return _coerce_optional_int(device.bcdDevice)
    except AttributeError:
        return None


def _device_matches(device: _UsbDeviceProtocol, *, product_ids: tuple[int, ...], required_bcd: int | None) -> bool:
    try:
        vendor_id = _coerce_int(device.idVendor)
        product_id = _coerce_int(device.idProduct)
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


def _detach_kernel_driver_if_needed(device: _UsbDeviceProtocol, *, interface_number: int) -> None:
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


def _resolve_output_endpoint(
    device: _UsbDeviceProtocol,
    usb_core: _UsbCoreModuleProtocol,
    usb_util: _UsbUtilModuleProtocol,
    *,
    interface_number: int,
) -> int:
    try:
        cfg = device.get_active_configuration()
    except (usb_core.USBError, OSError):
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
    def __init__(
        self,
        *,
        device: _UsbDeviceProtocol,
        usb_util: _UsbUtilModuleProtocol,
        out_endpoint_address: int,
        interface_number: int,
    ) -> None:
        self._device = device
        self._usb_util = usb_util
        self._out_endpoint_address = int(out_endpoint_address)
        self._interface_number = int(interface_number)

    def send_control_report(self, report: bytes) -> int:
        payload = bytes(report)
        return _coerce_int(
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
        return bytes(cast(bytes | bytearray | list[int], data))

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
        vendor_id=_coerce_optional_int(device.idVendor) or int(protocol.VENDOR_ID),
        product_id=_coerce_int(device.idProduct),
        bcd_device=device_bcd_device_or_none(device),
        bus=_coerce_optional_int(device.bus),
        address=_coerce_optional_int(device.address),
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
