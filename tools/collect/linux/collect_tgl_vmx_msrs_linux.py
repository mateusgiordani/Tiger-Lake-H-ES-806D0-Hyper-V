#!/usr/bin/env python3
"""Collect read-only Tiger Lake VMX/MSR evidence from a Linux live system.

Run as root after loading the standard Linux ``msr`` module::

    sudo modprobe msr
    sudo python3 collect_tgl_vmx_msrs_linux.py > tgl-vmx-msrs.json

The script never writes an MSR.  It compares every online logical processor,
because a single AP with different VMX controls is enough to break Hyper-V's
early multiprocessor launch.
"""

from __future__ import annotations

import json
import os
import platform
import re
from collections import defaultdict
from pathlib import Path


MSRS = {
    0x00000010: "IA32_TIME_STAMP_COUNTER",
    0x00000017: "IA32_PLATFORM_ID",
    0x0000001B: "IA32_APIC_BASE",
    0x0000003A: "IA32_FEATURE_CONTROL",
    0x0000008B: "IA32_BIOS_SIGN_ID",
    0x000000CE: "MSR_PLATFORM_INFO",
    0x000000FE: "IA32_MTRRCAP",
    0x0000010A: "IA32_ARCH_CAPABILITIES",
    0x00000122: "IA32_TSX_CTRL",
    0x00000277: "IA32_PAT",
    0x000002FF: "IA32_MTRR_DEF_TYPE",
    0x00000480: "IA32_VMX_BASIC",
    0x00000481: "IA32_VMX_PINBASED_CTLS",
    0x00000482: "IA32_VMX_PROCBASED_CTLS",
    0x00000483: "IA32_VMX_EXIT_CTLS",
    0x00000484: "IA32_VMX_ENTRY_CTLS",
    0x00000485: "IA32_VMX_MISC",
    0x00000486: "IA32_VMX_CR0_FIXED0",
    0x00000487: "IA32_VMX_CR0_FIXED1",
    0x00000488: "IA32_VMX_CR4_FIXED0",
    0x00000489: "IA32_VMX_CR4_FIXED1",
    0x0000048A: "IA32_VMX_VMCS_ENUM",
    0x0000048B: "IA32_VMX_PROCBASED_CTLS2",
    0x0000048C: "IA32_VMX_EPT_VPID_CAP",
    0x0000048D: "IA32_VMX_TRUE_PINBASED_CTLS",
    0x0000048E: "IA32_VMX_TRUE_PROCBASED_CTLS",
    0x0000048F: "IA32_VMX_TRUE_EXIT_CTLS",
    0x00000490: "IA32_VMX_TRUE_ENTRY_CTLS",
    0x00000491: "IA32_VMX_VMFUNC",
    0x00000492: "IA32_VMX_PROCBASED_CTLS3",
    0x00000493: "IA32_VMX_EXIT_CTLS2",
}

PROCBASED2_FEATURES = {
    0: "virtualize_apic_accesses",
    1: "ept",
    3: "rdtscp",
    4: "virtualize_x2apic",
    5: "vpid",
    7: "unrestricted_guest",
    8: "apic_register_virtualization",
    9: "virtual_interrupt_delivery",
    12: "invpcid",
    13: "vm_functions",
    14: "vmcs_shadowing",
    17: "page_modification_logging",
    18: "ept_violation_ve",
    20: "xsaves_xrstors",
    22: "mode_based_execute_control",
    23: "sub_page_write_permissions",
    25: "tsc_scaling",
    26: "user_wait_pause",
    30: "bus_lock_detection",
}

EPT_VPID_FEATURES = {
    0: "execute_only_ept",
    6: "page_walk_length_4",
    8: "ept_uc_memory_type",
    14: "ept_wb_memory_type",
    16: "ept_2mb_pages",
    17: "ept_1gb_pages",
    20: "invept",
    25: "invept_single_context",
    26: "invept_all_contexts",
    32: "invvpid",
    40: "invvpid_individual_address",
    41: "invvpid_single_context",
    42: "invvpid_all_contexts",
    43: "invvpid_single_context_retaining_globals",
}


def online_cpus() -> list[int]:
    text = Path("/sys/devices/system/cpu/online").read_text().strip()
    result: list[int] = []
    for item in text.split(","):
        if "-" in item:
            start, end = map(int, item.split("-", 1))
            result.extend(range(start, end + 1))
        else:
            result.append(int(item))
    return result


def read_msr(cpu: int, index: int) -> int:
    path = f"/dev/cpu/{cpu}/msr"
    fd = os.open(path, os.O_RDONLY)
    try:
        data = os.pread(fd, 8, index)
    finally:
        os.close(fd)
    if len(data) != 8:
        raise OSError(f"short read from {path} at MSR 0x{index:X}")
    return int.from_bytes(data, "little")


def flags(value: int, definitions: dict[int, str]) -> list[str]:
    return [name for bit, name in definitions.items() if value & (1 << bit)]


