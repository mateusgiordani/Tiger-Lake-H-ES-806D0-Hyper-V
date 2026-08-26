# Firmware sources and reproducibility

This repository does not require a redistributed ERYING firmware image to
reproduce the extracted Setup/IFR evidence. Obtain the firmware from the
manufacturer, verify it, and derive artifacts locally into the ignored
`build/firmware/` directory.

## Official ERYING packages

Manufacturer page:
<https://www.erying.cc/sys-pd/14.html>

The page distinguishes two incompatible board revisions. Use HM570111 only
when the BIOS identifies the board as HM5701xx, and HM570307 only for HM5703xx.

| Package | Official ZIP SHA-256 | Contained image | Image SHA-256 |
|---|---|---|---|
| Polestar M-ATX G613 HM570111 | `8561544D6094FD03C44EAD25520D4638F3B0EF5234881811F41E4E1048BF05FB` | `HM570111.bin` (16 MiB) | `16529D3B622D150CB2E2EEDA95347C68A878532D39B8B3D9C1F4084A4CFFCCBE` |
| Polestar M-ATX G613 HM570307 | `72303BFBFBABC1138DB2C3EA938837726AA4679AA81D54896B344EE578F260D8` | `HM570307.bin` (16 MiB) | `BBB237F0D1FC85BC44B674BB138F6C8AD0646F8D38AF6576F521AEF8FB3EDCF1` |

These hashes were verified against downloads from the manufacturer page on
2026-08-25. A changed ZIP must be reviewed rather than silently accepted.

## Reproduce Setup PE32 and IFR

Required tools:

| Tool | Upstream | Archive SHA-256 | Executable SHA-256 |
|---|---|---|---|
| UEFIExtract NE A75, Windows x64 | <https://github.com/LongSoft/UEFITool/releases/tag/A75> | `20FF18208913D32C99E3B002717ABEDDAA3B6509AC62E6699E462B0F533BE646` | `E372554C8EC1C8F1AD123D739072EB699CF011D12D2D71954BCDB63C79812FB0` |
| IFRExtractor-RS 1.6.1, Windows | <https://github.com/LongSoft/IFRExtractor-RS/releases/tag/v1.6.1> | `3A0D93ECD3A4CB092D210C499D125FFD782982311F5F8DC40A8B180B58C4FFE7` | `01B50D394A93EDAD8299207AE0C88577D65DB5FC86280467AFAB55E486D62C1C` |

Run the pinned Python wrapper against the downloaded ZIP or its extracted BIN:

```powershell
python tools/extract_firmware_artifacts.py 'C:\Downloads\Polestar M-ATX G613 HM570111.zip'
```

Equivalent low-level extraction:

```powershell
UEFIExtract.exe HM570111.bin 899407D7-99FE-43D8-9A21-79EC328CAC21 `
  -o build\firmware\setup -m body -t 10
ifrextractor.exe build\firmware\setup\body.bin
```

Expected outputs:

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| Setup PE32 body | 908,320 | `BBB280F2B2F2F927A94BCFA8F29F79752FA68A19665F0962D29C523DABA34837` |
| en-US IFR text | 1,842,633 | `0F668F6D080F009BC82BB6B7AD82CFB08BBD8F7651AC4DA6477C019A05596465` |

The wrapper validates the package, firmware, tool executables, Setup body and
IFR output. It refuses unknown hashes.

## Runtime dump and MADT candidate

The tested system's runtime SPI dump is not obtainable from the public BIOS:
it contains board-specific NVRAM and persistent CSME data. Its private
reference SHA-256 is
`68E9A8113DDDA6E192AA72417E69BD83A3E37DC10D4F1421F0D3B282E49231BD`.

The layout-preserving MADT candidate is reproduced only from that exact private
dump:

```powershell
python archive/experiments/legacy-scripts/build_madt_lzma_patch.py `
  C:\private\polestar_full_1.bin build\firmware\madt-candidate.bin `
  --lzma-tool C:\tools\LzmaCompress.exe
```

The builder requires `LzmaCompress.exe` SHA-256
`AFA25C0D24EB12A30E6D4CCBB6262CE7444EBBD93A64A208AA2E17C931900093`
and must produce candidate SHA-256
`4F99E06399972E31D7D86383D8B81E451C7F75A5D5A00DB8CD8A34AFA25E8E73`.
This candidate remains an experiment and is not authorized for flashing.
