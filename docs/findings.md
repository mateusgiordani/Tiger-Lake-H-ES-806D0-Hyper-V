# DocumentaÃ§Ã£o EstÃ¡vel e ReprodutÃ­vel â€” Polestar HM570 Hyper-V

**Objetivo:** reativar `WSL2/Docker/Hyper-V` nesta placa de forma **reversÃ­vel, sem gravar BIOS**, a partir do estado atual validado em 25/08/2026.

---

## 1. Hardware e firmware em execuÃ§Ã£o

- **Placa:** Polestar/Erying HM570, famÃ­lia `HM570111`, BIOS AMI `THM570111` \(SMBIOS `06/08/2023`\)
- **CPU:** Tiger Lake-H ES `806D0` \(family 6, model `0x8D` = 141, stepping 0, 8C/16T, APIC IDs `0,2,4,6,8,10,12,14,1,3,5,7,9,11,13,15`\)
- **Microcode ativo:** `0x50` \(payload 17/12/2020, `MSR 0x8B` e `Win32_VideoController` confirmam, sem payload pÃºblico novo para `06-8d-00`\)
- **GPU em uso:** RX 7800 XT \(driver estÃ¡vel `32.0.31035.1003` de 24/07/2026, `amduw23g-203304`\), iGPU `8086:9A60` enumerada mas desabilitada no `Setup`
- **SPI:** Winbond `EF4018`, 16 MiB, `FPT 15.0.20.1419` com Descriptor vÃ¡lido
- **Armazenamento:** NVMe Windows \(Netac\) + NVMe Ubuntu \(Lexar/KDE\) com bootloaders separados, ESP do Windows em `disk1/part1`
- **Rede para KDNET futuro:** Realtek `10EC:8168` \(lista oficial Microsoft\)

## 2. Qual BIOS vocÃª estÃ¡ rodando vs o que estÃ¡ na pasta

| Arquivo | SHA-256 | Layout | Status |
|---|---|---|---|
| `HM570111.bin` | `16529D3B622D150CB2E2EEDA95347C68A878532D39B8B3D9C1F4084A4CFFCCBE` | ME `0x001000`, BIOS `0x500000` | **ReferÃªncia de fÃ¡brica da sua famÃ­lia** |
| Runtime `polestar_full_1.bin` | `68E9A8113DDDA6E192AA72417E69BD83A3E37DC10D4F1421F0D3B282E49231BD` | idem | **O que estÃ¡ gravado hoje** â€” idÃªntico ao `HM570111` de `0x560000` a `0xFFFFFF`, diferenÃ§as sÃ³ em `0x50008F..0x55FFFF` \(NVRAM\+espelho\) e `0x1FA000..0x278307` \(CSME persistente\) |
| `HM570307.bin` | `BBB237F0D1FC85BC44B674BB138F6C8AD0646F8D38AF6576F521AEF8FB3EDCF1` | ME `0x001000`, BIOS `0x500000` | FamÃ­lia diferente, 28 mÃ³dulos diferentes, **nÃ£o gravar** |
| `BIOSATUALIZADA.bin` | `AD7ADFC9E82A280445D977104D3226D49E895B1AB5413A45A7324ACA34598F6A` | ME `0x001000`, BIOS `0x400000` | **Layout incompatÃ­vel**, nÃ£o usar como doadora nem recuperaÃ§Ã£o |
| Candidata `polestar-hyperv-madt-nmi-zero-based-layout-preserved.bin` | `4F99E06399972E31D7D86383D8B81E451C7F75A5D5A00DB8CD8A34AFA25E8E73` | idem runtime | SÃ³ 16 bytes NMI `1..16â†’0..15`, **nÃ£o autorizada pra flash ainda** |

**ConclusÃ£o:** sua BIOS atual Ã© `HM570111`. Use sempre os 3 dumps `polestar_full_*.bin` como recuperaÃ§Ã£o, nunca `BIOSATUALIZADA.bin`.

### 2.1 VariÃ¡veis ativas validadas \(NVRAM `500078h`/`530078h` idÃªnticas\)

