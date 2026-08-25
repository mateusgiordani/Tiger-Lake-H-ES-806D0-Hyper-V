#!/usr/bin/env python3
"""Compare leaf bodies from two UEFIExtract ``all`` output trees."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def leaf_bodies(root: Path) -> dict[str, tuple[int, str]]:
    result = {}
    for body in root.rglob("body.bin"):
        parent = body.parent
        if any(item.is_dir() for item in parent.iterdir()):
            continue
        data = body.read_bytes()
        key = parent.relative_to(root).as_posix()
        result[key] = (len(data), hashlib.sha256(data).hexdigest().upper())
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    args = parser.parse_args()

    left = leaf_bodies(args.left)
    right = leaf_bodies(args.right)
    print(f"Leaf bodies: left={len(left)} right={len(right)}")
    changed = 0
    for key in sorted(left.keys() | right.keys()):
        a, b = left.get(key), right.get(key)
        if a == b:
            continue
        changed += 1
        if a is None:
            print(f"ONLY RIGHT: {key} {b}")
        elif b is None:
            print(f"ONLY LEFT:  {key} {a}")
        else:
            print(f"DIFFERENT:  {key}")
            print(f"  left={a}")
            print(f"  right={b}")
    print(f"Changed/missing leaf bodies: {changed}")
    return 0 if changed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
