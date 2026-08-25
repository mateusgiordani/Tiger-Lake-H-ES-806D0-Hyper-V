# Known workaround

The boot that demonstrated native Hyper-V on the affected Erying/Polestar HM570
Tiger Lake-H ES platform used BCD entry `HV 07 SEM XSAVE` from the diagnostic
matrix. That entry sets the causal fix for the CPUID/XSTATE inconsistency; the
matrix script also applied `vsmlaunchtype=off` to every test entry, so VSM was
not isolated in that successful run.

**Required for the demonstrated XSAVE workaround**

```powershell
bcdedit /set "{current}" hypervisorlaunchtype auto
bcdedit /set "{current}" xsavedisable 1
```

**Also present in the successful test environment**

```powershell
bcdedit /set "{current}" vsmlaunchtype off
```

Do not claim that `xsavedisable=1` alone is sufficient until a boot confirms
Hyper-V with default VSM settings. Until that isolation test exists, treat
`vsmlaunchtype=off` as part of the observed working configuration, not as a
proven optional extra.

Use a test boot entry first and preserve a known-good Windows entry. Confirm
the settings with `bcdedit /enum` before rebooting. To roll back:

```powershell
bcdedit /deletevalue "{current}" xsavedisable
bcdedit /set "{current}" hypervisorlaunchtype off
```

This is a reversible boot-configuration workaround, not a firmware repair. It
does not prove which firmware component creates the CPUID/XSTATE inconsistency
and should not be combined with an unvalidated BIOS flash.

The MADT/OpenCore experiment is documented separately in
[`opencore-madt-experiment.md`](opencore-madt-experiment.md).
