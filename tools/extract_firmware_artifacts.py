#!/usr/bin/env python3
"""Reproduce validated research artifacts from an authorized ERYING BIOS copy."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROVENANCE_PATH = ROOT / "firmware" / "manifests" / "artifact-provenance.json"
PROVENANCE = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
SOURCES = {model: PROVENANCE["sources"][model] for model in ("HM570111", "HM570307")}
TOOLS = PROVENANCE["tools"]
DERIVED = PROVENANCE["derived_from_HM570111"]
SETUP_GUID = DERIVED["setup_ffs_guid"]
PE32_SECTION_TYPE = DERIVED["section_type"]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"VALIDATION FAILED: {message}")


def identify_firmware(data: bytes) -> str:
    digest = sha256_bytes(data)
    for model, expected in SOURCES.items():
        if digest == expected["firmware_sha256"]:
            require(len(data) == expected["firmware_bytes"], f"{model} size mismatch")
            return model
    raise SystemExit(f"VALIDATION FAILED: unrecognized firmware SHA-256 {digest}")


def read_source(path: Path) -> tuple[str, bytes, dict]:
    require(path.is_file(), f"source not found: {path}")
    if path.suffix.lower() != ".zip":
        data = path.read_bytes()
        model = identify_firmware(data)
        return model, data, {"kind": "firmware", "sha256": sha256_bytes(data)}

    package_hash = sha256_file(path)
    models = [model for model, expected in SOURCES.items() if package_hash == expected["official_zip_sha256"]]
    require(len(models) == 1, f"unrecognized official ZIP SHA-256 {package_hash}")
    model = models[0]
    with zipfile.ZipFile(path) as package:
        matches = [name for name in package.namelist() if Path(name).name.upper() == f"{model}.BIN"]
        require(len(matches) == 1, f"expected exactly one {model}.bin in ZIP")
        data = package.read(matches[0])
    require(identify_firmware(data) == model, "ZIP contains an unexpected firmware image")
    return model, data, {"kind": "official_zip", "sha256": package_hash}


def validate_tool(path: Path, key: str) -> None:
    label = f"{TOOLS[key]['name']} {TOOLS[key]['version']}"
    require(path.is_file(), f"{label} not found: {path}")
    actual = sha256_file(path)
    require(actual == TOOLS[key]["executable_sha256"], f"{label} SHA-256 mismatch: {actual}")


def run_checked(command: list[str], label: str) -> None:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    require(result.returncode == 0, f"{label} failed\n{result.stdout}\n{result.stderr}")


def extract_setup(firmware: Path, output_dir: Path, uefi_extract: Path, ifr_extractor: Path) -> dict:
    validate_tool(uefi_extract, "uefi_extract")
    validate_tool(ifr_extractor, "ifr_extractor")
    setup_path = output_dir / "HM570111-Setup-PE32.bin"
    with tempfile.TemporaryDirectory(prefix="hm570111-setup-") as temp_name:
        extract_dir = Path(temp_name) / "setup"
        run_checked(
            [str(uefi_extract.resolve()), str(firmware.resolve()), SETUP_GUID,
             "-o", str(extract_dir), "-m", "body", "-t", PE32_SECTION_TYPE],
            "UEFIExtract",
        )
        body = extract_dir / "body.bin"
        require(body.is_file(), "UEFIExtract did not create body.bin")
        require(body.stat().st_size == DERIVED["setup_pe32_bytes"], "Setup PE32 size mismatch")
        require(sha256_file(body) == DERIVED["setup_pe32_sha256"], "Setup PE32 SHA-256 mismatch")
        shutil.copyfile(body, setup_path)

    run_checked([str(ifr_extractor.resolve()), str(setup_path.resolve())], "IFRExtractor-RS")
    ifr_path = Path(str(setup_path) + ".0.0.en-US.uefi.ifr.txt")
    require(ifr_path.is_file(), "IFRExtractor-RS did not create the expected en-US IFR")
    require(ifr_path.stat().st_size == DERIVED["ifr_bytes"], "IFR output size mismatch")
    require(sha256_file(ifr_path) == DERIVED["ifr_sha256"], "IFR output SHA-256 mismatch")
    return {
        "setup": {"path": str(setup_path), "bytes": setup_path.stat().st_size, "sha256": sha256_file(setup_path)},
        "ifr": {"path": str(ifr_path), "bytes": ifr_path.stat().st_size, "sha256": sha256_file(ifr_path)},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="official HM570111/HM570307 ZIP or extracted 16 MiB BIN")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "build" / "firmware")
    parser.add_argument("--uefi-extract", type=Path, default=ROOT / ".tools" / "uefiextract-a75" / "UEFIExtract.exe")
    parser.add_argument("--ifr-extractor", type=Path, default=ROOT / ".tools" / "ifrextractor-rs-1.6.1" / "ifrextractor.exe")
    parser.add_argument("--source-only", action="store_true", help="validate the package/image without deriving Setup/IFR")
    args = parser.parse_args()

    model, data, source_identity = read_source(args.source)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    firmware_path = args.output_dir / f"{model}.bin"
    firmware_path.write_bytes(data)
    report = {
        "schema_version": 1,
        "model": model,
        "source": source_identity,
        "firmware": {"path": str(firmware_path), "bytes": len(data), "sha256": sha256_bytes(data)},
        "derived": {},
    }
    if not args.source_only:
        require(model == "HM570111", "Setup/IFR reproduction is currently pinned only for HM570111; use --source-only")
        report["derived"] = extract_setup(firmware_path, args.output_dir, args.uefi_extract, args.ifr_extractor)
    report_path = args.output_dir / f"{model}-artifact-report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
