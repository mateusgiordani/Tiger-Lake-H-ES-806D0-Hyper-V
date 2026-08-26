import importlib.util
import copy
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


def test_report_decodes_cpuid_visible_in_the_captured_boot():
    values = validator.cpuid_values(load("affected"))
    assert values["xsave"] is True
    assert values["osxsave"] is True
    assert values["avx"] is True
    assert values["cpuid_1_0"]["ecx"] == "0x7FFAFBFF"


def test_known_good_has_no_cpuid_issues():
    assert validator.validate_cpuid(load("known-good")) == []


def test_diagnostic_bypass_is_not_false_clean():
    result = validator.build_report(load("diagnostic-bypass"))
    assert result["classification"] == "Diagnostic bypass active"
    assert result["platform_match"] is True
    assert result["overall_status"] == "ISSUES DETECTED"
    assert result["xsave_hyperv_signature"]["match"] is False
    assert result["xsave_hyperv_signature"]["windows_xsave_disabled_state"] is True
    assert result["xsave_hyperv_signature"]["bcd_xsavedisable_confirmed"] is True
    assert result["xsave_hyperv_signature"]["diagnostic_bypass_active"] is True
    assert result["recommendation"] is None
    assert result["diagnostic_mitigation"]["active"] is True
    assert result["checks"][0]["values"]["xsave"] is False
    assert result["checks"][0]["values"]["avx"] is False
    assert any(issue["code"] == "WINDOWS_XSAVE_AVX_UNAVAILABLE" for issue in result["issues"])
    assert validator.report_exit_code(result) == 1


def test_xsave_unavailable_without_bcd_is_not_claimed_as_active_bypass():
    data = copy.deepcopy(load("diagnostic-bypass"))
    data["collection"]["windows_bcd"] = {
        "available": False,
        "error": "access denied",
    }
    result = validator.build_report(data)
    assert result["classification"] == "Windows XSAVE/AVX unavailable"
    assert result["platform_match"] is True
    assert result["xsave_hyperv_signature"]["windows_xsave_disabled_state"] is True
    assert result["xsave_hyperv_signature"]["bcd_xsavedisable_confirmed"] is False
    assert result["xsave_hyperv_signature"]["diagnostic_bypass_active"] is False
    assert result["diagnostic_mitigation"] is None
    assert "cause is not confirmed" in result["issues"][0]["message"]


def test_known_good_does_not_match_affected_signature():
    result = validator.build_report(load("known-good"))
    assert result["known_signature_match"] is False
    assert result["platform_match"] is False
    assert result["recommendation"] is None
    assert result["diagnostic_mitigation"] is None


def test_affected_report_exposes_only_degraded_diagnostic_mitigation():
    result = validator.build_report(load("affected"))
    assert result["known_signature_match"] is True
    assert result["platform_match"] is True
    assert result["xsave_hyperv_signature"]["match"] is True
    assert result["classification"] == "Affected"
    assert result["validator_version"] == "0.5.0"
    assert result["recommendation"] is None
    mitigation = result["diagnostic_mitigation"]
    assert "xsavedisable" in mitigation["command"]
    assert mitigation["suitable_for_daily_use"] is False
    assert mitigation["known_impact"] == [
        "AVX unavailable",
        "AVX2 unavailable",
        "AVX-512 unavailable",
    ]
    assert "exact trigger" in mitigation["causal_limit"]


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
    assert result["diagnostic_mitigation"] is None


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
    assert validator.report_exit_code(result) == 1


def test_incomplete_cpuid_exit_code_is_two():
    data = {
        "cpu": {"signature": "000806D0"},
        "cpuid": {},
    }
    result = validator.build_report(data)
    assert validator.report_exit_code(result) == 2


def test_known_good_exit_code_is_zero():
    result = validator.build_report(load("known-good"))
    assert validator.report_exit_code(result) == 0
