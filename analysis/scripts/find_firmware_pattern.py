#!/usr/bin/env python3
"""Locate a binary slice in firmware images or extracted UEFI module trees."""

from __future__ import annotations

import argparse
from pathlib import Path


def all_offsets(haystack: bytes, needle: bytes):
    start = 0
    while True:
        offset = haystack.find(needle, start)
        if offset < 0:
            return
        yield offset
        start = offset + 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("needle_file", type=Path)
    parser.add_argument("targets", type=Path, nargs="+")
    parser.add_argument("--offset", type=lambda value: int(value, 0), default=0)
    parser.add_argument("--length", type=lambda value: int(value, 0))
    parser.add_argument("--glob", default="body.bin")
    args = parser.parse_args()

    source = args.needle_file.read_bytes()
    end = None if args.length is None else args.offset + args.length
    needle = source[args.offset:end]
    if not needle:
        raise SystemExit("Needle is empty")

    print(
        f"Needle: {args.needle_file} offset=0x{args.offset:X} "
        f"length=0x{len(needle):X} ({len(needle)} bytes)"
    )
    matches = 0
    for target in args.targets:
        candidates = [target] if target.is_file() else target.rglob(args.glob)
        for candidate in candidates:
            try:
                data = candidate.read_bytes()
            except OSError:
                continue
            for offset in all_offsets(data, needle):
                matches += 1
                print(f"MATCH {candidate} @ 0x{offset:X}")
    print(f"Total matches: {matches}")
    return 0 if matches else 1


if __name__ == "__main__":
    raise SystemExit(main())
