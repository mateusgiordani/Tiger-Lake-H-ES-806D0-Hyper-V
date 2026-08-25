#!/usr/bin/env python3
"""Safely install or restore the staged OpenCore MADT test on BIOS_BACKUP.

Dry-run is the default.  Installation preserves the existing EFI directory as
EFI-FPT-BACKUP.  Restore preserves the used OpenCore tree as
EFI-OPENCORE-MADT-SAVED instead of deleting it.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "analysis" / "opencore-madt-test"
EXPECTED_VOLUME_LABEL = "BIOS_BACKUP"
EXPECTED_DUMP_HASH = "68E9A8113DDDA6E192AA72417E69BD83A3E37DC10D4F1421F0D3B282E49231BD"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def volume_label(root: Path) -> str:
    if os.name != "nt":
        raise RuntimeError("This safety check is implemented only for Windows")
    name = ctypes.create_unicode_buffer(261)
    ok = ctypes.windll.kernel32.GetVolumeInformationW(
        str(root), name, len(name), None, None, None, None, 0
    )
    if not ok:
        raise ctypes.WinError()
    return name.value


def validate_destination(destination: Path) -> Path:
    resolved = destination.resolve()
    anchor = Path(resolved.anchor).resolve()
    if resolved != anchor or not resolved.drive:
        raise ValueError("Destination must be an explicit drive root such as G:\\")
    label = volume_label(resolved)
    if label != EXPECTED_VOLUME_LABEL:
        raise ValueError(
            f"Refusing volume {resolved}: expected label {EXPECTED_VOLUME_LABEL!r}, found {label!r}"
        )
    for index in range(1, 4):
        dump = resolved / f"polestar_full_{index}.bin"
        if not dump.is_file():
            raise FileNotFoundError(f"Required verified backup is missing: {dump}")
        actual = sha256(dump)
        if actual != EXPECTED_DUMP_HASH:
            raise ValueError(f"Unexpected backup hash for {dump}: {actual}")
    return resolved


def validate_staging(source: Path) -> dict:
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        path = source / Path(entry["path"])
        if not path.is_file():
            raise FileNotFoundError(f"Staged file is missing: {path}")
        if path.stat().st_size != entry["size"] or sha256(path) != entry["sha256"]:
            raise ValueError(f"Staged file failed manifest verification: {path}")
    return manifest


def install(source: Path, destination: Path, apply: bool) -> None:
    current_efi = destination / "EFI"
    fpt_backup = destination / "EFI-FPT-BACKUP"
    if not current_efi.is_dir():
        raise FileNotFoundError(f"Expected existing FPT EFI directory is missing: {current_efi}")
    if not (current_efi / "BOOT" / "BOOTX64.EFI").is_file():
        raise FileNotFoundError("Existing EFI/BOOT/BOOTX64.EFI is missing")
    if fpt_backup.exists():
        raise FileExistsError(f"Refusing to replace existing backup: {fpt_backup}")

    print(f"PLAN: rename {current_efi} -> {fpt_backup}")
    print(f"PLAN: copy {source / 'EFI'} -> {current_efi}")
    if not apply:
        print("DRY-RUN: no files changed; add --apply only during the reboot test window")
        return

    current_efi.rename(fpt_backup)
    try:
        shutil.copytree(source / "EFI", current_efi)
        shutil.copy2(source / "manifest.json", destination / "OPENCORE-MADT-TEST-MANIFEST.json")
        shutil.copy2(source / "LEIA-ME-TESTE-MADT.md", destination / "LEIA-ME-TESTE-MADT.md")
    except Exception:
        if current_efi.exists():
            shutil.rmtree(current_efi)
        fpt_backup.rename(current_efi)
        raise
    print("INSTALLED: existing FPT EFI preserved as EFI-FPT-BACKUP")


def restore(source: Path, destination: Path, manifest: dict, apply: bool) -> None:
    current_efi = destination / "EFI"
    fpt_backup = destination / "EFI-FPT-BACKUP"
    saved_test = destination / "EFI-OPENCORE-MADT-SAVED"
    if not fpt_backup.is_dir():
        raise FileNotFoundError(f"FPT EFI backup is missing: {fpt_backup}")
    if saved_test.exists():
        raise FileExistsError(f"Refusing to replace existing saved test tree: {saved_test}")
    expected_config = next(
        item["sha256"] for item in manifest["files"] if item["path"] == "EFI/OC/config.plist"
    )
    current_config = current_efi / "OC" / "config.plist"
    if not current_config.is_file() or sha256(current_config) != expected_config:
        raise ValueError("Current EFI is not the exact staged OpenCore test; refusing restore rename")

    print(f"PLAN: rename {current_efi} -> {saved_test}")
    print(f"PLAN: rename {fpt_backup} -> {current_efi}")
    if not apply:
        print("DRY-RUN: no files changed; add --apply to perform the reversible restore")
        return

    current_efi.rename(saved_test)
    try:
        fpt_backup.rename(current_efi)
    except Exception:
        saved_test.rename(current_efi)
        raise
    print("RESTORED: original FPT EFI is active; used OpenCore tree was preserved")


def select_mode(destination: Path, manifest: dict, enabled: bool, apply: bool) -> None:
    oc_dir = destination / "EFI" / "OC"
    active = oc_dir / "config.plist"
    selected_name = "config-patch-enabled.plist" if enabled else "config-control-disabled.plist"
    selected = oc_dir / selected_name
    hashes = {item["path"]: item["sha256"] for item in manifest["files"]}
    enabled_hash = hashes["EFI/OC/config-patch-enabled.plist"]
    control_hash = hashes["EFI/OC/config-control-disabled.plist"]
    selected_hash = enabled_hash if enabled else control_hash
    if not selected.is_file() or sha256(selected) != selected_hash:
        raise ValueError(f"USB mode file is missing or altered: {selected}")
    if not active.is_file() or sha256(active) not in {enabled_hash, control_hash}:
        raise ValueError("Active USB config.plist is not either validated test mode")

    label = "PATCH ENABLED" if enabled else "CONTROL DISABLED"
    print(f"PLAN: select {label}: copy {selected_name} -> config.plist")
    if not apply:
        print("DRY-RUN: no files changed; add --apply to select this mode")
        return
    shutil.copy2(selected, active)
    if sha256(active) != selected_hash:
        raise RuntimeError("Post-copy config verification failed")
    print(f"SELECTED: {label}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True, help="BIOS_BACKUP drive root, e.g. G:\\")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument(
        "--action",
        choices=("install", "restore", "enable-patch", "disable-patch"),
        default="install",
    )
    parser.add_argument("--apply", action="store_true", help="perform the printed operation")
    args = parser.parse_args()

    source = args.source.resolve()
    manifest = validate_staging(source)
    destination = validate_destination(args.destination)
    print(f"Validated OpenCore staging: {source}")
    print(f"Validated destination: {destination} ({EXPECTED_VOLUME_LABEL})")
    print("Validated all three original 16 MiB BIOS dumps by SHA-256")
    if args.action == "install":
        install(source, destination, args.apply)
    elif args.action == "restore":
        restore(source, destination, manifest, args.apply)
    else:
        select_mode(destination, manifest, args.action == "enable-patch", args.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