def decode_control(value: int) -> dict[str, str]:
    low = value & 0xFFFFFFFF
    high = value >> 32
    return {
        "must_be_1": f"0x{low:08X}",
        "may_be_1": f"0x{high:08X}",
        "must_be_0": f"0x{(~high) & 0xFFFFFFFF:08X}",
    }


def decode_feature_control(value: int) -> dict[str, object]:
    return {
        "locked": bool(value & (1 << 0)),
        "vmx_inside_smx": bool(value & (1 << 1)),
        "vmx_outside_smx": bool(value & (1 << 2)),
        "senter_local_function_mask": f"0x{(value >> 8) & 0x7F:02X}",
        "senter_global_enable": bool(value & (1 << 15)),
        "sgx_launch_control_enable": bool(value & (1 << 17)),
        "sgx_global_enable": bool(value & (1 << 18)),
    }


def decode_apic_base(value: int) -> dict[str, object]:
    return {
        "bsp": bool(value & (1 << 8)),
        "x2apic_enabled": bool(value & (1 << 10)),
        "apic_global_enable": bool(value & (1 << 11)),
        "base": f"0x{value & 0xFFFFFFFFFFFFF000:016X}",
    }


def decode_vmx_basic(value: int) -> dict[str, object]:
    return {
        "vmcs_revision_id": f"0x{value & 0x7FFFFFFF:08X}",
        "vmcs_region_bytes": (value >> 32) & 0x1FFF,
        "physical_address_width_32_only": bool(value & (1 << 48)),
        "dual_monitor_smm": bool(value & (1 << 49)),
        "memory_type": (value >> 50) & 0xF,
        "vm_exit_instruction_info": bool(value & (1 << 54)),
        "true_controls": bool(value & (1 << 55)),
    }


def cpuinfo_signature() -> dict[str, str]:
    text = Path("/proc/cpuinfo").read_text(errors="replace")
    result: dict[str, str] = {}
    for key in ("vendor_id", "cpu family", "model", "stepping", "microcode", "model name"):
        match = re.search(rf"^{re.escape(key)}\s*:\s*(.+)$", text, re.MULTILINE)
        if match:
            result[key] = match.group(1).strip()
    return result


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("Run as root; reading /dev/cpu/*/msr requires privilege")
    cpus = online_cpus()
    values: dict[str, dict[str, object]] = {}
    errors: list[str] = []
    for cpu in cpus:
        cpu_values: dict[str, object] = {}
        for index, name in MSRS.items():
            try:
                value = read_msr(cpu, index)
            except OSError as exc:
                cpu_values[name] = {"error": str(exc)}
                errors.append(f"CPU {cpu} {name}: {exc}")
                continue
            decoded: dict[str, object] = {"index": f"0x{index:X}", "value": f"0x{value:016X}"}
            if name.endswith("_CTLS") or name in {
                "IA32_VMX_PROCBASED_CTLS2",
                "IA32_VMX_TRUE_PINBASED_CTLS",
                "IA32_VMX_TRUE_PROCBASED_CTLS",
                "IA32_VMX_TRUE_EXIT_CTLS",
                "IA32_VMX_TRUE_ENTRY_CTLS",
            }:
                decoded["control"] = decode_control(value)
            if name == "IA32_VMX_PROCBASED_CTLS2":
                decoded["may_enable"] = flags(value >> 32, PROCBASED2_FEATURES)
            if name == "IA32_VMX_EPT_VPID_CAP":
                decoded["capabilities"] = flags(value, EPT_VPID_FEATURES)
            if name == "IA32_FEATURE_CONTROL":
                decoded["feature_control"] = decode_feature_control(value)
            if name == "IA32_APIC_BASE":
                decoded["apic"] = decode_apic_base(value)
            if name == "IA32_VMX_BASIC":
                decoded["vmx_basic"] = decode_vmx_basic(value)
            cpu_values[name] = decoded
        values[str(cpu)] = cpu_values

    fingerprints: defaultdict[str, list[int]] = defaultdict(list)
    for cpu, snapshot in values.items():
        normalized = dict(snapshot)
        # The timestamp counter necessarily advances between sequential reads.
        normalized.pop("IA32_TIME_STAMP_COUNTER", None)
        # Per-CPU APIC base is expected to differ only in the BSP bit.
        apic = normalized.get("IA32_APIC_BASE")
        if isinstance(apic, dict) and "value" in apic:
            apic = dict(apic)
            apic["value"] = f"0x{int(str(apic['value']), 16) & ~(1 << 8):016X}"
            decoded_apic = apic.get("apic")
            if isinstance(decoded_apic, dict):
                decoded_apic = dict(decoded_apic)
                decoded_apic["bsp"] = False
                apic["apic"] = decoded_apic
            normalized["IA32_APIC_BASE"] = apic
        fingerprints[json.dumps(normalized, sort_keys=True)].append(int(cpu))

    report = {
        "collector": "collect_tgl_vmx_msrs_linux.py",
        "kernel": platform.release(),
        "cpuinfo": cpuinfo_signature(),
        "online_cpus": cpus,
        "identical_msr_groups": list(fingerprints.values()),
        "per_cpu": values,
        "errors": errors,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
