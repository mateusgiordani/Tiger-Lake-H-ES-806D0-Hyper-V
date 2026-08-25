#!/usr/bin/env python3
"""Dump raw CPUID leaves on Windows, including a per-logical-CPU comparison.

This is read-only and uses the unprivileged CPUID instruction.  It does not
install a driver and cannot read VMX capability MSRs; use the Linux MSR
collector for that separate step.
"""

from __future__ import annotations

import ctypes
import argparse
import json
import os
import struct
from collections import defaultdict
from pathlib import Path


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.VirtualAlloc.restype = ctypes.c_void_p
kernel32.VirtualAlloc.argtypes = (
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.c_ulong,
    ctypes.c_ulong,
)
kernel32.VirtualFree.restype = ctypes.c_int
kernel32.VirtualFree.argtypes = (ctypes.c_void_p, ctypes.c_size_t, ctypes.c_ulong)
kernel32.GetCurrentThread.restype = ctypes.c_void_p
kernel32.SetThreadAffinityMask.restype = ctypes.c_size_t
kernel32.SetThreadAffinityMask.argtypes = (ctypes.c_void_p, ctypes.c_size_t)


# Windows x64 ABI: RCX=leaf, RDX=subleaf, R8=UINT32[4] output.
# RBX is nonvolatile and must be preserved across CPUID.
CODE = bytes.fromhex(
    "53"          # push rbx
    "8BC1"        # mov eax, ecx
    "8BCA"        # mov ecx, edx
    "0FA2"        # cpuid
    "418900"      # mov [r8], eax
    "41895804"    # mov [r8+4], ebx
    "41894808"    # mov [r8+8], ecx
    "4189500C"    # mov [r8+12], edx
    "5B"          # pop rbx
    "C3"          # ret
)

MEM_COMMIT_RESERVE = 0x3000
MEM_RELEASE = 0x8000
PAGE_EXECUTE_READWRITE = 0x40


class Cpuid:
    def __init__(self) -> None:
        self.address = kernel32.VirtualAlloc(
            None, len(CODE), MEM_COMMIT_RESERVE, PAGE_EXECUTE_READWRITE
        )
        if not self.address:
            raise ctypes.WinError(ctypes.get_last_error())
        ctypes.memmove(self.address, CODE, len(CODE))
        signature = ctypes.CFUNCTYPE(
            None, ctypes.c_uint32, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)
        )
        self.function = signature(self.address)

    def close(self) -> None:
        if self.address:
            if not kernel32.VirtualFree(self.address, 0, MEM_RELEASE):
                raise ctypes.WinError(ctypes.get_last_error())
            self.address = 0

    def __call__(self, leaf: int, subleaf: int = 0) -> tuple[int, int, int, int]:
        output = (ctypes.c_uint32 * 4)()
        self.function(leaf, subleaf, output)
        return tuple(int(value) for value in output)  # type: ignore[return-value]

    def __enter__(self) -> "Cpuid":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def regs(values: tuple[int, int, int, int]) -> dict[str, str]:
    return dict(zip(("eax", "ebx", "ecx", "edx"), (f"0x{x:08X}" for x in values)))


def vendor(values: tuple[int, int, int, int]) -> str:
    _, ebx, ecx, edx = values
    return struct.pack("<III", ebx, edx, ecx).decode("ascii", "replace")


def brand(cpuid: Cpuid, maximum_extended: int) -> str:
    if maximum_extended < 0x80000004:
        return ""
    data = b"".join(struct.pack("<IIII", *cpuid(leaf)) for leaf in range(0x80000002, 0x80000005))
    return data.rstrip(b"\0 ").decode("ascii", "replace")


def wanted_subleaves(cpuid: Cpuid, leaf: int) -> list[int]:
    if leaf == 0x4:
        result = []
        for subleaf in range(64):
            result.append(subleaf)
            if cpuid(leaf, subleaf)[0] & 0x1F == 0:
                break
        return result
    if leaf == 0x7:
        return list(range(min(cpuid(leaf, 0)[0], 64) + 1))
    if leaf in (0xB, 0x1F):
        result = []
        for subleaf in range(32):
            result.append(subleaf)
            if cpuid(leaf, subleaf)[1] == 0:
                break
        return result
    if leaf == 0xD:
        return list(range(64))
    if leaf in (0xF, 0x10, 0x12, 0x14, 0x17, 0x18):
        return list(range(16))
    return [0]


