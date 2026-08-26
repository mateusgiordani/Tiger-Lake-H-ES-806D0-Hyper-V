import importlib.util
import sys
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
