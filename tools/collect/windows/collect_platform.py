#!/usr/bin/env python3
"""Collect a normalized Windows platform JSON for validate_platform.py."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import dump_acpi_windows
import dump_cpuid_windows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="normalized platform JSON output")
    parser.add_argument("--madt-output", type=Path, help="also save the raw APIC table")
    args = parser.parse_args()
    with dump_cpuid_windows.Cpuid() as cpuid:
        report = dump_cpuid_windows.enumerate_leaves(cpuid)
        report["hyperv_relevant_consistency"] = dump_cpuid_windows.hyperv_relevant_consistency(cpuid)
        report["timekeeping_consistency"] = dump_cpuid_windows.timekeeping_consistency(cpuid)
        report["per_cpu_comparison"] = dump_cpuid_windows.per_cpu_fingerprint(cpuid)
        report["windows_processor_features"] = dump_cpuid_windows.windows_processor_features()
    normalized = dump_cpuid_windows.normalized_platform(report)
    if args.madt_output:
        args.madt_output.parent.mkdir(parents=True, exist_ok=True)
        args.madt_output.write_bytes(dump_acpi_windows.read_firmware_table("APIC"))
        normalized["madt"] = {"path": str(args.madt_output)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(normalized, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
