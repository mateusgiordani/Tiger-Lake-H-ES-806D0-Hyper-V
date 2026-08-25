# Documentação Estável e Reprodutível — Polestar HM570 Hyper-V

**Objetivo:** reativar `WSL2/Docker/Hyper-V` nesta placa de forma **reversível, sem gravar BIOS**, a partir do estado atual validado em 25/08/2026.

---

## 1. Hardware e firmware em execução

- **Placa:** Polestar/Erying HM570, família `HM570111`, BIOS AMI `THM570111` \(SMBIOS `06/08/2023`\)
- **CPU:** Tiger Lake-H ES `806D0` \(family 6, model `0x8D` = 141, stepping 0, 8C/16T, APIC IDs `0,2,4,6,8,10,12,14,1,3,5,7,9,11,13,15`\)
- **Microcode ativo:** `0x50` \(payload 17/12/2020, `MSR 0x8B` e `Win32_VideoController` confirmam, sem payload público novo para `06-8d-00`\)
- **GPU em uso:** RX 7800 XT \(driver estável `32.0.31035.1003` de 24/07/2026, `amduw23g-203304`\), iGPU `8086:9A60` enumerada mas desabilitada no `Setup`
- **SPI:** Winbond `EF4018`, 16 MiB, `FPT 15.0.20.1419` com Descriptor válido
- **Armazenamento:** NVMe Windows \(Netac\) + NVMe Ubuntu \(Lexar/KDE\) com bootloaders separados, ESP do Windows em `disk1/part1`
- **Rede para KDNET futuro:** Realtek `10EC:8168` \(lista oficial Microsoft\)

## 2. Qual BIOS você está rodando vs o que está na pasta

| Arquivo | SHA-256 | Layout | Status |
|---|---|---|---|
| `HM570111.bin` | `16529D3B622D150CB2E2EEDA95347C68A878532D39B8B3D9C1F4084A4CFFCCBE` | ME `0x001000`, BIOS `0x500000` | **Referência de fábrica da sua família** |
| Runtime `polestar_full_1.bin` | `68E9A8113DDDA6E192AA72417E69BD83A3E37DC10D4F1421F0D3B282E49231BD` | idem | **O que está gravado hoje** — idêntico ao `HM570111` de `0x560000` a `0xFFFFFF`, diferenças só em `0x50008F..0x55FFFF` \(NVRAM\+espelho\) e `0x1FA000..0x278307` \(CSME persistente\) |
| `HM570307.bin` | `BBB237F0D1FC85BC44B674BB138F6C8AD0646F8D38AF6576F521AEF8FB3EDCF1` | ME `0x001000`, BIOS `0x500000` | Família diferente, 28 módulos diferentes, **não gravar** |
| `BIOSATUALIZADA.bin` | `AD7ADFC9E82A280445D977104D3226D49E895B1AB5413A45A7324ACA34598F6A` | ME `0x001000`, BIOS `0x400000` | **Layout incompatível**, não usar como doadora nem recuperação |
| Candidata `polestar-hyperv-madt-nmi-zero-based-layout-preserved.bin` | `4F99E06399972E31D7D86383D8B81E451C7F75A5D5A00DB8CD8A34AFA25E8E73` | idem runtime | Só 16 bytes NMI `1..16→0..15`, **não autorizada pra flash ainda** |

**Conclusão:** sua BIOS atual é `HM570111`. Use sempre os 3 dumps `polestar_full_*.bin` como recuperação, nunca `BIOSATUALIZADA.bin`.

### 2.1 Variáveis ativas validadas \(NVRAM `500078h`/`530078h` idênticas\)

```
CpuSetup+0x0B9 VMX=1, +0x22A AVX3=1 (AVX512 off), +0x229 AVX=0 (AVX on)
SaSetup+0x087 VT-d=1, +0x091 X2APIC Opt-Out=0, +0x092 DMA Guarantee=1
Setup+0x8D3 IOMMU pre-boot=0, +0x6E8 MSI=1
```
`AVX3=Disabled` é obrigatório neste `D0` \(ligar trava POST\), mas deixa órfão `VP2INTERSECT`.

## 3. Achados no Linux \(Ubuntu 24.04, kernel `6.14.0-37`, coleta `run-in-ubuntu.sh`\)

Evidências em `analysis/linux-msr/vmx-ON` \(`34B6B668...`\) e `vmx-OFF` \(`D084D8F4...`\):

- **16 LPs idênticos:** `identical_msr_groups=[[0..15]]` \(normalizado TSC/BSP\), sem divergência AP→BSP
- **Feature Control:** `locked=1, vmx_outside_smx=1` em todos, coerente; com `VMX` desligado vira `0x1` limpo
- **VMX_BASIC:** `rev 0x13, 1280B, memtype WB, >32-bit PA, true controls` — normal TGL
- **Capacidades completas:** `EPT` \(exec-only/2M/1G/INVEPT all\), `VPID` \(all INVVPID\), suíte `APICv` \(APIC-access/x2APIC/APIC-reg/VID/posted/VNMI\), `MBEC`, `XSaves`, `VMCS shadowing`, `VMFUNC` — nada faltando
- **x2APIC+IR funciona no hardware:** `dmesg` mostra `DMAR-IR: Enabled IRQ remapping in x2apic mode`, `x2apic enabled`, `IOAPIC 2` sob `FED91000`, e a mesma `MADT` defeituosa `LAPIC_NMI acpi_id[0x01]..[0x10]`
- **Microcode `0x50`** nos 16 LPs, topologia `0,2,4...14,1,3...15` idêntica à `MADT`

