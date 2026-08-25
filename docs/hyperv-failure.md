# RelatÃ³rio Final â€” Polestar HM570: do bootloop do Hyper-V ao workaround estÃ¡vel

**Placa:** Erying/Polestar HM570 \(famÃ­lia `HM570111`, BIOS AMI `THM570111` 06/08/2023\)
**CPU:** Tiger Lake-H Engineering Sample `806D0` \(family 6, model 0x8D, stepping 0, 8C/16T, microcode `0x50` de 17/12/2020\)
**GPU:** RX 7800 XT \(iGPU desabilitada, mas enumerada como `8086:9A60`\)
**PerÃ­odo:** 24â€“25/08/2026
**Estado atual:** `HV 07 SEM XSAVE` \(nativo, sem OpenCore\) boota com hipervisor ativo e libera `WSL2/Docker`

---

## 1. Qual era o problema

Windows limpo, `hypervisorlaunchtype=Auto` â†’ reset instantÃ¢neo antes do login. Sem tela azul, sem `MEMORY.DMP`, sÃ³ `Kernel-Power 41` com `BugCheckCode=0`. Linux/KVM com `VMX/EPT` funcionava normal, o que descartava â€œvirtualizaÃ§Ã£o desligadaâ€. `WSL2`, emuladores Android e `Docker` no Windows ficaram inutilizÃ¡veis porque todos exigem o hipervisor da Microsoft.

## 2. Caminhos da investigaÃ§Ã£o

### 2.1 Defeito ACPI confirmado: MADT

A `MADT` entregue tem 16 `Processor Local APIC` ativos `UID 0..15` \(APIC IDs `0,2,4,6,8,10,12,14,1,3,5,7,9,11,13,15`\) mas 16 `Local APIC NMI` apontando para `UID 1..16` \(LINT 1\). A CPU `0` fica sem NMI e a Ãºltima entrada aponta para `UID 16` inexistente. Origem: template embarcado `1..16` que o firmware corrige pra `0..15` nos LAPICs e esquece nos NMIs. Linux ignora o campo `UID` nesse parser, por isso o KVM passa.

Hashes de referÃªncia:
- Dump runtime validado: `68E9A8113DDDA6E192AA72417E69BD83A3E37DC10D4F1421F0D3B282E49231BD`
- `HM570111.bin`: `16529D3B622D150CB2E2EEDA95347C68A878532D39B8B3D9C1F4084A4CFFCCBE`
- Candidata layout-preserved \(sÃ³ 16 bytes NMI `1..16â†’0..15`\): `4F99E06399972E31D7D86383D8B81E451C7F75A5D5A00DB8CD8A34AFA25E8E73`

### 2.2 Segundo defeito confirmado: CPUID/XSTATE Ã³rfÃ£o

Dump `CPUID` nos 16 LPs:
- `CPUID.7:EBX[16] AVX512F = 0`, `EBX[31] AVX512VL = 0`
- `CPUID.7:EDX[8] AVX512_VP2INTERSECT = 1`
- `CPUID.D.0:EAX = 0x207` \(XCR0 bits 5â€“7 de AVX-512 ausentes\)

`NVRAM CpuSetup+0x22A = 1` \(AVX3 desabilitado\). A BIOS esconde AVX-512 pela metade e deixa o `VP2INTERSECT` Ã³rfÃ£o. Tentativa de ligar `AVX3` trava o POST neste `D0`, entÃ£o nÃ£o dÃ¡ pra coerenciar por `Setup`.

### 2.3 O que foi descartado

`IA32_VMX_*` idÃªnticos nos 16 LPs \(coleta Ubuntu 25/08, `tgl-vmx-msrs.json` `34B6B668...` vs `D084D8F4...`\), `EPT/VPID/APICv/MBEC/XSaves` completos, `DMAR` 80 bytes com 1Ã— `DRHD Include-All` em `FED91000` coerente. O silÃ­cio tem tudo que o `hvix64.exe` exige.

## 3. Tentativa com OpenCore

Para nÃ£o gravar BIOS Ã s cegas, montamos OpenCore `1.0.7 RELEASE` sem kexts, sÃ³ com patch de 96 bytes da `MADT` \(assinatura `APIC`, tamanho 300, `OemTableID` exato\):
- `PATCH ENABLED` â†’ entrega `NMI 0..15`, checksum recalculado, `SHA-256 DEC804...` confirmado via `GetSystemFirmwareTable`
- `CONTROL DISABLED` â†’ mesma cadeia, `MADT` original `1..16` \(controle negativo\)

Resultados com `Hyper-V baseline` pela cadeia OpenCore:
- `PATCH ENABLED` â†’ `SYSTEM_THREAD_EXCEPTION_NOT_HANDLED (0x7E)` visÃ­vel, `C0000005`, mesmo offset `0xA96`
- `CONTROL DISABLED` ainda pendente atÃ© 25/08

A cadeia OpenCore por si sÃ³ jÃ¡ muda o mapa de memÃ³ria UEFI e faz o boot avanÃ§ar mais longe que a cadeia nativa.

## 4. O experimento de controle \(25/08, 10:43\)

