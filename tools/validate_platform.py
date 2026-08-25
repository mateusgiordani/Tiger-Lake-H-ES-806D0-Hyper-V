#!/usr/bin/env python3
"""Validate normalized platform evidence without collecting live hardware data."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path


VALIDATOR_VERSION = "0.2.0"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "tests" / "fixtures" / "affected" / "platform.json"
KNOWN_FMS = 0x000806D0


def _int(value: object) -> int:
    if not isinstance(value, str):
        return int(value)
    try:
        return int(value, 0)
    except ValueError:
        return int(value, 16)


def _leaf(data: dict, leaf: str, subleaf: str = "0") -> dict:
    leaves = data.get("cpuid", {})
    entry = leaves.get(leaf, {})
    return entry.get(subleaf, entry.get(f"0x{_int(subleaf):X}", {}))


def _bit(data: dict, leaf: str, register: str, bit: int) -> int:
    return (_int(_leaf(data, leaf).get(register, 0)) >> bit) & 1


def _fms(data: dict) -> int | None:
    signature = data.get("cpu", {}).get("signature")
    if signature is not None:
        return _int(signature)
    value = _leaf(data, "0x00000001").get("eax")
    return _int(value) if value is not None else None


def parse_madt(path: Path) -> tuple[set[int], set[int], list[int]]:
    """Return enabled processor UIDs, concrete NMI UIDs and raw bytes.

    Supports legacy Local APIC entries (types 0/4) and x2APIC entries
    (types 9/10).  NMI wildcard UIDs 0xFF and 0xFFFFFFFF are retained in the
    NMI set and handled by the comparison logic.
    """
    data = path.read_bytes()
    if len(data) < 44 or data[:4] != b"APIC":
        raise ValueError(f"{path}: not an ACPI MADT/APIC table")
    declared = struct.unpack_from("<I", data, 4)[0]
    if declared != len(data):
        raise ValueError(f"{path}: declared length {declared} != file length {len(data)}")
    if sum(data) & 0xFF:
        raise ValueError(f"{path}: invalid ACPI checksum")
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
        elif kind == 9 and length >= 16:
            uid, flags = struct.unpack_from("<II", data, offset + 8)
            if flags & 1:
                cpu_uids.add(uid)
        elif kind == 10 and length >= 12:
            nmi_uids.add(struct.unpack_from("<I", data, offset + 4)[0])
        offset += length
    return cpu_uids, nmi_uids, list(data)


def madt_summary(path: Path) -> dict:
    cpus, nmis, raw = parse_madt(path)
    return {
        "path": str(path),
        "bytes": len(raw),
        "checksum_valid": (sum(raw) & 0xFF) == 0,
        "active_cpu_uids": sorted(cpus),
        "nmi_uids": sorted(nmis),
    }


def validate_madt(path: Path) -> list[tuple[str, str]]:
    cpus, nmis, _ = parse_madt(path)
    wildcards = {uid for uid in nmis if uid in (0xFF, 0xFFFFFFFF)}
    concrete_nmis = nmis - wildcards
    issues: list[tuple[str, str]] = []
    if not wildcards and cpus != concrete_nmis:
        missing = sorted(cpus - concrete_nmis)
        orphan = sorted(concrete_nmis - cpus)
        issues.append(("MADT_NMI_UID_MISMATCH", f"missing={missing} orphan={orphan}"))
    if not wildcards and {uid + 1 for uid in cpus} == concrete_nmis:
        issues.append(("NMI_UID_OFFSET_PLUS_ONE", "Local APIC NMI UIDs are shifted by +1"))
    return issues


def cpuid_values(data: dict) -> dict:
    avx512f = bool(_bit(data, "0x00000007", "ebx", 16))
    avx512vl = bool(_bit(data, "0x00000007", "ebx", 31))
    vp2 = bool(_bit(data, "0x00000007", "edx", 8))
    xstate_eax = _int(_leaf(data, "0x0000000D").get("eax", 0))
    xstate = {str(state): bool(xstate_eax & (1 << state)) for state in (5, 6, 7)}
    return {
        "fms": f"{_fms(data):08X}" if _fms(data) is not None else None,
        "cpuid_7_0": _leaf(data, "0x00000007"),
        "cpuid_d_0": _leaf(data, "0x0000000D"),
        "avx512f": avx512f,
        "avx512vl": avx512vl,
        "avx512_vp2intersect": vp2,
        "xstate_components_5_6_7": xstate,
        "missing_avx512_xstate": [state for state, available in xstate.items() if not available],
    }


def validate_cpuid(data: dict) -> list[tuple[str, str]]:
    values = cpuid_values(data)
    issues: list[tuple[str, str]] = []
    if values["avx512_vp2intersect"] and not values["avx512f"]:
        issues.append(("ORPHAN_AVX512_VP2INTERSECT", "VP2INTERSECT=1 while AVX512F=0"))
    if values["avx512_vp2intersect"] and values["missing_avx512_xstate"]:
        issues.append(("AVX512_XSTATE_UNAVAILABLE", f"missing XSTATE components={values['missing_avx512_xstate']}"))
    return issues


def build_report(data: dict, madt: Path | None = None) -> dict:
    cpuid = cpuid_values(data)
    cpuid_issues = validate_cpuid(data)
    madt_issues: list[tuple[str, str]] = []
    summary = None
    if madt:
        summary = madt_summary(madt)
        madt_issues = validate_madt(madt)
    issues = [
        {"code": code, "message": message, "source": "cpuid"}
        for code, message in cpuid_issues
    ] + [
        {"code": code, "message": message, "source": "madt"}
        for code, message in madt_issues
    ]
    known_signature_match = _fms(data) == KNOWN_FMS
    cpuid_platform_match = known_signature_match and any(
        issue[0] == "ORPHAN_AVX512_VP2INTERSECT" for issue in cpuid_issues
    ) and any(issue[0] == "AVX512_XSTATE_UNAVAILABLE" for issue in cpuid_issues)
    checks = [
        {"name": "CPUID/XSTATE", "status": "FAIL" if cpuid_issues else "PASS", "values": cpuid},
    ]
    if madt:
        checks.append({"name": "MADT", "status": "FAIL" if madt_issues else "PASS", "summary": summary})
    return {
        "schema_version": 1,
        "validator_version": VALIDATOR_VERSION,
        "input": data.get("source", "normalized platform JSON"),
        "cpu": data.get("cpu", {}),
        "checks": checks,
        "issues": issues,
        "madt": summary,
        "known_signature_match": known_signature_match,
        "platform_match": cpuid_platform_match,
        "classification": "Affected" if cpuid_platform_match else ("Not affected" if known_signature_match else "Unknown"),
        "recommendation": 'bcdedit /set "{current}" xsavedisable 1' if cpuid_platform_match else None,
    }


def print_report(result: dict) -> None:
    print("BIOS Interposer Platform Validator")
    cpu = result["cpu"]
    print("\nCPU")
    print(f"  Vendor: {cpu.get('vendor', 'unknown')}")
    print(f"  CPUID signature: {cpu.get('signature', result['checks'][0]['values'].get('fms', 'unknown'))}")
    print(f"  Logical processors: {cpu.get('logical_processors', 'unknown')}")
    for check in result["checks"]:
        print(f"\n{check['name']}")
        for issue in result["issues"]:
            if issue["source"].lower() == check["name"].split("/")[0].lower() or issue["source"] == check["name"].lower():
                print(f"  [FAIL] {issue['code']}: {issue['message']}")
        if not any(issue["source"] == ("cpuid" if check["name"].startswith("CPUID") else "madt") for issue in result["issues"]):
            print(f"  [{check['status']}] {check['name']}")
    print("\nClassification")
    marker = "MATCH" if result["platform_match"] else ("NO MATCH" if result["known_signature_match"] else "UNKNOWN")
    print(f"  [{marker}] {result['classification']}")
    if result["recommendation"]:
        print("\nKnown workaround:")
        print(f"  {result['recommendation']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path, default=DEFAULT_INPUT, help="normalized platform JSON")
    parser.add_argument("--madt", type=Path, help="optional ACPI MADT binary")
    parser.add_argument("--report-json", type=Path, help="write the complete machine-readable report")
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    result = build_report(data, args.madt)
    print_report(result)
    if args.report_json:
        args.report_json.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if result["classification"] != "Affected" or not result["issues"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
