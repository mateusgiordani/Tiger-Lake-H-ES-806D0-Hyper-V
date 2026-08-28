# Runtime SPI manifest — AVX-512 enabled

Captured on 2026-08-27. Full images live under repository-local
`private/runtime-2026-08-27-avx512/` and are excluded by `.gitignore`.

| Private file | Bytes | SHA-256 | Role |
|---|---:|---|---|
| `polestar_full_with_avx512_1.bin` | 16,777,216 | `1115251F5F9A28DB65ABA69F5393280372AF2F4015F5C363C028703EC4AE33C6` | canonical read 1 |
| `polestar_full_with_avx512_2.bin` | 16,777,216 | `1115251F5F9A28DB65ABA69F5393280372AF2F4015F5C363C028703EC4AE33C6` | canonical read 2 |
| `polestar_full_with_avx512_3.bin` | 16,777,216 | `9E68D4C652A07339108D890817E724805F6F5CA886EEE8E40E6599FC18B7EA3E` | CSME-mutated read |

Reads 1 and 2 are byte-identical. Read 3 differs from them by 271 bytes only
inside `0x1FA000–0x278307`, the persistent CSME window. All three have identical
Flash Descriptor, BIOS NVRAM and executable BIOS bytes.

## Baseline comparison

Baseline 2026-08-24 SHA-256:
`68E9A8113DDDA6E192AA72417E69BD83A3E37DC10D4F1421F0D3B282E49231BD`.

| Region | Old SHA-256 | AVX-512 SHA-256 | Changed bytes |
|---|---|---|---:|
| Descriptor `0x000000–0x000FFF` | `92E4E39242D6B0410692B833513067AEEF21218215B3D539DF2BB45A0DC6685D` | same | 0 |
| CSME `0x001000–0x4FFFFF` | `BAC4CA22BB9F572668C92C49DC63B9340C3024680AE67603A41301AF134F6623` | `0D0EF1E4DB377BE0158238E89B3BE018F6C52308426AE9937B868B8A00247AD3` | 224,768 |
| BIOS NVRAM `0x500000–0x55FFFF` | `CB657F80FEDC377CE8DB5FB656C5E9EA3F63297D1183B0ADE29CCE5AADC26D33` | `44AB1D99FEB004E02D8F105BCBCC7D96564D2AF373C383FDDFB0D4BFD3E99542` | 223,051 |
| BIOS executable `0x560000–0xFFFFFF` | `1BE2BD258E0DCC62BB0FC27C434B39753F7F2CCA0AD3C23D1041EDA10990C607` | same | 0 |

Only persistent CSME data and BIOS NVRAM changed. UEFI executable module
comparison: 309 keys on each side, 0 changed.

See [`docs/avx512-runtime-firmware-diff.md`](../../../docs/avx512-runtime-firmware-diff.md)
for NVAR interpretation and project impact.
