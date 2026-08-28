# Small-model handoff: AVX-512 evidence hygiene

## Objective

Finish low-risk repository hygiene for the 2026-08-27 AVX-512 firmware capture.
Do not reinterpret the binary investigation, modify BCD, flash firmware, or
publish full SPI images.

The technical source of truth is
[`avx512-runtime-firmware-diff.md`](avx512-runtime-firmware-diff.md). Preserve
its distinction between the AVX3 fix and the still-required MBEC fallback.

## Verified private inputs

Current private files are under repository-local
`private/runtime-2026-08-27-avx512/` and are ignored:

- `polestar_full_with_avx512_1.bin`, 16,777,216 bytes,
  SHA-256 `1115251F5F9A28DB65ABA69F5393280372AF2F4015F5C363C028703EC4AE33C6`;
- `polestar_full_with_avx512_2.bin`, same size and hash;
- `polestar_full_with_avx512_3.bin`, 16,777,216 bytes,
  SHA-256 `9E68D4C652A07339108D890817E724805F6F5CA886EEE8E40E6599FC18B7EA3E`.

The third read differs only by 271 bytes of mutable CSME state. Never replace
or rename it as though it were corrupt.

## Allowed tasks

1. Optionally organize the three ignored binaries under
   `private/runtime-2026-08-27-avx512/`, but only after hashing source and
   destination and proving byte identity. Do not delete the source until the
   destination is verified.
2. Update navigation links in README or documentation indexes to include:
   - `docs/avx512-runtime-firmware-diff.md`;
   - `firmware/manifests/runtime-2026-08-27-avx512/MANIFEST.md`.
3. Check terminology across current docs:
   - AVX3 enabled repairs AVX-512 CPUID/XSTATE coherence;
   - current successful Hyper-V boot still disables hardware MBEC;
   - AVX3 alone has not been tested as the Hyper-V boot fix.
4. Verify all public hashes against the ignored private files.
5. Ensure no `.bin`, absolute user path, hostname or private identifier is
   staged.
6. Run `python -m pytest` and `git diff --check`.
7. Report the exact staged file list before committing. Commit or push only if
   the user explicitly requests it.

## Do not do

- Do not run FPT write commands or any firmware flashing tool.
- Do not rewrite Git history.
- Do not normalize away the read-3 CSME difference.
- Do not claim all NVAR mirrors agree: linked append-only records are at
  different generations.
- Do not run a hardware-MBEC boot experiment without a separate explicit user
  request and a recovery-safe BCD plan.
