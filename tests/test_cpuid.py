import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("validator", ROOT / "tools" / "validate_platform.py")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def load(name):
    return json.loads((ROOT / "tests" / "fixtures" / name / "platform.json").read_text())


def test_affected_detects_orphan_vp2intersect():
    codes = {code for code, _ in validator.validate_cpuid(load("affected"))}
    assert "ORPHAN_AVX512_VP2INTERSECT" in codes
    assert "AVX512_XSTATE_UNAVAILABLE" in codes


def test_known_good_has_no_cpuid_issues():
    assert validator.validate_cpuid(load("known-good")) == []
