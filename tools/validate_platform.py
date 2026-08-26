#!/usr/bin/env python3
"""Validate normalized platform evidence without collecting live hardware data."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path


VALIDATOR_VERSION = "0.5.0"
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


def _register_present(data: dict, leaf: str, register: str, subleaf: str = "0") -> bool:
    return register in _leaf(data, leaf, subleaf)


def cpuid_data_complete(data: dict) -> tuple[bool, list[str]]:
    """Require the CPUID leaves used for Hyper-V XSAVE classification."""
    missing: list[str] = []
    if not _register_present(data, "0x00000007", "ebx"):
        missing.append("CPUID.7.0.EBX")
    if not _register_present(data, "0x00000007", "edx"):
        missing.append("CPUID.7.0.EDX")
    if not _register_present(data, "0x0000000D", "eax"):
        missing.append("CPUID.D.0.EAX")
    return not missing, missing


def resolve_madt_path(data: dict, input_path: Path, cli_madt: Path | None) -> Path | None:
    if cli_madt is not None:
        return cli_madt
    madt_info = data.get("madt")
    if not isinstance(madt_info, dict):
        return None
    raw_path = madt_info.get("path")
    if not raw_path:
        return None
    path = Path(raw_path)
    if not path.is_absolute():
        path = (input_path.parent / path).resolve()
    return path


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
            _, flags, uid = struct.unpack_from("<III", data, offset + 4)
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
    orphan = sorted(concrete_nmis - cpus)
    if wildcards:
        missing: list[int] = []
    else:
        missing = sorted(cpus - concrete_nmis)
    if missing or orphan:
        issues.append(("MADT_NMI_UID_MISMATCH", f"missing={missing} orphan={orphan}"))
    if not wildcards and {uid + 1 for uid in cpus} == concrete_nmis:
        issues.append(("NMI_UID_OFFSET_PLUS_ONE", "Local APIC NMI UIDs are shifted by +1"))
    return issues


def cpuid_values(data: dict) -> dict:
    leaf1 = _leaf(data, "0x00000001")
    leaf1_ecx = _int(leaf1["ecx"]) if "ecx" in leaf1 else None
    avx512f = bool(_bit(data, "0x00000007", "ebx", 16))
    avx512vl = bool(_bit(data, "0x00000007", "ebx", 31))
    vp2 = bool(_bit(data, "0x00000007", "edx", 8))
    xstate_eax = _int(_leaf(data, "0x0000000D").get("eax", 0))
    xstate = {str(state): bool(xstate_eax & (1 << state)) for state in (5, 6, 7)}
    return {
        "fms": f"{_fms(data):08X}" if _fms(data) is not None else None,
        "cpuid_1_0": leaf1,
        "xsave": bool(leaf1_ecx & (1 << 26)) if leaf1_ecx is not None else None,
        "osxsave": bool(leaf1_ecx & (1 << 27)) if leaf1_ecx is not None else None,
        "avx": bool(leaf1_ecx & (1 << 28)) if leaf1_ecx is not None else None,
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


def windows_processor_features(data: dict) -> dict[str, bool] | None:
    raw = data.get("collection", {}).get("windows_processor_features", {}).get("features")
    if not isinstance(raw, dict):
        return None
    result: dict[str, bool] = {}
    for name, feature in raw.items():
        if isinstance(feature, dict) and isinstance(feature.get("available"), bool):
            result[name] = feature["available"]
    return result or None


def windows_xsave_disabled_state(data: dict, known_signature_match: bool) -> bool:
    features = windows_processor_features(data)
    return bool(
        known_signature_match
        and features
        and features.get("xsave_enabled") is False
        and features.get("avx") is False
        and features.get("avx2") is False
    )


def bcd_xsavedisable_enabled(data: dict) -> bool:
    bcd = data.get("collection", {}).get("windows_bcd", {})
    if not isinstance(bcd, dict) or bcd.get("available") is not True:
        return False
    elements = bcd.get("current_entry", {}).get("elements", {})
    if not isinstance(elements, dict) or "xsavedisable" not in elements:
        return False
    try:
        return _int(elements["xsavedisable"]) != 0
    except (TypeError, ValueError):
        return False


def diagnostic_mitigation(matches_affected_signature: bool, active: bool = False) -> dict | None:
    if not matches_affected_signature and not active:
        return None
    return {
        "command": 'bcdedit /set "{diagnostic-entry-guid}" xsavedisable 1',
        "active": active,
        "purpose": "Confirm XSAVE/XSTATE involvement in the early Hyper-V startup failure",
        "suitable_for_daily_use": False,
        "known_impact": [
            "AVX unavailable",
            "AVX2 unavailable",
            "AVX-512 unavailable",
        ],
        "not_implied": [
            "SSE unavailable",
            "SSE2 unavailable",
        ],
        "causal_limit": (
            "This globally disables kernel XSAVE handling; it localizes the failure to the "
            "XSAVE/XSTATE path but does not identify VP2INTERSECT or any other single component "
            "as the exact trigger."
        ),
    }


def build_report(data: dict, madt: Path | None = None) -> dict:
    cpuid = cpuid_values(data)
    cpuid_complete, missing_cpuid = cpuid_data_complete(data)
    cpuid_issues = validate_cpuid(data) if cpuid_complete else []
    if not cpuid_complete:
        cpuid_issues = [
            ("INCOMPLETE_CPUID", f"Required CPUID data missing: {', '.join(missing_cpuid)}"),
        ]
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
    windows_features = windows_processor_features(data)
    xsave_disabled_state = windows_xsave_disabled_state(data, known_signature_match)
    bcd_xsavedisable = bcd_xsavedisable_enabled(data)
    bypass_active = xsave_disabled_state and bcd_xsavedisable
    windows_issues: list[tuple[str, str]] = []
    if xsave_disabled_state:
        windows_issues.append((
            "WINDOWS_XSAVE_AVX_UNAVAILABLE",
            (
                "Windows reports XSAVE, AVX and AVX2 unavailable; BCD confirms "
                "xsavedisable is active"
                if bypass_active
                else "Windows reports XSAVE, AVX and AVX2 unavailable; cause is not "
                     "confirmed because BCD does not confirm xsavedisable"
            ),
        ))
    xsave_hyperv_match = cpuid_complete and known_signature_match and any(
        issue[0] == "ORPHAN_AVX512_VP2INTERSECT" for issue in cpuid_issues
    ) and any(issue[0] == "AVX512_XSTATE_UNAVAILABLE" for issue in cpuid_issues)
    cpuid_platform_match = xsave_hyperv_match or xsave_disabled_state
    if not cpuid_complete:
        classification = "Unknown"
    elif bypass_active:
        classification = "Diagnostic bypass active"
    elif xsave_disabled_state:
        classification = "Windows XSAVE/AVX unavailable"
    elif xsave_hyperv_match:
        classification = "Affected"
    elif known_signature_match:
        classification = "Not affected"
    else:
        classification = "Unknown"
    if bypass_active:
        xsave_status = "BYPASS ACTIVE"
    elif xsave_disabled_state:
        xsave_status = "XSAVE UNAVAILABLE (BCD UNCONFIRMED)"
    else:
        xsave_status = (
            "MATCH" if xsave_hyperv_match
            else ("NO MATCH" if known_signature_match and cpuid_complete else "UNKNOWN")
        )
    madt_status = "NOT CHECKED" if madt is None else ("DETECTED" if madt_issues else "CLEAN")
    overall_status = "INCOMPLETE" if not cpuid_complete else ("ISSUES DETECTED" if issues else "CLEAN")
    checks = [
        {
            "name": "CPUID/XSTATE",
            "status": "INCOMPLETE" if not cpuid_complete else ("FAIL" if cpuid_issues else "PASS"),
            "values": cpuid,
        },
    ]
    if windows_features is not None:
        checks.append({
            "name": "WINDOWS",
            "status": "FAIL" if windows_issues else "PASS",
            "values": {
                "processor_features": windows_features,
                "bcd_xsavedisable_confirmed": bcd_xsavedisable,
            },
        })
    if madt:
        checks.append({"name": "MADT", "status": "FAIL" if madt_issues else "PASS", "summary": summary})
    issues.extend(
        {"code": code, "message": message, "source": "windows"}
        for code, message in windows_issues
    )
    if windows_issues and cpuid_complete:
        overall_status = "ISSUES DETECTED"
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
        "xsave_hyperv_signature": {
            "status": xsave_status,
            "match": xsave_hyperv_match,
            "windows_xsave_disabled_state": xsave_disabled_state,
            "bcd_xsavedisable_confirmed": bcd_xsavedisable,
            "diagnostic_bypass_active": bypass_active,
        },
        "madt_firmware_anomaly": {"status": madt_status, "detected": bool(madt_issues)},
        "overall_status": overall_status,
        "cpuid_complete": cpuid_complete,
        "classification": classification,
        "recommendation": None,
        "diagnostic_mitigation": diagnostic_mitigation(xsave_hyperv_match, bypass_active),
    }


def report_exit_code(result: dict) -> int:
    """0 = clean, 1 = issues detected, 2 = insufficient input data."""
    if result["overall_status"] == "INCOMPLETE":
        return 2
    if result["overall_status"] == "ISSUES DETECTED":
        return 1
    return 0


def print_report(result: dict) -> None:
    print("BIOS Interposer Platform Validator")
    cpu = result["cpu"]
    print("\nCPU")
    print(f"  Vendor: {cpu.get('vendor', 'unknown')}")
    print(f"  CPUID signature: {cpu.get('signature', result['checks'][0]['values'].get('fms', 'unknown'))}")
    print(f"  Logical processors: {cpu.get('logical_processors', 'unknown')}")
    for check in result["checks"]:
        print(f"\n{check['name']}")
        check_source = (
            "cpuid" if check["name"].startswith("CPUID")
            else "madt" if check["name"] == "MADT"
            else "windows"
        )
        check_issues = [issue for issue in result["issues"] if issue["source"] == check_source]
        for issue in check_issues:
            print(f"  [FAIL] {issue['code']}: {issue['message']}")
        if not check_issues:
            print(f"  [{check['status']}] {check['name']}")
    print("\nClassification")
    xsave = result["xsave_hyperv_signature"]
    madt = result["madt_firmware_anomaly"]
    print(f"  Known Hyper-V XSAVE signature: [{xsave['status']}]")
    print(f"  MADT firmware anomaly: [{madt['status']}]")
    print(f"  Overall platform status: {result['overall_status']}")
    print(f"  Hyper-V XSAVE classification: {result['classification']}")
    mitigation = result["diagnostic_mitigation"]
    if mitigation:
        print("\nDiagnostic mitigation (not recommended for daily use):")
        print(f"  {mitigation['command']}")
        print(f"  Purpose: {mitigation['purpose']}")
        print(f"  Known impact: {', '.join(mitigation['known_impact'])}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path, default=DEFAULT_INPUT, help="normalized platform JSON")
    parser.add_argument("--madt", type=Path, help="optional ACPI MADT binary")
    parser.add_argument("--report-json", type=Path, help="write the complete machine-readable report")
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    madt_path = resolve_madt_path(data, args.input, args.madt)
    result = build_report(data, madt_path)
    print_report(result)
    if args.report_json:
        args.report_json.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report_exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())
