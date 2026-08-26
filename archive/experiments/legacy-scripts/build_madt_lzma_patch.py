#!/usr/bin/env python3
"""Build a layout-preserving Polestar HM570 MADT patch candidate.

Only the payload of the existing LZMA GUID-defined section is replaced.  The
outer FFS file, section headers, firmware volumes, Descriptor, CSME, NVRAM and
all uncompressed offsets remain unchanged.  Extensive identity checks make the
script refuse any input other than the validated runtime dump.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import lzma
import subprocess
import struct
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PROVENANCE_PATH = ROOT / "firmware" / "manifests" / "artifact-provenance.json"
PROVENANCE = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
PRIVATE_SOURCE = PROVENANCE["sources"]["runtime_private"]
LZMA_TOOL = PROVENANCE["tools"]["lzma_compress"]
PRIVATE_DERIVED = PROVENANCE["derived_from_private_runtime"]

EXPECTED_FIRMWARE_SIZE = PRIVATE_SOURCE["firmware_bytes"]
EXPECTED_FIRMWARE_SHA256 = PRIVATE_SOURCE["firmware_sha256"]
PAYLOAD_OFFSET = 0x5710A8
PAYLOAD_LENGTH = 0x2E49E8
EXPECTED_PAYLOAD_SHA256 = "2A16026C955EC62DC01CF4F082D6E92065B9B463DFDBF1E82AB0B3BCBCFB9DF3"
EXPECTED_UNCOMPRESSED_SIZE = 0xBC0010
EXPECTED_UNCOMPRESSED_SHA256 = "47CFEEBE52060A76DE7A7F140039CA35A06D20BBB3D73BCA5021A294A5F6961B"
EXPECTED_PATTERN_OFFSET = 0xA571B4
EXPECTED_LZMA_TOOL_SHA256 = LZMA_TOOL["executable_sha256"]
EXPECTED_OUTPUT_SHA256 = PRIVATE_DERIVED["madt_candidate_sha256"]

FIND = bytes.fromhex(
    "040601050001040602050001040603050001040604050001"
    "040605050001040606050001040607050001040608050001"
    "04060905000104060A05000104060B05000104060C050001"
    "04060D05000104060E05000104060F050001040610050001"
)
REPLACE = bytes.fromhex(
    "040600050001040601050001040602050001040603050001"
    "040604050001040605050001040606050001040607050001"
    "04060805000104060905000104060A05000104060B050001"
    "04060C05000104060D05000104060E05000104060F050001"
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"SAFETY CHECK FAILED: {message}")


def validate_candidate_hash(candidate: bytes | bytearray) -> str:
    candidate_hash = sha256(candidate)
    require(candidate_hash == EXPECTED_OUTPUT_SHA256, "candidate SHA-256 mismatch")
    return candidate_hash


def compress_lzma_alone(data: bytes, tool: Path) -> bytes:
    require(tool.is_file(), f"LzmaCompress tool not found: {tool}")
    require(sha256(tool.read_bytes()) == EXPECTED_LZMA_TOOL_SHA256, "LzmaCompress tool SHA-256 mismatch")
    with tempfile.TemporaryDirectory(prefix="polestar-lzma-") as temp_name:
        temp = Path(temp_name)
        source = temp / "source.bin"
        encoded_path = temp / "encoded.lzma"
        source.write_bytes(data)
        result = subprocess.run(
            [str(tool.resolve()), "-e", "-o", str(encoded_path), str(source)],
            check=False,
            capture_output=True,
            text=True,
        )
        require(result.returncode == 0, f"LzmaCompress failed: {result.stdout} {result.stderr}")
        require(encoded_path.is_file(), "LzmaCompress did not produce output")
        encoded = encoded_path.read_bytes()
    require(encoded[0] == 0x5D, f"unexpected LZMA property byte 0x{encoded[0]:02X}")
    require(encoded[1:5] == struct.pack("<I", 0x1000000), "LZMA dictionary changed")
    require(encoded[5:13] == struct.pack("<Q", len(data)), "LZMA declared size changed")
    return encoded


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("firmware", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--lzma-tool", type=Path, required=True)
    args = parser.parse_args()

    firmware = args.firmware.read_bytes()
    require(len(firmware) == EXPECTED_FIRMWARE_SIZE, "firmware size is not 16 MiB")
    require(sha256(firmware) == EXPECTED_FIRMWARE_SHA256, "input firmware SHA-256 is not the validated dump")

    payload = firmware[PAYLOAD_OFFSET : PAYLOAD_OFFSET + PAYLOAD_LENGTH]
    require(len(payload) == PAYLOAD_LENGTH, "truncated LZMA payload")
    require(sha256(payload) == EXPECTED_PAYLOAD_SHA256, "LZMA payload SHA-256 mismatch")
    require(payload[0] == 0x5D, "unexpected LZMA property byte")
    require(struct.unpack_from("<I", payload, 1)[0] == 0x1000000, "unexpected LZMA dictionary")
    require(struct.unpack_from("<Q", payload, 5)[0] == EXPECTED_UNCOMPRESSED_SIZE, "unexpected declared size")

    uncompressed = lzma.decompress(payload, format=lzma.FORMAT_ALONE)
    require(len(uncompressed) == EXPECTED_UNCOMPRESSED_SIZE, "unexpected decompressed size")
    require(sha256(uncompressed) == EXPECTED_UNCOMPRESSED_SHA256, "unexpected decompressed SHA-256")
    require(uncompressed.count(FIND) == 1, "MADT NMI pattern is not unique")
    require(uncompressed.find(FIND) == EXPECTED_PATTERN_OFFSET, "MADT NMI pattern offset changed")

    patched_uncompressed = uncompressed.replace(FIND, REPLACE, 1)
    changed = [index for index, pair in enumerate(zip(uncompressed, patched_uncompressed)) if pair[0] != pair[1]]
    expected_changed = [EXPECTED_PATTERN_OFFSET + 2 + 6 * index for index in range(16)]
    require(changed == expected_changed, "patch changed bytes outside the 16 NMI UID fields")

    encoded = compress_lzma_alone(patched_uncompressed, args.lzma_tool)
    require(len(encoded) <= PAYLOAD_LENGTH, f"new LZMA stream is too large ({len(encoded)} > {PAYLOAD_LENGTH})")
    require(lzma.decompress(encoded, format=lzma.FORMAT_ALONE) == patched_uncompressed, "new stream verification failed")

    padded_payload = encoded + b"\xFF" * (PAYLOAD_LENGTH - len(encoded))
    candidate = bytearray(firmware)
    candidate[PAYLOAD_OFFSET : PAYLOAD_OFFSET + PAYLOAD_LENGTH] = padded_payload
    require(len(candidate) == EXPECTED_FIRMWARE_SIZE, "candidate size changed")
    require(candidate[:0x500000] == firmware[:0x500000], "Descriptor or CSME changed")
    require(candidate[0x500000:PAYLOAD_OFFSET] == firmware[0x500000:PAYLOAD_OFFSET], "BIOS prefix changed")
    require(candidate[PAYLOAD_OFFSET + PAYLOAD_LENGTH :] == firmware[PAYLOAD_OFFSET + PAYLOAD_LENGTH :], "BIOS suffix changed")
    candidate_hash = validate_candidate_hash(candidate)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(candidate)
    print(f"Input SHA256:       {sha256(firmware)}")
    print(f"Patched data SHA256:{sha256(patched_uncompressed)}")
    print(f"LZMA bytes:         {len(encoded)} / {PAYLOAD_LENGTH} (padding {PAYLOAD_LENGTH - len(encoded)})")
    print(f"Output SHA256:      {candidate_hash}")
    print(f"Output:             {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
