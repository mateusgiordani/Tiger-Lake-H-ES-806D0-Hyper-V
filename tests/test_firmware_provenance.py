import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROVENANCE_PATH = ROOT / "firmware" / "manifests" / "artifact-provenance.json"


def load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_extractor_uses_provenance_manifest():
    provenance = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
    extractor = load_script("extract_firmware_artifacts", ROOT / "tools" / "extract_firmware_artifacts.py")

    assert extractor.PROVENANCE_PATH == PROVENANCE_PATH
    assert extractor.SOURCES["HM570111"] is extractor.PROVENANCE["sources"]["HM570111"]
    assert extractor.TOOLS is extractor.PROVENANCE["tools"]
    assert extractor.DERIVED is extractor.PROVENANCE["derived_from_HM570111"]
    assert extractor.PROVENANCE == provenance


def test_madt_builder_pins_manifest_output_hash():
    provenance = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
    builder = load_script(
        "build_madt_lzma_patch",
        ROOT / "archive" / "experiments" / "legacy-scripts" / "build_madt_lzma_patch.py",
    )

    assert builder.PROVENANCE_PATH == PROVENANCE_PATH
    assert builder.EXPECTED_OUTPUT_SHA256 == provenance["derived_from_private_runtime"]["madt_candidate_sha256"]
    assert builder.EXPECTED_FIRMWARE_SHA256 == provenance["sources"]["runtime_private"]["firmware_sha256"]
    assert builder.EXPECTED_LZMA_TOOL_SHA256 == provenance["tools"]["lzma_compress"]["executable_sha256"]
    with pytest.raises(SystemExit, match="candidate SHA-256 mismatch"):
        builder.validate_candidate_hash(b"not the pinned candidate")


def test_lzma_binary_origin_is_fully_pinned():
    provenance = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
    tool = provenance["tools"]["lzma_compress"]

    assert tool["version"] == "0.2 Build 28123"
    assert len(tool["binary_revision"]) == 40
    assert tool["archive_filename"].endswith(f"{tool['binary_revision']}.zip")
    assert len(tool["archive_sha256"]) == 64
    assert len(tool["executable_sha256"]) == 64