```
CpuSetup+0x0B9 VMX=1, +0x22A AVX3=1 (AVX512 off), +0x229 AVX=0 (AVX on)
SaSetup+0x087 VT-d=1, +0x091 X2APIC Opt-Out=0, +0x092 DMA Guarantee=1
Setup+0x8D3 IOMMU pre-boot=0, +0x6E8 MSI=1
```
`AVX3=Disabled` Ã© obrigatÃ³rio neste `D0` \(ligar trava POST\), mas deixa Ã³rfÃ£o `VP2INTERSECT`.

## 3. Achados no Linux \(Ubuntu 24.04, kernel `6.14.0-37`, coleta `run-in-ubuntu.sh`\)

EvidÃªncias em `evidence/msr/linux/vmx-ON` \(`34B6B668...`\) e `vmx-OFF` \(`D084D8F4...`\):

- **16 LPs idÃªnticos:** `identical_msr_groups=[[0..15]]` \(normalizado TSC/BSP\), sem divergÃªncia APâ†’BSP
- **Feature Control:** `locked=1, vmx_outside_smx=1` em todos, coerente; com `VMX` desligado vira `0x1` limpo
- **VMX_BASIC:** `rev 0x13, 1280B, memtype WB, >32-bit PA, true controls` â€” normal TGL
- **Capacidades completas:** `EPT` \(exec-only/2M/1G/INVEPT all\), `VPID` \(all INVVPID\), suÃ­te `APICv` \(APIC-access/x2APIC/APIC-reg/VID/posted/VNMI\), `MBEC`, `XSaves`, `VMCS shadowing`, `VMFUNC` â€” nada faltando
- **x2APIC+IR funciona no hardware:** `dmesg` mostra `DMAR-IR: Enabled IRQ remapping in x2apic mode`, `x2apic enabled`, `IOAPIC 2` sob `FED91000`, e a mesma `MADT` defeituosa `LAPIC_NMI acpi_id[0x01]..[0x10]`
- **Microcode `0x50`** nos 16 LPs, topologia `0,2,4...14,1,3...15` idÃªntica Ã  `MADT`

**Descarta:** divergÃªncia `VMX` por LP e falta de `EPT/APICv` no silÃ­cio. ReforÃ§a: o segundo defeito Ã© `CPUID/XSTATE` e/ou consumo de `MADT` pelo hipervisor.

## 4. Achados no Windows \(alÃ©m da MADT\)

- **MADT:** `300` bytes, `NMI 1..16` vs `CPU 0..15` \(controle 25/08: `NMI 0..15` corrigida muda `reset silenciosoâ†’0x7E`\), `DMAR` 80 bytes `HAW 0x26` com 1Ã— `DRHD`, `DSDT` com bug `PR16` usando `PF15`
- **CPUID:** `VP2INTERSECT=1` sem `AVX512F/VL/XSTATE 5-7` em todos os LPs
- **Hyper-V:** `hvix64.exe 10.0.26100.9168` com caminhos de `MinimalLoop/NMI/MachineCheck` que reiniciam sem bugcheck

## 5. Guia reprodutÃ­vel â€” ativar Hyper-V de forma segura

> **PrincÃ­pio:** nada Ã© gravado na flash. Tudo Ã© BCD reversÃ­vel, `{current}` permanece padrÃ£o seguro atÃ© vocÃª decidir tornar permanente.

### 5.1 PrÃ©-requisitos \(uma vez\)

1. BitLocker `C:` descriptografado, Secure Boot `Off` nos testes com OpenCore \(se usar\), SanDisk com `EFI-FPT-BACKUP` intacto
2. PowerShell **como Administrador**

### 5.2 Backup e matriz \(cria 18 entradas persistentes, nÃ£o one-shot\)

```powershell
Set-Location (git rev-parse --show-toplevel)
archive\experiments\legacy-scripts\prepare-hyperv-diagnostic-matrix.ps1          # dry-run
archive\experiments\legacy-scripts\prepare-hyperv-diagnostic-matrix.ps1 -Apply   # cria + backup em evidence\boot\bcd-backups\hyperv-matrix-*.json
```

