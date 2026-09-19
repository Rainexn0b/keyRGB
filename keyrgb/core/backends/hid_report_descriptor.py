"""Minimal HID report-descriptor helpers for application-collection usage."""

from __future__ import annotations

_HID_TYPE_MAIN = 0
_HID_TYPE_GLOBAL = 1
_HID_TYPE_LOCAL = 2
_HID_TAG_USAGE_PAGE = 0x0
_HID_TAG_USAGE = 0x0
_HID_TAG_COLLECTION = 0xA
_HID_COLLECTION_APPLICATION = 0x01
_HID_LONG_ITEM_PREFIX = 0xFE
_HID_ITEM_SIZES = (0, 1, 2, 4)


def application_collection_usage(descriptor: bytes) -> tuple[int, int] | None:
    """Return ``(usage_page, usage)`` for the first Application collection."""

    usage_page = 0
    usage = 0
    index = 0
    length = len(descriptor)
    while index < length:
        prefix = descriptor[index]
        index += 1
        if prefix == _HID_LONG_ITEM_PREFIX:
            if index + 1 >= length:
                break
            data_size = int(descriptor[index])
            index += 2 + data_size
            continue

        size = _HID_ITEM_SIZES[prefix & 0x03]
        item_type = (prefix >> 2) & 0x03
        tag = (prefix >> 4) & 0x0F
        if index + size > length:
            break
        value = int.from_bytes(descriptor[index : index + size], "little") if size else 0
        index += size

        if item_type == _HID_TYPE_GLOBAL and tag == _HID_TAG_USAGE_PAGE:
            usage_page = value
        elif item_type == _HID_TYPE_LOCAL and tag == _HID_TAG_USAGE:
            usage = value
        elif item_type == _HID_TYPE_MAIN and tag == _HID_TAG_COLLECTION and value == _HID_COLLECTION_APPLICATION:
            return usage_page, usage

    return None


__all__ = ["application_collection_usage"]
