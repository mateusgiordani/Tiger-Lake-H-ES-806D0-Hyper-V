import importlib.util
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
