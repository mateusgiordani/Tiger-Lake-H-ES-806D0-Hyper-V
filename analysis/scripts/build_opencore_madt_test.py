#!/usr/bin/env python3
"""Build a reversible OpenCore USB tree that patches the Polestar MADT in RAM.

This script never touches a physical USB drive, firmware, BCD, or registry.  It
stages files below analysis/opencore-madt-test after validating the captured
runtime MADT and the exact byte sequence to be replaced.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import plistlib
import shutil
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MADT = ROOT / "analysis" / "acpi-runtime" / "apic.dat"
DEFAULT_OC = ROOT / "analysis" / "tools" / "OpenCore-1.0.7-RELEASE"
DEFAULT_OUTPUT = ROOT / "analysis" / "opencore-madt-test"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def parse_madt(data: bytes) -> dict:
    if len(data) < 44 or data[:4] != b"APIC":
        raise ValueError("Input is not an ACPI MADT/APIC table")
    declared_length = struct.unpack_from("<I", data, 4)[0]
    if declared_length != len(data):
        raise ValueError(
            f"MADT length mismatch: header={declared_length}, file={len(data)}"
        )
    if sum(data) & 0xFF:
        raise ValueError("Captured MADT checksum is invalid")

    records = []
    offset = 44
    while offset < len(data):
        if offset + 2 > len(data):
            raise ValueError(f"Truncated MADT record header at 0x{offset:X}")
        record_type, record_length = data[offset], data[offset + 1]
        if record_length < 2 or offset + record_length > len(data):
            raise ValueError(
                f"Invalid MADT record at 0x{offset:X}: length={record_length}"
            )
        records.append(
            {
                "offset": offset,
                "type": record_type,
                "length": record_length,
                "bytes": data[offset : offset + record_length],
            }
        )
        offset += record_length
    if offset != len(data):
        raise ValueError("MADT record walk did not end at table boundary")

    lapics = [r for r in records if r["type"] == 0]
    nmis = [r for r in records if r["type"] == 4]
    if len(lapics) != 16:
        raise ValueError(f"Expected 16 Local APIC records, found {len(lapics)}")
    if len(nmis) != 16:
        raise ValueError(f"Expected 16 Local APIC NMI records, found {len(nmis)}")
    if any(r["length"] != 6 for r in nmis):
        raise ValueError("All Local APIC NMI records must be exactly 6 bytes")

    nmi_offsets = [r["offset"] for r in nmis]
    expected_offsets = list(range(nmi_offsets[0], nmi_offsets[0] + 16 * 6, 6))
    if nmi_offsets != expected_offsets:
        raise ValueError("Local APIC NMI records are not one contiguous sequence")

    nmi_uids = [r["bytes"][2] for r in nmis]
    if nmi_uids != list(range(1, 17)):
        raise ValueError(f"Expected buggy NMI UIDs 1..16, found {nmi_uids}")

    cpu_uids = [r["bytes"][2] for r in lapics]
    if cpu_uids != list(range(16)):
        raise ValueError(f"Expected CPU UIDs 0..15, found {cpu_uids}")

    find = b"".join(r["bytes"] for r in nmis)
    replacement_records = []
    for uid, record in enumerate(nmis):
        corrected = bytearray(record["bytes"])
        corrected[2] = uid
        replacement_records.append(bytes(corrected))
    replace = b"".join(replacement_records)

    patched = bytearray(data)
    start = nmi_offsets[0]
    patched[start : start + len(replace)] = replace
    patched[9] = 0
    patched[9] = (-sum(patched)) & 0xFF
    if sum(patched) & 0xFF:
        raise AssertionError("Internal patched MADT checksum calculation failed")

    return {
        "declared_length": declared_length,
        "revision": data[8],
        "checksum": data[9],
        "oem_id": data[10:16],
        "oem_table_id": data[16:24],
        "nmi_offset": start,
        "cpu_uids": cpu_uids,
        "nmi_uids_before": nmi_uids,
        "nmi_uids_after": list(range(16)),
        "find": find,
        "replace": replace,
        "patched_table": bytes(patched),
    }


def set_bool_dict_false(values: dict) -> None:
    for key, value in values.items():
        if isinstance(value, bool):
            values[key] = False


def make_config(sample: Path, madt: dict) -> dict:
    config = plistlib.loads(sample.read_bytes())
    for key in [key for key in config if key.startswith("#WARNING")]:
        del config[key]

    config["ACPI"]["Add"] = []
    config["ACPI"]["Delete"] = []
    config["ACPI"]["Patch"] = [
        {
            "Base": "",
            "BaseSkip": 0,
            "Comment": "Polestar MADT Local APIC NMI UID 1-16 to 0-15",
            "Count": 1,
            "Enabled": True,
            "Find": madt["find"],
            "Limit": 0,
            "Mask": b"",
            "OemTableId": madt["oem_table_id"],
            "Replace": madt["replace"],
            "ReplaceMask": b"",
            "Skip": 0,
            "TableLength": madt["declared_length"],
            "TableSignature": b"APIC",
        }
    ]
    set_bool_dict_false(config["ACPI"]["Quirks"])

    config["Booter"]["MmioWhitelist"] = []
    config["Booter"]["Patch"] = []
    set_bool_dict_false(config["Booter"]["Quirks"])
    config["Booter"]["Quirks"]["ProvideMaxSlide"] = 0

    config["DeviceProperties"]["Add"] = {}
    config["DeviceProperties"]["Delete"] = {}

    config["Kernel"]["Add"] = []
    config["Kernel"]["Block"] = []
    config["Kernel"]["Force"] = []
    config["Kernel"]["Patch"] = []
    config["Kernel"]["Emulate"]["Cpuid1Data"] = b"\x00" * 4
    config["Kernel"]["Emulate"]["Cpuid1Mask"] = b"\x00" * 4
    config["Kernel"]["Emulate"]["DummyPowerManagement"] = False
    config["Kernel"]["Emulate"]["MaxKernel"] = ""
    config["Kernel"]["Emulate"]["MinKernel"] = ""
    set_bool_dict_false(config["Kernel"]["Quirks"])
    config["Kernel"]["Quirks"]["SetApfsTrimTimeout"] = -1
    config["Kernel"]["Scheme"]["CustomKernel"] = False
    config["Kernel"]["Scheme"]["FuzzyMatch"] = False
    config["Kernel"]["Scheme"]["KernelArch"] = "Auto"
    config["Kernel"]["Scheme"]["KernelCache"] = "Auto"

    # OpenCore already blesses the standard Microsoft path.  Keeping this
    # empty avoids a redundant-entry validation error while retaining Windows
    # auto-discovery with ScanPolicy=0.
    config["Misc"]["BlessOverride"] = []
    config["Misc"]["Entries"] = []
    config["Misc"]["Tools"] = []
    boot = config["Misc"]["Boot"]
    boot["HideAuxiliary"] = False
    boot["LauncherOption"] = "Disabled"
    boot["PickerMode"] = "Builtin"
    boot["ShowPicker"] = True
    boot["Timeout"] = 10
    debug = config["Misc"]["Debug"]
    debug["AppleDebug"] = False
    debug["ApplePanic"] = False
    debug["DisableWatchDog"] = False
    debug["DisplayLevel"] = 0x80000002
    debug["SysReport"] = False
    debug["Target"] = 3
    security = config["Misc"]["Security"]
    security["AllowSetDefault"] = False
    security["AuthRestart"] = False
    security["BlacklistAppleUpdate"] = False
    security["DmgLoading"] = "Any"
    security["EnablePassword"] = False
    security["ExposeSensitiveData"] = 0
    security["ScanPolicy"] = 0
    security["SecureBootModel"] = "Disabled"
    security["Vault"] = "Optional"
    config["Misc"]["Serial"]["Init"] = False
    config["Misc"]["Serial"]["Override"] = False

    config["NVRAM"]["Add"] = {}
    config["NVRAM"]["Delete"] = {}
    config["NVRAM"]["LegacyOverwrite"] = False
    config["NVRAM"]["LegacySchema"] = {}
    config["NVRAM"]["WriteFlash"] = False

    platform = config["PlatformInfo"]
    platform["Automatic"] = False
    platform["CustomMemory"] = False
    platform["UpdateDataHub"] = False
    platform["UpdateNVRAM"] = False
    platform["UpdateSMBIOS"] = False
    platform["UpdateSMBIOSMode"] = "Create"

    config["UEFI"]["ConnectDrivers"] = True
    config["UEFI"]["Drivers"] = [
        {
            "Arguments": "",
            "Comment": "Required OpenCore runtime driver",
            "Enabled": True,
            "LoadEarly": False,
            "Path": "OpenRuntime.efi",
        }
    ]
    config["UEFI"]["ReservedMemory"] = []
    config["UEFI"]["Unload"] = []
    set_bool_dict_false(config["UEFI"]["Quirks"])
    config["UEFI"]["Quirks"]["ResizeGpuBars"] = -1
    config["UEFI"]["Quirks"]["TscSyncTimeout"] = 0
    config["UEFI"]["Output"]["ProvideConsoleGop"] = True
    config["UEFI"]["Output"]["Resolution"] = "Max"

    return config


def copy_file(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--madt", type=Path, default=DEFAULT_MADT)
    parser.add_argument("--opencore", type=Path, default=DEFAULT_OC)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    madt_path = args.madt.resolve()
    oc_root = args.opencore.resolve()
    output = args.output.resolve()
    madt = parse_madt(madt_path.read_bytes())

    sample = oc_root / "Docs" / "Sample.plist"
    config = make_config(sample, madt)

    if output.exists():
        # This script owns only this explicit staging directory.
        shutil.rmtree(output)
    efi = output / "EFI"
    copy_file(oc_root / "X64" / "EFI" / "BOOT" / "BOOTx64.efi", efi / "BOOT" / "BOOTx64.efi")
    copy_file(oc_root / "X64" / "EFI" / "OC" / "OpenCore.efi", efi / "OC" / "OpenCore.efi")
    copy_file(
        oc_root / "X64" / "EFI" / "OC" / "Drivers" / "OpenRuntime.efi",
        efi / "OC" / "Drivers" / "OpenRuntime.efi",
    )
    (efi / "OC" / "ACPI").mkdir(parents=True, exist_ok=True)
    (efi / "OC" / "Kexts").mkdir(parents=True, exist_ok=True)
    (efi / "OC" / "Resources").mkdir(parents=True, exist_ok=True)
    (efi / "OC" / "Tools").mkdir(parents=True, exist_ok=True)

    config_path = efi / "OC" / "config.plist"
    with config_path.open("wb") as stream:
        plistlib.dump(config, stream, fmt=plistlib.FMT_XML, sort_keys=False)

    enabled_config_path = efi / "OC" / "config-patch-enabled.plist"
    shutil.copy2(config_path, enabled_config_path)
    control = copy.deepcopy(config)
    control["ACPI"]["Patch"][0]["Enabled"] = False
    control_config_path = efi / "OC" / "config-control-disabled.plist"
    with control_config_path.open("wb") as stream:
        plistlib.dump(control, stream, fmt=plistlib.FMT_XML, sort_keys=False)

    patched_reference = output / "patched-apic-reference.dat"
    patched_reference.write_bytes(madt["patched_table"])
    readme = output / "LEIA-ME-TESTE-MADT.md"
    copy_file(ROOT / "analysis" / "OPENCORE_MADT_TEST.md", readme)

    files = [
        efi / "BOOT" / "BOOTx64.efi",
        efi / "OC" / "OpenCore.efi",
        efi / "OC" / "Drivers" / "OpenRuntime.efi",
        config_path,
        enabled_config_path,
        control_config_path,
        patched_reference,
        readme,
    ]
    manifest = {
        "purpose": "Reversible in-memory diagnostic patch for Polestar MADT NMI UIDs",
        "warning": "Staging tree only; no physical USB, BCD, registry, or firmware was modified",
        "source_madt": str(madt_path),
        "source_madt_sha256": sha256(madt_path),
        "madt": {
            "signature": "APIC",
            "length": madt["declared_length"],
            "revision": madt["revision"],
            "oem_id_ascii": madt["oem_id"].decode("ascii", "replace"),
            "oem_table_id_hex": madt["oem_table_id"].hex().upper(),
            "nmi_sequence_offset_hex": f"0x{madt['nmi_offset']:X}",
            "nmi_uids_before": madt["nmi_uids_before"],
            "nmi_uids_after": madt["nmi_uids_after"],
            "find_hex": madt["find"].hex().upper(),
            "replace_hex": madt["replace"].hex().upper(),
            "replacement_count": 1,
        },
        "opencore_source": str(oc_root),
        "files": [
            {
                "path": str(path.relative_to(output)).replace("\\", "/"),
                "size": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in files
        ],
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Staged: {output}")
    print(f"Source MADT SHA-256: {manifest['source_madt_sha256']}")
    print(f"NMI UIDs: {madt['nmi_uids_before']} -> {madt['nmi_uids_after']}")
    print(f"Patch bytes: {len(madt['find'])}, Count=1, TableSignature=APIC, TableLength={madt['declared_length']}")
    print(f"Patched reference checksum: {sum(madt['patched_table']) & 0xFF}")
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
