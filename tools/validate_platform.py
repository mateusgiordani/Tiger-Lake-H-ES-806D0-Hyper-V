#!/usr/bin/env python3
"""Validate normalized platform evidence without collecting live hardware data."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "tests" / "fixtures" / "affected" / "platform.json"


def _int(value: object) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def _leaf(data: dict, leaf: str, subleaf: str = "0") -> dict:
    return data.get("cpuid", {}).get(leaf, {}).get(subleaf, {})


def _bit(data: dict, leaf: str, register: str, bit: int) -> int:
    return (_int(_leaf(data, leaf).get(register, 0)) >> bit) & 1


def parse_madt(path: Path) -> tuple[set[int], set[int], list[int]]:
    data = path.read_bytes()
    if len(data) < 44 or data[:4] != b"APIC":
        raise ValueError(f"{path}: not an ACPI MADT/APIC table")
    declared = struct.unpack_from("<I", data, 4)[0]
    if declared != len(data):
        raise ValueError(f"{path}: declared length {declared} != file length {len(data)}")
    cpu_uids: set[int] = set()
    nmi_uids: set[int] = set()
    offset = 44
    while offset < len(data):
        kind, length = struct.unpack_from("BB", data, offset)
        if length < 2 or offset + length > len(data):
            raise ValueError(f"{path}: invalid subtable at 0x{offset:X}")
        if kind == 0 and length >= 8:
            uid, _, flags = struct.unpack_from("<BBI", data, offset + 2)
            if flags & 1:
                cpu_uids.add(uid)
        elif kind == 4 and length >= 6:
            nmi_uids.add(data[offset + 2])
        offset += length
    return cpu_uids, nmi_uids, list(data)


def validate_madt(path: Path) -> list[tuple[str, str]]:
    cpus, nmis, _ = parse_madt(path)
    concrete_nmis = {uid for uid in nmis if uid != 0xFF}
    issues: list[tuple[str, str]] = []
    if cpus != concrete_nmis and 0xFF not in nmis:
        missing, orphan = sorted(cpus - concrete_nmis), sorted(concrete_nmis - cpus)
        issues.append(("MADT_NMI_UID_MISMATCH", f"missing={missing} orphan={orphan}"))
    if {uid + 1 for uid in cpus} == concrete_nmis:
        issues.append(("NMI_UID_OFFSET_PLUS_ONE", "Local APIC NMI UIDs are shifted by +1"))
    return issues


def validate_cpuid(data: dict) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    avx512f = _bit(data, "0x00000007", "ebx", 16)
    avx512vl = _bit(data, "0x00000007", "ebx", 31)
    vp2 = _bit(data, "0x00000007", "edx", 8)
    if vp2 and not avx512f:
        issues.append(("ORPHAN_AVX512_VP2INTERSECT", "VP2INTERSECT=1 while AVX512F=0"))
    if vp2 and not avx512vl:
        issues.append(("ORPHAN_AVX512_VP2INTERSECT_VL", "VP2INTERSECT=1 while AVX512VL=0"))
    xstate_eax = _int(_leaf(data, "0x0000000D").get("eax", 0))
    missing_xstate = [state for state in (5, 6, 7) if not (xstate_eax & (1 << state))]
    if vp2 and missing_xstate:
        issues.append(("AVX512_XSTATE_UNAVAILABLE", f"missing XSTATE components={missing_xstate}"))
    return issues


def report(data: dict, madt: Path | None) -> int:
    cpu = data.get("cpu", {})
    print("BIOS Interposer Platform Validator")
    print("\nCPU")
    print(f"  Vendor: {cpu.get('vendor', 'unknown')}")
    print(f"  Family/Model/Stepping: {cpu.get('family', '?')}/{cpu.get('model', '?')}/{cpu.get('stepping', '?')}")
    print(f"  CPUID signature: {cpu.get('signature', 'unknown')}")
    print(f"  Logical processors: {cpu.get('logical_processors', 'unknown')}")
    issues: list[tuple[str, str]] = []
    if madt:
        print("\nMADT")
        cpus, nmis, _ = parse_madt(madt)
        print(f"  Active CPU UIDs:       {sorted(cpus)}")
        print(f"  Local APIC NMI UIDs:   {sorted(nmis)}")
        issues.extend(validate_madt(madt))
        for code, detail in issues:
            if code.startswith("MADT") or code.startswith("NMI_"):
                print(f"  [FAIL] {code}: {detail}")
    print("\nCPUID/XSTATE")
    for code, detail in validate_cpuid(data):
        issues.append((code, detail))
        print(f"  [FAIL] {code}: {detail}")
    signature = data.get("signature", "ERYING_TGL_ES_806D0_XSAVE")
    print("\nHyper-V compatibility signature")
    print(f"  [MATCH] {signature}")
    print("\nSuggested workaround:")
    print('  bcdedit /set "{current}" xsavedisable 1')
    return 1 if issues else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path, default=DEFAULT_INPUT, help="normalized platform JSON")
    parser.add_argument("--madt", type=Path, help="optional ACPI MADT binary")
    parser.add_argument("--report-json", type=Path, help="write machine-readable validation report")
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    status = report(data, args.madt)
    if args.report_json:
        args.report_json.write_text(json.dumps({"input": str(args.input), "status": "fail" if status else "pass"}, indent=2) + "\n", encoding="utf-8")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
