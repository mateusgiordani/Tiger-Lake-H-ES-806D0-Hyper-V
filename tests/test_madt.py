import importlib.util
import struct
from pathlib import Path


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("validator", ROOT / "tools" / "validate_platform.py")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def test_original_detects_uid_offset():
    path = ROOT / "tests" / "fixtures" / "affected" / "madt-original.dat"
    codes = {code for code, _ in validator.validate_madt(path)}
    assert {"MADT_NMI_UID_MISMATCH", "NMI_UID_OFFSET_PLUS_ONE"} <= codes


def test_fixed_is_consistent():
    path = ROOT / "tests" / "fixtures" / "affected" / "madt-fixed.dat"
    assert validator.validate_madt(path) == []


def test_x2apic_nmi_wildcard_is_supported(tmp_path):
    records = [
        struct.pack("<BBHIII", 9, 16, 0, 0, 1, 42),
        struct.pack("<BBHIB3x", 10, 12, 0, 0xFFFFFFFF, 1),
    ]
    table = bytearray(44 + sum(map(len, records)))
    table[:4] = b"APIC"
    struct.pack_into("<I", table, 4, len(table))
    table[8] = 6
    offset = 44
    for record in records:
        table[offset : offset + len(record)] = record
        offset += len(record)
    table[9] = (-sum(table)) & 0xFF
    path = tmp_path / "x2apic.dat"
    path.write_bytes(table)
    assert validator.parse_madt(path)[:2] == ({42}, {0xFFFFFFFF})
    assert validator.validate_madt(path) == []


def test_invalid_checksum_is_rejected(tmp_path):
    path = tmp_path / "bad.dat"
    data = bytearray((ROOT / "tests" / "fixtures" / "affected" / "madt-fixed.dat").read_bytes())
    data[9] ^= 1
    path.write_bytes(data)
    try:
        validator.parse_madt(path)
    except ValueError as error:
        assert "checksum" in str(error)
    else:
        raise AssertionError("invalid checksum was accepted")
