#!/usr/bin/env python3
"""Compare executable UEFI leaf sections by module UI name.

UEFIExtract paths include numeric child indexes that move when NVRAM or another
file is inserted.  Comparing the full path therefore produces noisy false
differences.  This tool groups PE32/TE executable sections by the nearest FFS
module UI name and compares their hashes independent of the numeric index.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path


INDEXED_NAME = re.compile(r"^\d+\s+(.+)$")
IMAGE_SECTION = re.compile(r"^\d+\s+(PE32|TE) image section$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def module_name(image_parent: Path, root: Path) -> str:
    current = image_parent.parent
    while current != root and root in current.parents:
        match = INDEXED_NAME.match(current.name)
        if match:
            name = match.group(1)
            if not name.endswith("section") and name not in {
                "Volume image section",
                "Compressed section",
                "GUID defined section",
            }:
                return name
        current = current.parent
    return image_parent.parent.name


def executables(root: Path) -> dict[str, set[tuple[int, str]]]:
    result: defaultdict[str, set[tuple[int, str]]] = defaultdict(set)
    for body in root.rglob("body.bin"):
        match = IMAGE_SECTION.match(body.parent.name)
        if not match:
            continue
        module = module_name(body.parent, root)
        key = f"{module} [{match.group(1)}]"
        result[key].add((body.stat().st_size, sha256(body)))
    return dict(result)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    parser.add_argument(
        "--filter",
        default="",
        help="case-insensitive regex applied to the normalized module name",
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()
    wanted = re.compile(args.filter, re.IGNORECASE) if args.filter else None

    left = executables(args.left.resolve())
    right = executables(args.right.resolve())
    keys = sorted(left.keys() | right.keys())
    changed = []
    for key in keys:
        if left.get(key) != right.get(key):
            changed.append(key)

    if args.json:
        selected = [key for key in changed if not wanted or wanted.search(key)]
        print(
            json.dumps(
                {
                    "left": str(args.left.resolve()),
                    "right": str(args.right.resolve()),
                    "left_modules": len(left),
                    "right_modules": len(right),
                    "identical_modules": len(keys) - len(changed),
                    "changed_modules": len(changed),
                    "changed_shown": selected,
                    "details": {
                        key: {
                            "left": [list(item) for item in sorted(left.get(key, set()))],
                            "right": [list(item) for item in sorted(right.get(key, set()))],
                        }
                        for key in selected
                    },
                },
                indent=2,
            )
        )
        return 0

    print(f"Executable module keys: left={len(left)} right={len(right)} changed={len(changed)}")
    shown = 0
    for key in changed:
        if wanted and not wanted.search(key):
            continue
        shown += 1
        print(f"{key}")
        print(f"  left={sorted(left.get(key, set()))}")
        print(f"  right={sorted(right.get(key, set()))}")
    print(f"Changed modules shown={shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