def enumerate_leaves(cpuid: Cpuid) -> dict[str, object]:
    maximum_basic = cpuid(0)[0]
    maximum_extended = cpuid(0x80000000)[0]
    leaves: dict[str, dict[str, dict[str, str]]] = {}
    ranges = [range(maximum_basic + 1)]
    if 0x80000000 <= maximum_extended <= 0x80000100:
        ranges.append(range(0x80000000, maximum_extended + 1))
    for leaf_range in ranges:
        for leaf in leaf_range:
            entries: dict[str, dict[str, str]] = {}
            for subleaf in wanted_subleaves(cpuid, leaf):
                values = cpuid(leaf, subleaf)
                # Keep mandatory subleaf zero and any nonzero extended subleaf.
                if subleaf == 0 or any(values):
                    entries[f"0x{subleaf:X}"] = regs(values)
            leaves[f"0x{leaf:08X}"] = entries
    return {
        "vendor": vendor(cpuid(0)),
        "brand": brand(cpuid, maximum_extended),
        "max_basic": f"0x{maximum_basic:08X}",
        "max_extended": f"0x{maximum_extended:08X}",
        "leaves": leaves,
    }


def per_cpu_fingerprint(cpuid: Cpuid) -> dict[str, object]:
    count = min(os.cpu_count() or 1, ctypes.sizeof(ctypes.c_size_t) * 8)
    thread = kernel32.GetCurrentThread()
    snapshots: dict[str, dict[str, list[str]]] = {}
    errors: list[str] = []
    probes = ((1, 0), (7, 0), (7, 1), (0xD, 0), (0xD, 1), (0x1A, 0))
    for cpu in range(count):
        previous = kernel32.SetThreadAffinityMask(thread, 1 << cpu)
        if not previous:
            errors.append(f"LP {cpu}: SetThreadAffinityMask failed: {ctypes.get_last_error()}")
            continue
        try:
            snapshots[str(cpu)] = {
                f"0x{leaf:X}:0x{subleaf:X}": [f"0x{x:08X}" for x in cpuid(leaf, subleaf)]
                for leaf, subleaf in probes
            }
        finally:
            kernel32.SetThreadAffinityMask(thread, previous)

    by_fingerprint: defaultdict[str, list[int]] = defaultdict(list)
    for cpu, snapshot in snapshots.items():
        # APIC IDs legitimately differ, so mask leaf 1 EBX[31:24].
        normalized = json.loads(json.dumps(snapshot))
        leaf1 = normalized["0x1:0x0"]
        leaf1[1] = f"0x{int(leaf1[1], 16) & 0x00FFFFFF:08X}"
        key = json.dumps(normalized, sort_keys=True)
        by_fingerprint[key].append(int(cpu))
    return {
        "logical_processors_checked": len(snapshots),
        "identical_feature_groups": list(by_fingerprint.values()),
        "snapshots": snapshots,
        "errors": errors,
    }


def hyperv_relevant_consistency(cpuid: Cpuid) -> dict[str, object]:
    """Highlight feature combinations that a strict hypervisor may validate."""
    leaf7_eax, leaf7_ebx, leaf7_ecx, leaf7_edx = cpuid(7, 0)
    xstate_eax, xstate_ebx, xstate_ecx, xstate_edx = cpuid(0xD, 0)
    xss_eax, xss_ebx, xss_ecx, xss_edx = cpuid(0xD, 1)
    avx512f = bool(leaf7_ebx & (1 << 16))
    avx512vl = bool(leaf7_ebx & (1 << 31))
    vp2intersect = bool(leaf7_edx & (1 << 8))
    pku = bool(leaf7_ecx & (1 << 3))
    cet_shadow_stack = bool(leaf7_ecx & (1 << 7))
    cet_ibt = bool(leaf7_edx & (1 << 20))
    avx512_xstate = {
        "opmask_bit_5": bool(xstate_eax & (1 << 5)),
        "zmm_hi256_bit_6": bool(xstate_eax & (1 << 6)),
        "hi16_zmm_bit_7": bool(xstate_eax & (1 << 7)),
    }
    related_xstate = {
        "pkru_xcr0_bit_9": bool(xstate_eax & (1 << 9)),
        "cet_user_xss_bit_11": bool(xss_ecx & (1 << 11)),
        "cet_supervisor_xss_bit_12": bool(xss_ecx & (1 << 12)),
    }
    full_avx512_xstate = all(avx512_xstate.values())
    orphan_vp2intersect = vp2intersect and not (avx512f or avx512vl) and not full_avx512_xstate
    inconsistent_pku_state = pku and not related_xstate["pkru_xcr0_bit_9"]
    inconsistent_cet_state = cet_shadow_stack and not (
        related_xstate["cet_user_xss_bit_11"] and related_xstate["cet_supervisor_xss_bit_12"]
    )
    return {
        "raw": {
            "cpuid_7_0": regs((leaf7_eax, leaf7_ebx, leaf7_ecx, leaf7_edx)),
            "cpuid_d_0": regs((xstate_eax, xstate_ebx, xstate_ecx, xstate_edx)),
            "cpuid_d_1": regs((xss_eax, xss_ebx, xss_ecx, xss_edx)),
        },
        "avx512f": avx512f,
        "avx512vl": avx512vl,
        "avx512_vp2intersect": vp2intersect,
        "avx512_xstate": avx512_xstate,
        "orphan_avx512_vp2intersect": orphan_vp2intersect,
        "pku": pku,
        "cet_shadow_stack": cet_shadow_stack,
        "cet_ibt": cet_ibt,
        "related_xstate": related_xstate,
        "inconsistent_pku_state": inconsistent_pku_state,
        "inconsistent_cet_state": inconsistent_cet_state,
        "interpretation": (
            "VP2INTERSECT is enumerated while AVX512F, AVX512VL and XCR0 AVX-512 "
            "state components 5-7 are absent; retest after changing the firmware AVX3 option. "
            f"PKU/PKRU consistency={not inconsistent_pku_state}; "
            f"CET/XSS consistency={not inconsistent_cet_state}."
            if orphan_vp2intersect
            else (
                "No orphan VP2INTERSECT combination detected. "
                f"PKU/PKRU consistency={not inconsistent_pku_state}; "
                f"CET/XSS consistency={not inconsistent_cet_state}."
            )
        ),
    }


