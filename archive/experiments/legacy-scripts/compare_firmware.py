#!/usr/bin/env python3
"""Report byte and block differences between equal-sized firmware images."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


REGIONS = (
    ("Descriptor", 0x000000, 0x001000),
    ("CSME", 0x001000, 0x500000),
    ("BIOS", 0x500000, 0x1000000),
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    parser.add_argument("--block-size", type=lambda value: int(value, 0), default=0x1000)
    args = parser.parse_args()

    left = args.left.read_bytes()
    right = args.right.read_bytes()
    if len(left) != len(right):
        raise SystemExit(f"length mismatch: {len(left)} vs {len(right)}")

    print(f"LEFT  {args.left}: {len(left)} bytes SHA256={sha(left)}")
    print(f"RIGHT {args.right}: {len(right)} bytes SHA256={sha(right)}")
    for name, start, end in REGIONS:
        a, b = left[start:end], right[start:end]
        changed = sum(x != y for x, y in zip(a, b))
        print(
            f"{name}: changed_bytes={changed} "
            f"left={sha(a)} right={sha(b)} equal={a == b}"
        )

    differing_offsets = [index for index, pair in enumerate(zip(left, right)) if pair[0] != pair[1]]
    if not differing_offsets:
        print("Images are identical")
        return 0

    block_size = args.block_size
    blocks = sorted({offset // block_size for offset in differing_offsets})
    print(
        f"Total changed bytes={len(differing_offsets)}, first=0x{differing_offsets[0]:X}, "
        f"last=0x{differing_offsets[-1]:X}, changed_{block_size:X}_blocks={len(blocks)}"
    )

    ranges = []
    start = previous = blocks[0]
    for block in blocks[1:]:
        if block != previous + 1:
            ranges.append((start, previous))
            start = block
        previous = block
    ranges.append((start, previous))
    print("Changed block ranges:")
    for first, last in ranges:
        print(f"  0x{first * block_size:X}-0x{min(len(left), (last + 1) * block_size) - 1:X}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
