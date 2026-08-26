import importlib.util
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows API collector")
def test_windows_processor_feature_ids_and_shape():
    script = ROOT / "tools" / "collect" / "windows" / "dump_cpuid_windows.py"
    spec = importlib.util.spec_from_file_location("dump_cpuid_windows", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    features = module.windows_processor_features()["features"]
    assert features["sse"]["id"] == 6
    assert features["sse2"]["id"] == 10
    assert features["xsave_enabled"]["id"] == 17
    assert features["avx"]["id"] == 39
    assert features["avx2"]["id"] == 40
    assert features["avx512f"]["id"] == 41
    assert all(isinstance(feature["available"], bool) for feature in features.values())


@pytest.mark.skipif(sys.platform != "win32", reason="Windows API collector")
def test_windows_bcd_collection_is_read_only_and_selective(monkeypatch):
    script = ROOT / "tools" / "collect" / "windows" / "dump_cpuid_windows.py"
    spec = importlib.util.spec_from_file_location("dump_cpuid_windows_bcd", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    def fake_run(command, **kwargs):
        assert command[-3:] == ["/enum", "{current}", "/v"]
        assert kwargs["check"] is False
        return SimpleNamespace(
            returncode=0,
            stdout=(
                "identifier {11111111-1111-1111-1111-111111111111}\n"
                "description Private machine name\n"
                "hypervisorloadoptions DISABLEHARDWAREMBEC\n"
                "hypervisorlaunchtype Auto\n"
                "xsavedisable 1\n"
            ),
            stderr="",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    result = module.windows_bcd_current_entry()
    assert result == {
        "available": True,
        "command": "bcdedit /enum {current} /v",
        "exit_code": 0,
        "current_entry": {
            "elements": {
                "hypervisorloadoptions": "DISABLEHARDWAREMBEC",
                "hypervisorlaunchtype": "Auto",
                "xsavedisable": "1",
            }
        },
    }


@pytest.mark.skipif(sys.platform != "win32", reason="Windows API collector")
def test_windows_bcd_permission_failure_is_explicit(monkeypatch):
    script = ROOT / "tools" / "collect" / "windows" / "dump_cpuid_windows.py"
    spec = importlib.util.spec_from_file_location("dump_cpuid_windows_denied", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="The boot configuration data store could not be opened. Access is denied.",
        ),
    )

    result = module.windows_bcd_current_entry()
    assert result["available"] is False
    assert result["exit_code"] == 1
    assert result["failure_kind"] == "permission_denied"
    assert "Access is denied" in result["stderr"]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows API collector")
def test_normalized_cpuid_is_labeled_as_root_partition_visible():
    script = ROOT / "tools" / "collect" / "windows" / "dump_cpuid_windows.py"
    spec = importlib.util.spec_from_file_location("dump_cpuid_windows_visibility", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    report = {
        "vendor": "GenuineIntel",
        "brand": "Test CPU",
        "leaves": {
            "0x00000001": {
                "0x0": {
                    "eax": "0x000806D0",
                    "ebx": "0x00000000",
                    "ecx": "0x80000000",
                    "edx": "0x00000000",
                }
            }
        },
        "per_cpu_comparison": {"logical_processors_checked": 1},
        "hyperv_relevant_consistency": {},
        "timekeeping_consistency": {},
        "windows_processor_features": {},
        "windows_bcd": {"available": False, "error": "access denied"},
    }
    normalized = module.normalized_platform(report)
    visibility = normalized["collection"]["cpuid_visibility"]
    assert visibility["scope"] == "windows_root_partition"
    assert visibility["hypervisor_present"] is True
    assert visibility["bare_metal_cpuid_claimed"] is False