**Descarta:** divergência `VMX` por LP e falta de `EPT/APICv` no silício. Reforça: o segundo defeito é `CPUID/XSTATE` e/ou consumo de `MADT` pelo hipervisor.

## 4. Achados no Windows \(além da MADT\)

- **MADT:** `300` bytes, `NMI 1..16` vs `CPU 0..15` \(controle 25/08: `NMI 0..15` corrigida muda `reset silencioso→0x7E`\), `DMAR` 80 bytes `HAW 0x26` com 1× `DRHD`, `DSDT` com bug `PR16` usando `PF15`
- **CPUID:** `VP2INTERSECT=1` sem `AVX512F/VL/XSTATE 5-7` em todos os LPs
- **Hyper-V:** `hvix64.exe 10.0.26100.9168` com caminhos de `MinimalLoop/NMI/MachineCheck` que reiniciam sem bugcheck

## 5. Guia reprodutível — ativar Hyper-V de forma segura

> **Princípio:** nada é gravado na flash. Tudo é BCD reversível, `{current}` permanece padrão seguro até você decidir tornar permanente.

### 5.1 Pré-requisitos \(uma vez\)

1. BitLocker `C:` descriptografado, Secure Boot `Off` nos testes com OpenCore \(se usar\), SanDisk com `EFI-FPT-BACKUP` intacto
2. PowerShell **como Administrador**

### 5.2 Backup e matriz \(cria 18 entradas persistentes, não one-shot\)

```powershell
Set-Location 'C:\Users\estum\OneDrive\Área de Trabalho\projeto conserto bios\bios-interposer'
.\analysis\scripts\prepare-hyperv-diagnostic-matrix.ps1          # dry-run
.\analysis\scripts\prepare-hyperv-diagnostic-matrix.ps1 -Apply   # cria + backup em analysis\bcd-backups\hyperv-matrix-*.json
```

Evite o menu de `Recovery`: antes dos testes \(temporário\):
```powershell
bcdedit /set "{current}" recoveryenabled No
bcdedit /set "{current}" bootstatuspolicy IgnoreAllFailures
reagentc /disable
```

### 5.3 Testar — ordem que mais separa causa \(sempre que possível pela cadeia nativa, sem OpenCore\)

| Ordem | Entrada | Isola | Esperado se for a causa |
|---|---|---|---|
| 1 | `HV 07 SEM XSAVE` | `VP2INTERSECT` órfão | **Boota com `HypervisorPresent: True`** \(foi o que bootou em 25/08 nativo\) |
| 2 | `HV 03 xAPIC LEGADO` | `x2APIC` | `0x7E` vs reset |
| 3 | `HV 05 MINIMO` | SMP+IOMMU+xAPIC | Se só ele bootar, falha é composta |

Para cada boot: anote `reset / 0x7E (4 params) / bootou`, fotografe BSOD, e já no desktop rode:
```powershell
(Get-CimInstance Win32_ComputerSystem).HypervisorPresent
systeminfo | findstr Hyper
wsl --status
```
Se cair no Recovery, escolha **Sair e continuar para o Windows**.

### 5.4 Tornar o dia-a-dia estável \(quando `HV 07` for o vencedor\)

```powershell
bcdedit /set "{current}" hypervisorlaunchtype auto
bcdedit /set "{current}" xsavedisable 1
bcdedit /set "{current}" vsmlaunchtype off
bcdedit /set "{current}" description "Windows - HV07 XSAVE OFF (dia-a-dia)"
bcdedit /default "{current}"
bcdedit /timeout 5
Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -All
```
`WSL2/Docker` voltam sem pendrive. Mantenha `Hyper-V` instalado, `VirtualMachinePlatform` ligado, driver AMD `32.0.31035.1003` de `24/07/2026` \(evite a `32.0.31041.1004` de `17/08` que congelou o logon após o Reparo de Inicialização\).

### 5.5 Limpeza e reversão

```powershell
.\analysis\scripts\remove-hyperv-diagnostic-matrix.ps1 -ManifestPath 'analysis\bcd-backups\hyperv-matrix-xxxxxxxx-xxxxxx.json' -Apply
bcdedit /set "{current}" recoveryenabled Yes
bcdedit /set "{current}" bootstatuspolicy DisplayAllFailures
reagentc /enable
# se não quiser mais hipervisor no dia-a-dia:
bcdedit /set "{current}" hypervisorlaunchtype off
bcdedit /deletevalue "{current}" xsavedisable
```

### 5.6 Quando gravar BIOS

Só se houver evidência causal clara e após: 3 leituras externas idênticas com `CH341` \(confirme `1.8V` vs `3.3V` no chip `EF4018`\), comparação com `68E9A811...`, e teste de restauração do dump original. A candidata `MADT` sozinha não resolveu; eventual patch definitivo teria que esconder também o `VP2INTERSECT`, mais invasivo que o BCD.

---

### Artefatos para reprodução

- `analysis/control-run-20260825/RELATORIO.md` — controle OpenCore
- `analysis/linux-msr/ANALISE_LINUX_MSR.md` — MSRs
- `analysis/RELATORIO_FINAL_HYPERV.md` — narrativa completa
- `analysis/candidates/...layout-preserved.bin` — candidata
- `backup da bios que estava rodando/polestar_full_*.bin` — recuperação