def timekeeping_consistency(cpuid: Cpuid) -> dict[str, object]:
    """Decode invariant-TSC and the architectural TSC/crystal ratio."""
    _, _, _, ext7_edx = cpuid(0x80000007, 0)
    denominator, numerator, crystal_hz, _ = cpuid(0x15, 0)
    base_mhz, max_mhz, bus_mhz, _ = cpuid(0x16, 0)
    tsc_hz = None
    if denominator and numerator and crystal_hz:
        tsc_hz = crystal_hz * numerator / denominator
    base_delta_percent = None
    if tsc_hz and base_mhz:
        base_delta_percent = abs(tsc_hz / 1_000_000 - base_mhz) / base_mhz * 100
    coherent = bool(ext7_edx & (1 << 8)) and tsc_hz is not None
    return {
        "invariant_tsc": bool(ext7_edx & (1 << 8)),
        "cpuid_15": {
            "denominator": denominator,
            "numerator": numerator,
            "crystal_hz": crystal_hz,
            "derived_tsc_hz": round(tsc_hz) if tsc_hz is not None else None,
        },
        "cpuid_16_mhz": {"base": base_mhz, "maximum": max_mhz, "bus": bus_mhz},
        "derived_tsc_vs_base_delta_percent": (
            round(base_delta_percent, 4) if base_delta_percent is not None else None
        ),
        "architecturally_coherent": coherent,
        "interpretation": (
            "Invariant TSC is present and CPUID leaf 0x15 supplies a complete ratio; "
            "no static CPUID timing inconsistency was detected. Per-LP TSC skew still "
            "requires a privileged measurement or a hypervisor-debug trace."
            if coherent
            else "The architectural TSC description is incomplete or non-invariant."
        ),
    }


def normalized_platform(report: dict[str, object]) -> dict[str, object]:
    """Convert this collector's rich capture into the validator schema."""
    leaves = report["leaves"]
    leaf1 = leaves.get("0x00000001", {}).get("0x0", {})
    eax = int(leaf1.get("eax", "0"), 16)
    family = (eax >> 8) & 0xF
    model = (eax >> 4) & 0xF
    if family == 0xF:
        family += (eax >> 20) & 0xFF
    if family in (0x6, 0xF):
        model |= ((eax >> 16) & 0xF) << 4
    stepping = eax & 0xF
    comparison = report["per_cpu_comparison"]
    return {
        "schema_version": 1,
        "source": "Windows CPUID collector",
        "cpu": {
            "vendor": report["vendor"],
            "brand": report["brand"],
            "family": family,
            "model": model,
            "stepping": stepping,
            "signature": f"{eax:08X}",
            "logical_processors": comparison["logical_processors_checked"],
        },
        "cpuid": leaves,
        "collection": {
            "per_cpu_comparison": comparison,
            "hyperv_relevant_consistency": report["hyperv_relevant_consistency"],
            "timekeeping_consistency": report["timekeeping_consistency"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normalized", type=Path, help="write validator-compatible platform JSON")
    args = parser.parse_args()
    with Cpuid() as cpuid:
        report = enumerate_leaves(cpuid)
        report["hyperv_relevant_consistency"] = hyperv_relevant_consistency(cpuid)
        report["timekeeping_consistency"] = timekeeping_consistency(cpuid)
        report["per_cpu_comparison"] = per_cpu_fingerprint(cpuid)
    if args.normalized:
        normalized = normalized_platform(report)
        args.normalized.write_text(json.dumps(normalized, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(normalized, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
