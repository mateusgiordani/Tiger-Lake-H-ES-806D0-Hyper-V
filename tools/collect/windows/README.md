# Windows collectors

These read-only collectors emit evidence for the normalized platform schema.

The CPUID collector records CPUID as visible in the current execution context and
Windows instruction availability from `IsProcessorFeaturePresent` for SSE,
SSE2, XSAVE, AVX, AVX2 and AVX-512F. Hyper-V or boot policy can mask visible
CPUID, so compare captures from normal and diagnostic BCD entries. A capture
with Hyper-V active is explicitly labeled `windows_root_partition`; it is not
bare-metal CPUID. The combined evidence also attempts a read-only collection of
the current BCD entry. If BCDEdit access is denied, the JSON records the BCD
evidence as unavailable instead of inferring `xsavedisable=1`.

The collector supports:

```powershell
python tools/collect/windows/dump_cpuid_windows.py --normalized platform.json
```

The combined collector can also save the MADT:

```powershell
python tools/collect/windows/collect_platform.py platform.json --madt-output apic.dat
```
