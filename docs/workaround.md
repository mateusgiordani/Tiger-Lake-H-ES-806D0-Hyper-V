# Known workaround

The only workaround currently demonstrated to allow native Hyper-V to boot on
the affected Erying/Polestar HM570 Tiger Lake-H ES platform is:

```powershell
bcdedit /set "{current}" hypervisorlaunchtype auto
bcdedit /set "{current}" xsavedisable 1
```

Use a test boot entry first and preserve a known-good Windows entry. Confirm
the setting with `bcdedit /enum` before rebooting. To roll back:

```powershell
bcdedit /deletevalue "{current}" xsavedisable
bcdedit /set "{current}" hypervisorlaunchtype off
```

This is a reversible boot-configuration workaround, not a firmware repair. It
does not prove which firmware component creates the CPUID/XSTATE inconsistency
and should not be combined with an unvalidated BIOS flash.

The MADT/OpenCore experiment is documented separately in
[`opencore-madt-experiment.md`](opencore-madt-experiment.md).
