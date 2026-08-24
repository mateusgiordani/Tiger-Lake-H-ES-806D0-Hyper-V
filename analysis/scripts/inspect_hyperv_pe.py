#!/usr/bin/env python3
"""Inspect Microsoft Hyper-V PE images without executing or modifying them.

Reports PE identity, CodeView/PDB identity, imports/exports, selected firmware
keywords, and privileged x86 instructions found in executable sections.
Requires: pefile, capstone.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64


KEYWORDS = re.compile(
    rb"(?i)(acpi|apic|x2apic|madt|dmar|iommu|vtd|vt-d|vmx|ept|vpid|"
    rb"cpuid|msr|mbec|mtrr|smx|txt|microcode|topology|processor|hypervisor)"
)

PRIVILEGED = {
    "cpuid",
    "rdmsr",
    "wrmsr",
    "vmcall",
    "vmlaunch",
    "vmresume",
    "vmxoff",
    "vmxon",
    "vmclear",
    "vmptrld",
    "vmptrst",
    "vmread",
    "vmwrite",
    "invept",
    "invvpid",
    "invpcid",
    "rdtsc",
    "rdtscp",
    "xsetbv",
    "xgetbv",
}


def decode(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return value.decode("utf-8", "replace")


def pdb_identity(pe: pefile.PE) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for entry in getattr(pe, "DIRECTORY_ENTRY_DEBUG", []):
        if entry.struct.Type != 2 or entry.struct.SizeOfData < 24:
            continue
        blob = pe.get_data(entry.struct.AddressOfRawData, entry.struct.SizeOfData)
        if not blob.startswith(b"RSDS"):
            continue
        raw_guid = blob[4:20]
        d1 = int.from_bytes(raw_guid[0:4], "little")
        d2 = int.from_bytes(raw_guid[4:6], "little")
        d3 = int.from_bytes(raw_guid[6:8], "little")
        d4 = raw_guid[8:]
        guid = f"{d1:08X}{d2:04X}{d3:04X}{d4.hex().upper()}"
        age = int.from_bytes(blob[20:24], "little")
        path = blob[24:].split(b"\0", 1)[0].decode("utf-8", "replace")
        records.append(
            {
                "pdb_path": path,
                "pdb_name": Path(path.replace("\\", "/")).name,
                "guid": guid,
                "age": age,
                "symbol_key": f"{guid}{age:X}",
            }
        )
    return records


def imported_symbols(pe: pefile.PE) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for library in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
        names = []
        for symbol in library.imports:
            names.append(decode(symbol.name) if symbol.name else f"ordinal:{symbol.ordinal}")
        result[decode(library.dll)] = names
    return result


def exported_symbols(pe: pefile.PE) -> list[str]:
    directory = getattr(pe, "DIRECTORY_ENTRY_EXPORT", None)
    if not directory:
        return []
    return [decode(item.name) if item.name else f"ordinal:{item.ordinal}" for item in directory.symbols]


def keyword_strings(data: bytes, limit: int = 120) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    candidates: list[tuple[int, str]] = []
    for match in re.finditer(rb"[ -~]{4,}", data):
        candidates.append((match.start(), match.group().decode("ascii", "replace")))
    for match in re.finditer(rb"(?:[ -~]\x00){4,}", data):
        candidates.append((match.start(), match.group()[::2].decode("ascii", "replace")))
    for offset, value in sorted(candidates):
        if KEYWORDS.search(value.encode("ascii", "replace")):
            found.append({"file_offset": f"0x{offset:X}", "value": value[:300]})
            if len(found) >= limit:
                break
    return found


def privileged_instructions(pe: pefile.PE, per_mnemonic: int = 16) -> dict[str, object]:
    dis = Cs(CS_ARCH_X86, CS_MODE_64)
    counts: Counter[str] = Counter()
    examples: dict[str, list[dict[str, str]]] = {}
    image_base = pe.OPTIONAL_HEADER.ImageBase
    for section in pe.sections:
        if not (section.Characteristics & 0x20000000):
            continue
        code = section.get_data()
        address = image_base + section.VirtualAddress
        for insn in dis.disasm(code, address):
            mnemonic = insn.mnemonic.lower()
            if mnemonic not in PRIVILEGED:
                continue
            counts[mnemonic] += 1
            bucket = examples.setdefault(mnemonic, [])
            if len(bucket) < per_mnemonic:
                bucket.append(
                    {
                        "va": f"0x{insn.address:X}",
                        "rva": f"0x{insn.address - image_base:X}",
                        "instruction": f"{insn.mnemonic} {insn.op_str}".strip(),
                    }
                )
    return {"counts": dict(sorted(counts.items())), "examples": examples}


def inspect(path: Path, disassemble: bool) -> dict[str, object]:
    data = path.read_bytes()
    pe = pefile.PE(data=data, fast_load=False)
    pe.parse_data_directories()
    result: dict[str, object] = {
        "path": str(path),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest().upper(),
        "machine": f"0x{pe.FILE_HEADER.Machine:04X}",
        "pe_timestamp_raw": f"0x{pe.FILE_HEADER.TimeDateStamp:08X}",
        "image_base": f"0x{pe.OPTIONAL_HEADER.ImageBase:X}",
        "entry_rva": f"0x{pe.OPTIONAL_HEADER.AddressOfEntryPoint:X}",
        "pdb": pdb_identity(pe),
        "imports": imported_symbols(pe),
        "exports": exported_symbols(pe),
        "keyword_strings": keyword_strings(data),
    }
    if disassemble:
        result["privileged_instructions"] = privileged_instructions(pe)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--no-disassemble", action="store_true")
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    reports = [inspect(path.resolve(), not args.no_disassemble) for path in args.paths]
    print(json.dumps(reports, indent=None if args.compact else 2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
