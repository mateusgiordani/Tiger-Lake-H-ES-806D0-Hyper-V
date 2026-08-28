# Runtime firmware comparison after enabling AVX-512

## Result

The 27 August 2026 runtime capture confirms that AVX-512 became available
through firmware configuration state, not through replacement of executable
firmware code.

The stable AVX-512 snapshot consists of two byte-identical 16 MiB FPT reads:

- `polestar_full_with_avx512_1.bin` — SHA-256
  `1115251F5F9A28DB65ABA69F5393280372AF2F4015F5C363C028703EC4AE33C6`;
- `polestar_full_with_avx512_2.bin` — the same SHA-256.

The third read has SHA-256
`9E68D4C652A07339108D890817E724805F6F5CA886EEE8E40E6599FC18B7EA3E`.
It differs from the first two by 271 bytes, all inside the persistent CSME
window. Its Descriptor and complete BIOS region are identical to reads 1 and 2.
Reads 1 and 2 are therefore the canonical stable snapshot; read 3 is retained
privately as evidence of normal mutable CSME state.

The private binary images are not distributed by this repository. Local copies
are kept under `private/runtime-2026-08-27-avx512/`. Their public hash and
region manifest is in
[`firmware/manifests/runtime-2026-08-27-avx512/`](../firmware/manifests/runtime-2026-08-27-avx512/).

## Comparison with the 24 August baseline

Baseline runtime dump SHA-256:
`68E9A8113DDDA6E192AA72417E69BD83A3E37DC10D4F1421F0D3B282E49231BD`.

| Region | Range | Result |
|---|---:|---|
| Flash Descriptor | `0x000000–0x000FFF` | identical |
| static CSME prefix | `0x001000–0x1F9FFF` | identical |
| persistent CSME window | `0x1FA000–0x278307` | 224,768 changed bytes |
| static CSME suffix | `0x278308–0x4FFFFF` | identical |
| BIOS NVRAM window | `0x500000–0x55FFFF` | 223,051 changed bytes |
| executable BIOS area | `0x560000–0xFFFFFF` | identical |

UEFIExtract A75 found 309 normalized executable module keys in each image.
Every executable module was identical. No changed PE32/TE firmware module is
needed to explain the new AVX-512 state.

## Configuration differences

AMI NVAR is append-only and uses linked data records. The new image contains
records from more than one update generation, and the two redundant stores are
not represented at the same generation by a naive directory-order reader.
Following the linked records exposes these changes relative to the old active
values:

| Variable | Offset | Old | New record | IFR meaning |
|---|---:|---:|---:|---|
| `CpuSetup` | `0x007` | `0` | `1` | BIST on reset |
| `CpuSetup` | `0x22A` | `1` | `0` | AVX3 disable flag; `0` means enabled |
| `Setup` | `0x799` | `0` | `1` | CrashLog On All Reset |
| `Setup` | `0x90D` | `0` | `1` | CrashLog Clear Enable |
| `Setup` | `0xA1F` | `1` | `0` | password protection of runtime variables |
| `PchSetup` | `0x687` | `0` | `1` | PMC Debug Message Enable |

The decisive AVX-512-related change is `CpuSetup+0x22A: 1 → 0`. This matches
the runtime evidence: Hyper-V's root partition now exposes AVX512F, AVX512VL,
VP2INTERSECT and XSTATE components 5–7 coherently on all 16 logical processors,
and an AVX-512F instruction executes successfully.

The other changed options must remain documented as confounders. They do not
directly explain AVX-512 enumeration, but this was not a single-variable
firmware A/B experiment.

## What this means for the project

This result resolves one previously open defect more narrowly:

- the orphan `AVX512_VP2INTERSECT` state was caused by the firmware's AVX3
  configuration path masking AVX512F/VL and XSTATE 5–7 incompletely;
- enabling AVX3 restores a coherent AVX-512 contract and makes AVX-512F usable;
- no firmware-code patch is required for that correction.

It does **not** close the Hyper-V boot investigation:

- the successful Windows capture still uses
  `hypervisorloadoptions DISABLEHARDWAREMBEC`;
- it proves `Hyper-V + XSAVE + AVX/AVX2 + AVX-512` can coexist when the hardware
  MBEC path is disabled;
- it does not prove that enabling AVX3 alone permits boot with hardware MBEC
  enabled.

The current model is therefore two independent controls that both matter:

1. BIOS AVX3 enabled fixes CPUID/XSTATE coherence and exposes usable AVX-512.
2. The BCD MBEC fallback remains required by the only successful Hyper-V boots
   collected so far.

A future causal test of `AVX3 enabled + hardware MBEC enabled` must preserve all
other BIOS variables and use a deliberate failure-safe boot entry. It is not
authorized or performed by this comparison.

## Safety and interpretation limits

- No firmware was written during this analysis.
- Full SPI dumps remain private because they contain machine-specific NVRAM and
  persistent CSME data.
- The third read's CSME drift must not be mistaken for a firmware-code change.
- A parser that reports only the first `CpuSetup` body can miss linked NVAR data
  and incorrectly report AVX3 as still disabled.
