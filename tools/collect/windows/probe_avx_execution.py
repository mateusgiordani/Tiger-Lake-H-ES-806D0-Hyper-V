#!/usr/bin/env python3
"""Execute one AVX and one AVX2 instruction in isolated child processes."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys


PROBES = {
    # vxorps ymm0, ymm0, ymm0; vzeroupper; ret
    "avx": bytes.fromhex("C5FC57C0 C5F877 C3"),
    # vpaddd ymm0, ymm0, ymm0; vzeroupper; ret
    "avx2": bytes.fromhex("C5FDFEC0 C5F877 C3"),
}

PROCESSOR_FEATURE_IDS = {
    "avx": 39,   # PF_AVX_INSTRUCTIONS_AVAILABLE
    "avx2": 40,  # PF_AVX2_INSTRUCTIONS_AVAILABLE
}


def execute_machine_code(code: bytes) -> None:
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
    address = kernel32.VirtualAlloc(None, len(code), 0x3000, 0x40)
    if not address:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        ctypes.memmove(address, code, len(code))
        ctypes.CFUNCTYPE(None)(address)()
    finally:
        if not kernel32.VirtualFree(address, 0, 0x8000):
            raise ctypes.WinError(ctypes.get_last_error())


def processor_feature_available(feature_id: int) -> bool:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.IsProcessorFeaturePresent.restype = ctypes.c_int
    kernel32.IsProcessorFeaturePresent.argtypes = (ctypes.c_uint32,)
    return bool(kernel32.IsProcessorFeaturePresent(feature_id))


def run_probes() -> dict[str, object]:
    results: dict[str, object] = {}
    for name in PROBES:
        completed = subprocess.run(
            [sys.executable, str(__file__), "--child", name],
            capture_output=True,
            text=True,
            check=False,
        )
        results[name] = {
            "status": "PASS" if completed.returncode == 0 else "FAIL",
            "exit_code": completed.returncode,
            "windows_feature_available": processor_feature_available(
                PROCESSOR_FEATURE_IDS[name]
            ),
        }
    return {
        "platform": "Windows",
        "probe_isolation": "one child process per instruction set",
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child", choices=sorted(PROBES))
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    args = parser.parse_args()
    if os.name != "nt":
        print("This probe requires Windows.", file=sys.stderr)
        return 2
    if args.child:
        execute_machine_code(PROBES[args.child])
        return 0

    report = run_probes()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for name, result in report["results"].items():
            print(f"{name.upper()}: {result['status']}")
    return 0 if all(
        result["status"] == "PASS" for result in report["results"].values()
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