Entrada `Windows - HYPERV OPENCORE CONTROL` \(GUID `5cbe73ca-b469-11f0-9ffb-c2e7dda09ff1`, `hypervisorlaunchtype Auto`, `vsmlaunchtype Off`, `nocrashautoreboot Yes`, `bootlog Yes`\), pendrive em `CONTROL DISABLED` \(`B537E452...`\).

Linha do tempo capturada:
- `10:43:35` boot da HV via OpenCore inicia \(ntbtlog criado\)
- `10:43:42` reset silencioso, ~7 s, 171 drivers carregados atÃ© `cdd.dll` \(Canonical Display Driver â€” inicializaÃ§Ã£o de sessÃ£o\), sem bugcheck/dump
- `10:44â€“11:02` seis resets, `Eventos 41/6008`, `10:56` Reparo de InicializaÃ§Ã£o executou

InterpretaÃ§Ã£o: `MADT` corrigida vs original **muda o modo de falha** \(reset silencioso â†’ `0x7E`\). CorreÃ§Ã£o necessÃ¡ria, mas nÃ£o suficiente. EvidÃªncia preservada em `evidence/boot/control-run-20260825/`.

## 5. Matriz BCD e a descoberta acidental

Criamos 18 entradas persistentes \(nÃ£o one-shot\) com `prepare-hyperv-diagnostic-matrix.ps1` \(15 s de menu, `{current}` padrÃ£o seguro\). Testes relatados:
- `HV 01 BASELINE` â†’ falha
- `HV 07 SEM XSAVE (xsavedisable=1)` â†’ falha pela cadeia OpenCore
- `HV 03 xAPIC LEGADO` â†’ `0x7E`

O `Recovery` do Windows atrapalhou \(exigiu `recoveryenabled No` / `bootstatuspolicy IgnoreAllFailures` / `reagentc /disable` temporÃ¡rio\).

**Descoberta:** ao sair da cadeia OpenCore e bootar **nativo** pelo `Windows Boot Manager`, `HV 07 SEM XSAVE` **bootou atÃ© o desktop com hipervisor ativo**:
```
HypervisorPresent: True
systeminfo: Hipervisor detectado
```
Todos os boots via OpenCore falhavam; sem ele, o `xsavedisable` isolou o Ã³rfÃ£o e o hipervisor subiu.

## 6. Por que o bootloader do Windows conseguiu â€œpatchearâ€ fora da BIOS

O `hvloader.dll` lÃª `hypervisorloadoptions`/`xsavedisable` do BCD antes de lanÃ§ar o `hvix64.exe`. Com `xsavedisable=1` ele desliga `XSAVE/XSTATE` pro hipervisor e **ignora a validaÃ§Ã£o incoerente** do `VP2INTERSECT` sem estado. Ã‰ um *workaround* de bootloader â€” nÃ£o conserta o `CPUID` do silÃ­cio, sÃ³ diz ao hipervisor pra nÃ£o validar aquele contrato. Por isso funciona sem gravar nada.

O OpenCore nÃ£o consegue fazer isso: ele sÃ³ entrega `ACPI`/mapa de memÃ³ria. `CPUID/XSTATE` Ã© lido direto da instruÃ§Ã£o, fora do alcance de patch `ACPI`.

## 7. SoluÃ§Ã£o do dia-a-dia adotada

Transformar o `HV 07` em padrÃ£o nativo:
```powershell
bcdedit /set "{current}" hypervisorlaunchtype auto
bcdedit /set "{current}" xsavedisable 1
bcdedit /set "{current}" vsmlaunchtype off
```
Com `VirtualMachinePlatform` habilitado, `WSL2`/`Docker` voltam. `IOMMU` continua ligado, `x2APIC` continua ligado, performance de `EPT/MBEC` preservada â€” sÃ³ o `XSAVE` do hipervisor fica desligado.

## 8. PrÃ³ximos passos e opÃ§Ã£o definitiva na BIOS

- Manter `xsavedisable` como workaround reversÃ­vel Ã© o recomendado hoje.
- Patch definitivo na flash exigiria esconder `VP2INTERSECT` no firmware \(mÃ³dulo que monta `CPUID.7` ou microcode\), mais invasivo que a `MADT` e sem microcode pÃºblico novo para `806D0` \(`0x50` Ã© o Ãºnico\). Com seu `CH341` jÃ¡ detectado (`ch341ser`/`ch341wdm`), a candidata `MADT` + eventual mÃ¡scara de `CPUID` pode ser preparada, mas sÃ³ com as 3 leituras externas idÃªnticas, checagem de tensÃ£o `1.8V/3.3V` e validaÃ§Ã£o de restauraÃ§Ã£o.
- Para ir mais fundo sem flash, o prÃ³ximo instrumento Ã© `KDNET` no Realtek `10EC:8168` via segundo PC cabeado, agora pela cadeia **nativa** com `HV 07`.

---

### Artefatos

- `firmware/patches/candidates/polestar-hyperv-madt-nmi-zero-based-layout-preserved.bin`
- `evidence/msr/linux/ANALISE_LINUX_MSR.md`
- `evidence/boot/control-run-20260825/ntbtlog.txt` e `system-events.json`
- `evidence/boot/bcd-backups/hyperv-matrix-*.json`
