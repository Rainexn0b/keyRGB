from __future__ import annotations

from types import SimpleNamespace

import pytest

from keyrgb.core.backends.ite8291r3_perkey import usb


class _FakeUsbError(OSError):
    pass


class _FakeCore:
    USBError = _FakeUsbError


class _FakeConfiguration:
    def __getitem__(self, _key: tuple[int, int]) -> object:
        return object()


class _FakeDevice:
    idVendor: object = usb.protocol.VENDOR_ID
    idProduct: object = usb.protocol.PRODUCT_IDS[0]
    bcdDevice: object = usb.protocol.REV_NUMBER
    bus: object = 1
    address: object = 2

    def __init__(self, events: list[str], *, kernel_driver_active: bool = True) -> None:
        self.events = events
        self.kernel_driver_active = kernel_driver_active

    def is_kernel_driver_active(self, interface_number: int) -> bool:
        assert interface_number == usb.DEFAULT_INTERFACE_NUMBER
        return self.kernel_driver_active

    def detach_kernel_driver(self, interface_number: int) -> None:
        assert interface_number == usb.DEFAULT_INTERFACE_NUMBER
        self.events.append("detach")
        self.kernel_driver_active = False

    def attach_kernel_driver(self, interface_number: int) -> None:
        assert interface_number == usb.DEFAULT_INTERFACE_NUMBER
        self.events.append("attach")
        self.kernel_driver_active = True

    def get_active_configuration(self) -> _FakeConfiguration:
        return _FakeConfiguration()


class _FakeUtil:
    ENDPOINT_OUT = 0
    CTRL_OUT = 0
    CTRL_TYPE_CLASS = 0
    CTRL_RECIPIENT_INTERFACE = 0
    CTRL_IN = 0

    def __init__(self, events: list[str], *, endpoint: object | None = None, dispose_error: Exception | None = None):
        self.events = events
        self.endpoint = endpoint if endpoint is not None else SimpleNamespace(bEndpointAddress=0x02)
        self.dispose_error = dispose_error

    def find_descriptor(self, _interface: object, *, custom_match) -> object | None:
        if self.endpoint is None:
            return None
        assert custom_match(self.endpoint)
        return self.endpoint

    def endpoint_direction(self, _address: int) -> int:
        return self.ENDPOINT_OUT

    def dispose_resources(self, _device: object) -> None:
        self.events.append("dispose")
        if self.dispose_error is not None:
            raise self.dispose_error


def _patch_usb_modules(
    monkeypatch: pytest.MonkeyPatch,
    *,
    device: _FakeDevice,
    usb_util: _FakeUtil,
) -> None:
    monkeypatch.setattr(usb, "_load_pyusb_modules", lambda: (_FakeCore(), usb_util))
    monkeypatch.setattr(usb, "find_matching_device", lambda **_kwargs: device)


def test_transport_close_disposes_before_reattaching_and_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    device = _FakeDevice(events)
    usb_util = _FakeUtil(events)
    _patch_usb_modules(monkeypatch, device=device, usb_util=usb_util)

    transport, info = usb.open_matching_transport()

    assert info.out_endpoint_address == 0x02
    assert events == ["detach"]

    transport.close()
    transport.close()

    assert events == ["detach", "dispose", "attach"]
    assert device.kernel_driver_active is True


def test_transport_open_rolls_back_endpoint_resolution_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    device = _FakeDevice(events)
    usb_util = _FakeUtil(events)
    usb_util.endpoint = None
    _patch_usb_modules(monkeypatch, device=device, usb_util=usb_util)

    with pytest.raises(RuntimeError, match="No USB OUT endpoint"):
        usb.open_matching_transport()

    assert events == ["detach", "dispose", "attach"]
    assert device.kernel_driver_active is True


def test_transport_open_rolls_back_metadata_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    device = _FakeDevice(events)
    device.idProduct = object()
    usb_util = _FakeUtil(events)
    _patch_usb_modules(monkeypatch, device=device, usb_util=usb_util)

    with pytest.raises(TypeError):
        usb.open_matching_transport()

    assert events == ["detach", "dispose", "attach"]
    assert device.kernel_driver_active is True


