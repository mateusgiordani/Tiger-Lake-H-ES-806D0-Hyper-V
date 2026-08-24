#!/usr/bin/env python3
"""Extract likely boot/configuration strings from Microsoft Hyper-V PE files.

This is a read-only triage helper.  It does not claim that every recovered
string is reachable in the current build; cross-reference analysis is still
required before treating a token as an effective switch.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ASCII = re.compile(rb"[ -~]{4,}")
UTF16 = re.compile(rb"(?:[ -~]\x00){4,}")
UPPER_TOKEN = re.compile(
    r"^(?:DISABLE|ENABLE|NO|USE|STORE|PROC|HYPERVISOR|IOMMU)"
    r"[A-Z0-9_]{3,}(?:=[A-Z0-9_]+)?$"
)
CONFIG_WORD = re.compile(
    r"(?i)(hypervisor|iommu|apic|vapic|x2apic|vmx|ept|vpid|mbec|slat|"
    r"xsave|xstate|tsc|timer|clock|mtrr|microcode|processor|topology|"
    r"memorypart|memory.partition|smt|thread|core|numa|mce|machine.check)"
)


def strings(data: bytes) -> list[tuple[int, str, str]]:
    found: dict[tuple[int, str], tuple[int, str, str]] = {}
    for match in ASCII.finditer(data):
        value = match.group().decode("ascii", "replace")
        found[(match.start(), value)] = (match.start(), "ascii", value)
    for match in UTF16.finditer(data):
        value = match.group()[::2].decode("ascii", "replace")
        found[(match.start(), value)] = (match.start(), "utf16le", value)
    return sorted(found.values())


def classify(value: str) -> list[str]:
    tags: list[str] = []
    if UPPER_TOKEN.fullmatch(value):
        tags.append("load-option-token")
    if CONFIG_WORD.search(value):
        tags.append("hyperv-relevant")
    return tags


def inspect(path: Path) -> dict[str, object]:
    records = []
    for offset, encoding, value in strings(path.read_bytes()):
        tags = classify(value)
        if not tags:
            continue
        records.append(
            {
                "file_offset": f"0x{offset:X}",
                "encoding": encoding,
                "tags": tags,
                "value": value,
            }
        )
    return {"path": str(path.resolve()), "matches": records}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    result = [inspect(path) for path in args.paths]
    print(json.dumps(result, ensure_ascii=False, indent=None if args.compact else 2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
