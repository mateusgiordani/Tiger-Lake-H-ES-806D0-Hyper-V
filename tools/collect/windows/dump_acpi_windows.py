#!/usr/bin/env python3
"""Read one ACPI table from Windows through GetSystemFirmwareTable.

The script is read-only.  It is intended to prove whether an OpenCore ACPI
patch is visible to Windows before any Hyper-V test is attempted.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import struct
from pathlib import Path


def table_fourcc(text: str) -> int:
    raw = text.encode("ascii")
    if len(raw) != 4:
        raise ValueError("ACPI signature must contain exactly four ASCII characters")
    return int.from_bytes(raw, "little")


def read_firmware_table(signature: str) -> bytes:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    get_table = kernel32.GetSystemFirmwareTable
    get_table.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32]
    get_table.restype = ctypes.c_uint32

    # The Win32 API documents the provider as the C multi-character literal
    # 'ACPI' (numeric 0x41435049), while FirmwareTableID is explicitly little
    # endian (e.g. FACP is passed as the C literal 'PCAF').
    provider = int.from_bytes(b"ACPI", "big")
    table_id = table_fourcc(signature)
    size = get_table(provider, table_id, None, 0)
    if size == 0:
        error = ctypes.get_last_error()
        raise OSError(error, f"GetSystemFirmwareTable({signature}) size query failed")
    buffer = (ctypes.c_ubyte * size)()
    written = get_table(provider, table_id, buffer, size)
    if written == 0:
        error = ctypes.get_last_error()
        raise OSError(error, f"GetSystemFirmwareTable({signature}) read failed")
    if written > size:
        raise RuntimeError(f"ACPI table grew between calls: allocated={size}, needed={written}")
    return bytes(buffer[:written])


def describe(data: bytes) -> dict:
    if len(data) < 36:
        raise ValueError("ACPI table is shorter than the standard 36-byte header")
    declared_length = struct.unpack_from("<I", data, 4)[0]
    checksum_valid = declared_length <= len(data) and (sum(data[:declared_length]) & 0xFF) == 0
    result = {
        "signature": data[:4].decode("ascii", "replace"),
        "declared_length": declared_length,
        "bytes_returned": len(data),
        "revision": data[8],
        "checksum_byte": data[9],
        "checksum_valid": checksum_valid,
        "oem_id": data[10:16].decode("ascii", "replace"),
        "oem_table_id_hex": data[16:24].hex().upper(),
        "sha256": hashlib.sha256(data).hexdigest().upper(),
    }
    if data[:4] == b"APIC" and declared_length == len(data):
        offset = 44
        local_apic_uids = []
        local_apic_ids = []
        local_apic_nmi_uids = []
        while offset < len(data):
            if offset + 2 > len(data):
                raise ValueError(f"Truncated MADT record at 0x{offset:X}")
            record_type, record_length = data[offset], data[offset + 1]
            if record_length < 2 or offset + record_length > len(data):
                raise ValueError(f"Invalid MADT record length at 0x{offset:X}")
            if record_type == 0 and record_length >= 8:
                local_apic_uids.append(data[offset + 2])
                local_apic_ids.append(data[offset + 3])
            elif record_type == 4 and record_length >= 6:
                local_apic_nmi_uids.append(data[offset + 2])
            offset += record_length
        result["madt"] = {
            "local_apic_uids": local_apic_uids,
            "local_apic_ids": local_apic_ids,
            "local_apic_nmi_uids": local_apic_nmi_uids,
            "nmi_uid_set_matches_cpu_uid_set": set(local_apic_nmi_uids) == set(local_apic_uids),
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signature", default="APIC", help="four-character ACPI signature")
    parser.add_argument("--output", type=Path, help="optional binary output path")
    parser.add_argument("--json", type=Path, help="optional JSON report path")
    args = parser.parse_args()

    signature = args.signature.upper()
    data = read_firmware_table(signature)
    report = describe(data)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(data)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
