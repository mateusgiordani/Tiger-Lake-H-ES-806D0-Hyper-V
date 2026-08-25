# Hyper-V MADT patch candidates

## Accepted for further hardware testing

`polestar-hyperv-madt-nmi-zero-based-layout-preserved.bin`

- Bytes: `16,777,216`
- SHA-256: `4F99E06399972E31D7D86383D8B81E451C7F75A5D5A00DB8CD8A34AFA25E8E73`
- Source dump SHA-256: `68E9A8113DDDA6E192AA72417E69BD83A3E37DC10D4F1421F0D3B282E49231BD`
- Logical change: sixteen MADT Local APIC NMI Processor UID bytes, from
  `1..16` to `0..15`.
- Descriptor, CSME, NVRAM, DMAR, DSDT/SSDT, executable modules, microcode,
  FFS headers, section headers, sizes and offsets are preserved.
- UEFIExtract A75 found 1,949 leaf bodies before and after; exactly one leaf
  differs, the 300-byte embedded MADT.

This image is **not yet authorized for flashing**. First obtain three matching
external-programmer reads, verify the chip voltage, prove recovery with the
original dump, and prepare a Hyper-V-off BCD recovery entry.

## Rejected build

The first old-engine rebuild is under
`../rejected/DO-NOT-FLASH-old-engine-rebuild/`. It is retained only as analysis
evidence and must not be flashed. UEFIPatch 0.28 reconstructed the full nested
volume and emitted a non-empty pad-file warning; the layout-preserved candidate
supersedes it.
