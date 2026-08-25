#!/usr/bin/env python3
"""Read Hyper-V-relevant AMI setup variables extracted by UEFIExtract.

This script is deliberately read-only.  It expects a ``*.bin.dump`` directory
created by UEFIExtract and reports the same offsets from every redundant NVAR
store found in the image.
"""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path


TARGETS: dict[str, tuple[tuple[int, str], ...]] = {
    "Setup": (
        (0x6E8, "MSI enabled / FADT MSI support"),
        (0x8D3, "IOMMU pre-boot behavior"),
    ),
    "CpuSetup": (
        (0x005, "Hyper-Threading"),
        (0x006, "Active processor cores (0 = all)"),
        (0x007, "BIST on reset"),
        (0x043, "CFG Lock"),
        (0x0B9, "Intel VMX virtualization"),
        (0x0F1, "AP threads idle manner (1 HLT, 2 MWAIT, 3 RUN)"),
        (0x194, "Total Memory Encryption"),
        (0x19D, "Per-core HT disable mask, low byte"),
        (0x19E, "Per-core HT disable mask, high byte"),
        (0x229, "AVX disable flag (0 = enabled)"),
        (0x22A, "AVX3 disable flag (0 = enabled)"),
    ),
    "SaSetup": (
        (0x087, "VT-d global"),
        (0x091, "X2APIC opt-out"),
        (0x092, "DMA control guarantee"),
        (0x093, "IGD VT-d"),
        (0x094, "IPU VT-d"),
        (0x095, "IOP VT-d"),
        (0x096, "ITBT VT-d"),
        (0x0C9, "ITBT DMA0"),
        (0x0CA, "ITBT DMA1"),
        (0x0FF, "CPU crash log device"),
    ),
    "PchSetup": (
        (0x5FF, "IOAPIC IRQ 24-119 entries"),
    ),
    "AmiWrapperSetup": (
        (0x002, "Limit CPUID maximum"),
    ),
}


def variable_name(info_path: Path) -> str | None:
    text = info_path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"^Text:\s*(.+?)\s*$", text, flags=re.MULTILINE)
    return match.group(1) if match else None


def store_base(info_path: Path) -> str:
    text = info_path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"^Base:\s*(.+?)\s*$", text, flags=re.MULTILINE)
    return match.group(1) if match else "unknown"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dump_dir", type=Path, help="UEFIExtract *.bin.dump directory")
    args = parser.parse_args()

    stores = sorted(
        path for path in args.dump_dir.rglob("*NVAR store") if path.is_dir()
    )
    if not stores:
        raise SystemExit("No extracted AMI NVAR stores found")

    snapshots: dict[str, list[bytes]] = {name: [] for name in TARGETS}

    for index, store in enumerate(stores, start=1):
        info_path = store / "info.txt"
        print(f"NVAR mirror {index}: base={store_base(info_path)}")
        variables: dict[str, Path] = {}
        for child in store.iterdir():
            child_info = child / "info.txt"
            child_body = child / "body.bin"
            if not child.is_dir() or not child_info.is_file() or not child_body.is_file():
                continue
            name = variable_name(child_info)
            if name in TARGETS:
                variables[name] = child_body

        for name, fields in TARGETS.items():
            body_path = variables.get(name)
            if body_path is None:
                print(f"  {name}: NOT FOUND")
                continue
            data = body_path.read_bytes()
            snapshots[name].append(data)
            digest = hashlib.sha256(data).hexdigest().upper()
            print(f"  {name}: {len(data)} bytes, SHA256={digest}")
            for offset, description in fields:
                if offset >= len(data):
                    value = "OUT OF RANGE"
                else:
                    value = f"0x{data[offset]:02X} ({data[offset]})"
                print(f"    +0x{offset:03X} = {value:<12} {description}")
        print()

    print("Mirror agreement for target variables:")
    for name, versions in snapshots.items():
        agreement = bool(versions) and all(item == versions[0] for item in versions[1:])
        print(f"  {name}: {'IDENTICAL' if agreement else 'DIFFERENT OR MISSING'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
