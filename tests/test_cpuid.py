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


def test_known_good_does_not_match_affected_signature():
    result = validator.build_report(load("known-good"))
    assert result["known_signature_match"] is False
    assert result["platform_match"] is False
    assert result["recommendation"] is None


def test_affected_report_recommends_only_known_workaround():
    result = validator.build_report(load("affected"))
    assert result["known_signature_match"] is True
    assert result["platform_match"] is True
    assert result["xsave_hyperv_signature"]["match"] is True
    assert result["classification"] == "Affected"
    assert "xsavedisable" in result["recommendation"]


def test_incomplete_cpuid_is_unknown_not_not_affected():
    data = {
        "cpu": {"signature": "000806D0"},
        "cpuid": {},
    }
    result = validator.build_report(data)
    assert result["cpuid_complete"] is False
    assert result["classification"] == "Unknown"
    assert result["overall_status"] == "INCOMPLETE"
    assert any(issue["code"] == "INCOMPLETE_CPUID" for issue in result["issues"])
    assert result["recommendation"] is None


def test_clean_cpuid_with_madt_anomaly_is_not_xsave_affected():
    data = load("affected")
    # CPUID limpo: sem VP2INTERSECT órfão nem XSTATE ausente.
    data["cpuid"]["0x00000007"]["0"]["edx"] = "0x00000000"
    result = validator.build_report(
        data,
        ROOT / "tests" / "fixtures" / "affected" / "madt-original.dat",
    )
    assert result["classification"] == "Not affected"
    assert result["xsave_hyperv_signature"]["match"] is False
    assert result["madt_firmware_anomaly"]["detected"] is True
    assert result["overall_status"] == "ISSUES DETECTED"
