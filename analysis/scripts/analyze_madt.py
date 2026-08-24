#!/usr/bin/env python3
"""Inspect, compare, and safely patch ACPI MADT binary tables."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path


ACPI_HEADER_SIZE = 36
MADT_FIXED_SIZE = 44


def parse_madt(data: bytes):
    if len(data) < MADT_FIXED_SIZE or data[:4] != b"APIC":
        raise ValueError("not an ACPI MADT/APIC table")
    declared_length = struct.unpack_from("<I", data, 4)[0]
    if declared_length != len(data):
        raise ValueError(f"declared length {declared_length} != file length {len(data)}")

    subtables = []
    offset = MADT_FIXED_SIZE
    while offset < len(data):
        if offset + 2 > len(data):
            raise ValueError(f"truncated subtable header at 0x{offset:X}")
        table_type, length = struct.unpack_from("BB", data, offset)
        if length < 2 or offset + length > len(data):
            raise ValueError(f"invalid subtable length {length} at 0x{offset:X}")
        raw = data[offset : offset + length]
        decoded = None
        if table_type == 0 and length >= 8:
            uid, apic_id, flags = struct.unpack_from("<BBI", raw, 2)
            decoded = {"uid": uid, "apic_id": apic_id, "flags": flags}
        elif table_type == 4 and length >= 6:
            uid, flags, lint = struct.unpack_from("<BHB", raw, 2)
            decoded = {"uid": uid, "flags": flags, "lint": lint}
        subtables.append((offset, table_type, length, decoded))
        offset += length
    return subtables


def checksum(data: bytes) -> int:
    return sum(data) & 0xFF


def describe(path: Path, data: bytes) -> None:
    subtables = parse_madt(data)
    cpus = [decoded for _, kind, _, decoded in subtables if kind == 0 and decoded]
    nmis = [decoded for _, kind, _, decoded in subtables if kind == 4 and decoded]
    enabled_uids = [item["uid"] for item in cpus if item["flags"] & 1]
    print(f"{path}: {len(data)} bytes, checksum=0x{checksum(data):02X}")
    print(f"  Enabled processor UIDs: {enabled_uids}")
    print(f"  Local APIC IDs: {[item['apic_id'] for item in cpus if item['flags'] & 1]}")
    print(f"  Local APIC NMI UIDs: {[item['uid'] for item in nmis]}")
    print(f"  Local APIC NMI LINTs: {[item['lint'] for item in nmis]}")
    invalid = [item["uid"] for item in nmis if item["uid"] != 0xFF and item["uid"] not in enabled_uids]
    missing = [uid for uid in enabled_uids if not any(item["uid"] in (uid, 0xFF) for item in nmis)]
    print(f"  NMI UIDs without enabled processor: {invalid}")
    print(f"  Enabled processors without NMI mapping: {missing}")


def compare(left: bytes, right: bytes) -> None:
    if len(left) != len(right):
        print(f"Comparison length differs: {len(left)} vs {len(right)}")
    differences = []
    for offset, (a, b) in enumerate(zip(left, right)):
        if a != b:
            differences.append((offset, a, b))
    print(f"Different bytes in common length: {len(differences)}")
    for offset, a, b in differences:
        print(f"  0x{offset:03X}: 0x{a:02X} -> 0x{b:02X}")


def patch_nmis(data: bytes, mode: str) -> bytes:
    patched = bytearray(data)
    nmi_index = 0
    for offset, kind, _, decoded in parse_madt(data):
        if kind != 4 or decoded is None:
            continue
        patched[offset + 2] = 0xFF if mode == "all" else nmi_index
        nmi_index += 1
    patched[9] = 0
    patched[9] = (-sum(patched)) & 0xFF
    if checksum(patched) != 0:
        raise AssertionError("failed to repair ACPI checksum")
    return bytes(patched)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("table", type=Path)
    parser.add_argument("--compare", type=Path)
    parser.add_argument("--patch-nmi", choices=("all", "zero-based"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    data = args.table.read_bytes()
    describe(args.table, data)
    if args.compare:
        other = args.compare.read_bytes()
        describe(args.compare, other)
        compare(data, other)
    if args.patch_nmi:
        if args.output is None:
            parser.error("--patch-nmi requires --output")
        patched = patch_nmis(data, args.patch_nmi)
        args.output.write_bytes(patched)
        print(f"Wrote {args.output} ({len(patched)} bytes)")
        describe(args.output, patched)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
