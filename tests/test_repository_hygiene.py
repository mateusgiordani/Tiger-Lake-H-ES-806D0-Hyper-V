import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_FIRMWARE_SUFFIXES = {".bin", ".rom", ".fd", ".cap"}
FORBIDDEN_DERIVED_SUFFIXES = (".uefi.ifr.txt",)


def tracked_paths() -> list[str]:
    if shutil.which("git") is None or not (ROOT / ".git").exists():
        pytest.skip("repository hygiene check requires a Git checkout")
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    return [path.decode("utf-8") for path in result.stdout.split(b"\0") if path]


def test_repository_does_not_distribute_firmware_images_or_complete_ifr():
    forbidden = []
    for path_text in tracked_paths():
        normalized = path_text.lower()
        if Path(normalized).suffix in FORBIDDEN_FIRMWARE_SUFFIXES:
            forbidden.append(path_text)
        elif normalized.endswith(FORBIDDEN_DERIVED_SUFFIXES):
            forbidden.append(path_text)

    assert not forbidden, "forbidden firmware artifacts are tracked:\n" + "\n".join(forbidden)