Evite o menu de `Recovery`: antes dos testes \(temporÃ¡rio\):
```powershell
bcdedit /set "{current}" recoveryenabled No
bcdedit /set "{current}" bootstatuspolicy IgnoreAllFailures
reagentc /disable
```

### 5.3 Testar â€” ordem que mais separa causa \(sempre que possÃ­vel pela cadeia nativa, sem OpenCore\)

| Ordem | Entrada | Isola | Esperado se for a causa |
|---|---|---|---|
| 1 | `HV 07 SEM XSAVE` | `VP2INTERSECT` Ã³rfÃ£o | **Boota com `HypervisorPresent: True`** \(foi o que bootou em 25/08 nativo\) |
| 2 | `HV 03 xAPIC LEGADO` | `x2APIC` | `0x7E` vs reset |
| 3 | `HV 05 MINIMO` | SMP+IOMMU+xAPIC | Se sÃ³ ele bootar, falha Ã© composta |

Para cada boot: anote `reset / 0x7E (4 params) / bootou`, fotografe BSOD, e jÃ¡ no desktop rode:
```powershell
(Get-CimInstance Win32_ComputerSystem).HypervisorPresent
systeminfo | findstr Hyper
wsl --status
```
Se cair no Recovery, escolha **Sair e continuar para o Windows**.

### 5.4 Tornar o dia-a-dia estÃ¡vel \(quando `HV 07` for o vencedor\)

```powershell
bcdedit /set "{current}" hypervisorlaunchtype auto
bcdedit /set "{current}" xsavedisable 1
bcdedit /set "{current}" vsmlaunchtype off
bcdedit /set "{current}" description "Windows - HV07 XSAVE OFF (dia-a-dia)"
bcdedit /default "{current}"
bcdedit /timeout 5
Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -All
```
`WSL2/Docker` voltam sem pendrive. Mantenha `Hyper-V` instalado, `VirtualMachinePlatform` ligado, driver AMD `32.0.31035.1003` de `24/07/2026` \(evite a `32.0.31041.1004` de `17/08` que congelou o logon apÃ³s o Reparo de InicializaÃ§Ã£o\).

### 5.5 Limpeza e reversÃ£o

```powershell
archive\experiments\legacy-scripts\remove-hyperv-diagnostic-matrix.ps1 -ManifestPath 'evidence\boot\bcd-backups\hyperv-matrix-xxxxxxxx-xxxxxx.json' -Apply
bcdedit /set "{current}" recoveryenabled Yes
bcdedit /set "{current}" bootstatuspolicy DisplayAllFailures
reagentc /enable
# se nÃ£o quiser mais hipervisor no dia-a-dia:
bcdedit /set "{current}" hypervisorlaunchtype off
bcdedit /deletevalue "{current}" xsavedisable
```

### 5.6 Quando gravar BIOS

SÃ³ se houver evidÃªncia causal clara e apÃ³s: 3 leituras externas idÃªnticas com `CH341` \(confirme `1.8V` vs `3.3V` no chip `EF4018`\), comparaÃ§Ã£o com `68E9A811...`, e teste de restauraÃ§Ã£o do dump original. A candidata `MADT` sozinha nÃ£o resolveu; eventual patch definitivo teria que esconder tambÃ©m o `VP2INTERSECT`, mais invasivo que o BCD.

---

### Artefatos para reproduÃ§Ã£o

- `evidence/boot/control-run-20260825/RELATORIO.md` â€” controle OpenCore
- `evidence/msr/linux/ANALISE_LINUX_MSR.md` â€” MSRs
- `archive/experiments/RELATORIO_FINAL_HYPERV.md` â€” narrativa completa
- `firmware/patches/candidates/...layout-preserved.bin` â€” candidata
- `backup da bios que estava rodando/polestar_full_*.bin` â€” recuperaÃ§Ã£o