def test_transport_close_reattaches_after_recoverable_dispose_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    device = _FakeDevice(events)
    usb_util = _FakeUtil(events, dispose_error=RuntimeError("dispose failed"))
    _patch_usb_modules(monkeypatch, device=device, usb_util=usb_util)

    transport, _info = usb.open_matching_transport()
    transport.close()

    assert events == ["detach", "dispose", "attach"]
    assert device.kernel_driver_active is True


def test_transport_failure_without_detach_does_not_attach(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    device = _FakeDevice(events, kernel_driver_active=False)
    usb_util = _FakeUtil(events)
    usb_util.endpoint = None
    _patch_usb_modules(monkeypatch, device=device, usb_util=usb_util)

    with pytest.raises(RuntimeError, match="No USB OUT endpoint"):
        usb.open_matching_transport()

    assert events == ["dispose"]


def test_coerce_optional_int_and_device_match_helpers() -> None:
    assert usb._coerce_optional_int(None) is None
    assert usb._coerce_optional_int(7) == 7
    assert usb._coerce_optional_int(object()) is None

    class _Dev:
        def __init__(self, **kwargs: object) -> None:
            self.__dict__.update(kwargs)

    good = _Dev(
        idVendor=usb.protocol.VENDOR_ID,
        idProduct=usb.protocol.PRODUCT_IDS[0],
        bcdDevice=usb.protocol.REV_NUMBER,
    )
    assert usb._device_matches(good, product_ids=tuple(usb.protocol.PRODUCT_IDS), required_bcd=usb.protocol.REV_NUMBER)
    assert usb._device_matches(good, product_ids=tuple(usb.protocol.PRODUCT_IDS), required_bcd=None)

    bad_vid = _Dev(idVendor=1, idProduct=usb.protocol.PRODUCT_IDS[0], bcdDevice=usb.protocol.REV_NUMBER)
    assert not usb._device_matches(
        bad_vid, product_ids=tuple(usb.protocol.PRODUCT_IDS), required_bcd=usb.protocol.REV_NUMBER
    )

    wrong_bcd = _Dev(
        idVendor=usb.protocol.VENDOR_ID,
        idProduct=usb.protocol.PRODUCT_IDS[0],
        bcdDevice=0x99,
    )
    assert not usb._device_matches(
        wrong_bcd, product_ids=tuple(usb.protocol.PRODUCT_IDS), required_bcd=usb.protocol.REV_NUMBER
    )

    broken = _Dev()
    assert not usb._device_matches(broken, product_ids=tuple(usb.protocol.PRODUCT_IDS), required_bcd=None)


def test_find_matching_device_loc_and_scan(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Core:
        USBError = OSError

        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def find(self, **kwargs: object) -> object | None:
            self.calls.append(kwargs)
            if "bus" in kwargs:
                return SimpleNamespace(
                    idVendor=usb.protocol.VENDOR_ID,
                    idProduct=usb.protocol.PRODUCT_IDS[0],
                    bcdDevice=usb.protocol.REV_NUMBER,
                )
            # custom_match path
            match = kwargs.get("custom_match")
            assert callable(match)
            candidate = SimpleNamespace(
                idVendor=usb.protocol.VENDOR_ID,
                idProduct=usb.protocol.PRODUCT_IDS[0],
                bcdDevice=usb.protocol.REV_NUMBER,
            )
            assert match(candidate) is True
            return candidate

    core = _Core()
    monkeypatch.setattr(usb, "_load_pyusb_modules", lambda: (core, object()))

    found = usb.find_matching_device(loc=(1, 2))
    assert found is not None
    assert core.calls[0]["bus"] == 1

    found2 = usb.find_matching_device()
    assert found2 is not None

    # loc miss
    core2 = _Core()

    def find_none(**kwargs: object) -> None:
        return None

    core2.find = find_none  # type: ignore[method-assign]
    monkeypatch.setattr(usb, "_load_pyusb_modules", lambda: (core2, object()))
    assert usb.find_matching_device(loc=(9, 9)) is None


def test_kernel_driver_helpers_and_transport_io(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []

    class _Dev:
        def __init__(self) -> None:
            self.active = True
            self.writes: list[tuple[int, bytes]] = []
            self.ctrls: list[tuple] = []

        def is_kernel_driver_active(self, iface: int) -> bool:
            return self.active

        def detach_kernel_driver(self, iface: int) -> None:
            events.append(f"detach:{iface}")
            self.active = False

        def attach_kernel_driver(self, iface: int) -> None:
            events.append(f"attach:{iface}")
            self.active = True

        def ctrl_transfer(self, *args: object) -> object:
            self.ctrls.append(args)
            if args[0] == 1:  # CTRL_IN style in fake util
                return bytes([1, 2, 3, 4])
            return 8

        def write(self, endpoint: int, data: bytes) -> int:
            self.writes.append((endpoint, bytes(data)))
            return len(data)

    class _Util:
        ENDPOINT_OUT = 0
        CTRL_OUT = 0
        CTRL_IN = 1
        CTRL_TYPE_CLASS = 0
        CTRL_RECIPIENT_INTERFACE = 0

        def build_request_type(self, direction: int, request_type: int, recipient: int) -> int:
            return int(direction)

        def dispose_resources(self, _device: object) -> None:
            events.append("dispose")

        def find_descriptor(self, _iface: object, *, custom_match) -> object:
            ep = SimpleNamespace(bEndpointAddress=0x02)
            assert custom_match(ep)
            return ep

        def endpoint_direction(self, _addr: int) -> int:
            return self.ENDPOINT_OUT

    device = _Dev()
    assert usb._check_kernel_driver_active(device, interface_number=1) is True
    assert usb._detach_kernel_driver_if_needed(device, interface_number=1) is True
    assert "detach:1" in events
    assert usb._detach_kernel_driver_if_needed(device, interface_number=1) is False  # already inactive

    # no is_kernel_driver_active
    assert usb._check_kernel_driver_active(SimpleNamespace(), interface_number=1) is False

    # attach best-effort
    usb._reattach_kernel_driver(device, interface_number=1)
    assert "attach:1" in events
    usb._reattach_kernel_driver(SimpleNamespace(), interface_number=1)

    # attach failure swallowed
    class _BadAttach:
        def attach_kernel_driver(self, _iface: int) -> None:
            raise OSError("gone")

    usb._reattach_kernel_driver(_BadAttach(), interface_number=1)

    util = _Util()
    transport = usb.PyUsbTransport(
        device=device,
        usb_util=util,
        out_endpoint_address=0x02,
        interface_number=1,
        kernel_driver_detached=False,
    )
    assert transport.send_control_report(b"\x01\x02") == 8
    assert transport.read_control_report(4) == b"\x01\x02\x03\x04"
    assert transport.write_data(b"\xaa\xbb") == 2
    assert device.writes == [(0x02, b"\xaa\xbb")]

    transport.close()
    with pytest.raises(OSError, match="closed"):
        transport.send_control_report(b"\x01")
    with pytest.raises(OSError, match="closed"):
        transport.read_control_report(4)
    with pytest.raises(OSError, match="closed"):
        transport.write_data(b"\x01")


def test_resolve_output_endpoint_sets_configuration_on_error() -> None:
    class _USBError(OSError):
        pass

    class _Core:
        USBError = _USBError

    class _Cfg:
        def __getitem__(self, _key: tuple[int, int]) -> object:
            return object()

    class _Dev:
        def __init__(self) -> None:
            self.calls = 0
            self.configured = False

        def get_active_configuration(self) -> _Cfg:
            self.calls += 1
            if self.calls == 1 and not self.configured:
                raise _USBError("not configured")
            return _Cfg()

        def set_configuration(self) -> None:
            self.configured = True

    class _Util:
        ENDPOINT_OUT = 0

        def find_descriptor(self, _iface: object, *, custom_match) -> object:
            return SimpleNamespace(bEndpointAddress=0x81)

        def endpoint_direction(self, addr: int) -> int:
            return self.ENDPOINT_OUT

    endpoint = usb._resolve_output_endpoint(_Dev(), _Core(), _Util(), interface_number=1)
    assert endpoint == 0x81
