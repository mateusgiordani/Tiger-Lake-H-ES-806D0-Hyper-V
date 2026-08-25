# AnÃ¡lise aprofundada â€” Polestar/Interposer HM570

Data da anÃ¡lise: 24/08/2026

## Escopo e seguranÃ§a

Esta etapa foi inteiramente de leitura e anÃ¡lise. NÃ£o houve gravaÃ§Ã£o na SPI, alteraÃ§Ã£o de NVRAM, ativaÃ§Ã£o do Hyper-V, mudanÃ§a no BCD ou reinicializaÃ§Ã£o.

O sistema em execuÃ§Ã£o identifica a BIOS como `THM570111`, AMI, data SMBIOS 06/08/2023. O processador Ã© um Tiger Lake ES, CPUID `806D0`, 8 nÃºcleos/16 threads, com microcode ativo `0x50`.

A prÃ³pria pÃ¡gina da Erying separa placas `HM5701xx` (imagem 111) de `HM5703xx` (imagem 307) e alerta que gravar a famÃ­lia errada pode causar tela preta. Isso reforÃ§a a decisÃ£o de nunca usar uma imagem 307/â€œLightningâ€ inteira como atalho: qualquer candidata deste trabalho deriva do dump runtime `THM570111` da prÃ³pria placa. Fonte: [Erying â€” Polestar 11th Gen HM570](https://www.erying.cc/sys-pd/20.html).

## Imagens analisadas

| Imagem | SHA-256 | Layout principal |
|---|---|---|
| `HM570111.bin` | `16529D3B622D150CB2E2EEDA95347C68A878532D39B8B3D9C1F4084A4CFFCCBE` | ME comeÃ§a em `0x001000`; BIOS em `0x500000` |
| `HM570307.bin` | `BBB237F0D1FC85BC44B674BB138F6C8AD0646F8D38AF6576F521AEF8FB3EDCF1` | ME comeÃ§a em `0x001000`; BIOS em `0x500000` |
| `BIOSATUALIZADA.bin` | `AD7ADFC9E82A280445D977104D3226D49E895B1AB5413A45A7324ACA34598F6A` | ME comeÃ§a em `0x001000`; BIOS em `0x400000` |

ConclusÃ£o importante: `BIOSATUALIZADA.bin` nÃ£o tem o mesmo particionamento das HM570111/HM570307. Ela nÃ£o deve ser misturada por regiÃµes nem gravada integralmente como se fosse equivalente.

## Descriptor SPI e CSME

Nas trÃªs imagens, o Intel Flash Descriptor declara acesso de leitura e escrita do host Ã s regiÃµes Descriptor, BIOS, ME, GbE e PDR. Isso indica um descriptor aberto na imagem. Um bloqueio adicional ainda pode ser aplicado em runtime pelo chipset/firmware.

Chips listados na tabela VSCC do projeto:

- Winbond `W25Q256` (`EF4019`)
- Macronix `MX25L256` (`C22019`)
- Winbond `W25Q128` (`EF4018`)

O cÃ³digo exato escrito no chip fÃ­sico deve ser lido antes de selecionar o componente no programador.

| Imagem | CSME | Plataforma | Estado | FWUpdate |
|---|---|---|---|---|
| HM570111 | `15.0.35.2039` | TGP/EBG-H stepping B | Configured | No |
| HM570307 | `15.0.21.1503` | TGP/EBG-H stepping A | Initialized | No |
| BIOSATUALIZADA | `15.0.35.1932` | TGP/EBG-H stepping B | Configured | No |

O descriptor aberto e o campo CSME `FWUpdate Support: No` nÃ£o sÃ£o contraditÃ³rios: o primeiro controla permissÃµes de regiÃµes SPI; o segundo descreve o mecanismo de atualizaÃ§Ã£o do firmware CSME. O backup completo via FPT pode funcionar, mas precisa ser validado pelo resultado e pelo hash.

As imagens contÃªm Startup ACM, mas o analisador nÃ£o conseguiu encontrar Key Manifest/Boot Policy Manifest vÃ¡lidos; as entradas FIT tÃªm tamanho zero e os ranges AMI protegidos estÃ£o preenchidos com `FF`. Isso sugere placeholders ou uma configuraÃ§Ã£o de engenharia, mas nÃ£o prova sozinho que Boot Guard esteja desativado nos fusÃ­veis.

## Microcode e VMX

As trÃªs imagens contÃªm microcode para CPUID `806D0`, revisÃ£o `0x50`, data 17/12/2020. O Windows tambÃ©m estÃ¡ executando a revisÃ£o `0x50`.

Portanto, a hipÃ³tese de â€œmicrocode ausente para o ESâ€ foi refutada. Linux/KVM funcionar e o Windows reportar suporte ao hipervisor tambÃ©m mostram que VMX/EPT nÃ£o estÃ£o simplesmente ausentes.

## Setup/IFR e defaults reais das imagens

O Setup AMI possui menus internos de engenharia e opÃ§Ãµes ocultas. Nas HM570111 e HM570307:

| Ajuste | VarStore/offset | HM570111 | HM570307 |
|---|---:|---:|---:|
| Intel VMX | `CpuSetup + 0xB9` | `1` | `1` |
| VT-d global | `SaSetup + 0x87` | `1` | `0` |
| X2APIC Opt Out | `SaSetup + 0x91` | `0` | `0` |
| DMA Control Guarantee | `SaSetup + 0x92` | `1` | `1` |
| IGD/IPU/IOP/ITBT VT-d | `SaSetup + 0x93..0x96` | `1` | `1` |
| MSI | `Setup + 0x6E8` | `1` | `1` |
| IOMMU preboot | `Setup + 0x8D3` | `0` | `0` |
| IOAPIC IRQ 24â€“119 | `PchSetup + 0x5FF` | `1` | `1` |
| CFG Lock | `CpuSetup + 0x43` | `0` | `0` |

Achado relevante: o IFR das duas BIOS marca VT-d como â€œEnabled, Defaultâ€, mas o bloco externo de defaults da HM570307 grava `0`. Logo, os defaults externos podem sobrescrever a indicaÃ§Ã£o apresentada pelo formulÃ¡rio. Uma ediÃ§Ã£o superficial no menu nÃ£o garante o valor efetivo.

Os valores acima sÃ£o defaults das imagens, nÃ£o uma leitura da NVRAM atualmente ativa. A sessÃ£o do Windows nÃ£o estÃ¡ elevada e o firmware nÃ£o foi interrogado via EFI Shell, entÃ£o os valores ativos sÃ³ devem ser afirmados depois de ler a flash/NVRAM atual.

## ComparaÃ§Ã£o do cÃ³digo HM570111 Ã— HM570307

As duas imagens possuem 379 mÃ³dulos UEFI com os mesmos GUIDs. Desses, 351 tÃªm CRC idÃªntico e 28 diferem. Entre os diferentes estÃ£o Setup, NVRAM/defaults, PlatformInitPreMem e SMBIOS.

Os principais mÃ³dulos de VT-d e ACPI sÃ£o idÃªnticos entre as duas imagens:

- `IntelVTdDxe` â€” CRC `35EAE02B`
- `PlatformVTdSampleDxe` â€” CRC `97898A76`
- `IntelVtdSmm` â€” CRC `39C20A8C`
- `IntelVTdPmrPei` â€” CRC `B29BD462`
- `PlatformVTdInfoSamplePei` â€” CRC `5E46DF0C`
- `AcpiTableDxe` â€” CRC `54C626B0`
- `AdvancedAcpiDxe` â€” CRC `8CB7D604`

Isso indica que a HM570307 nÃ£o traz uma correÃ§Ã£o clara do nÃºcleo VT-d/ACPI; a diferenÃ§a mais evidente Ã© de configuraÃ§Ã£o/defaults e alguns mÃ³dulos de inicializaÃ§Ã£o da plataforma.

## ACPI entregue ao Windows em runtime

Todas as 28 tabelas ACPI capturadas passaram no checksum de 8 bits. NÃ£o hÃ¡ sinal de corrupÃ§Ã£o simples.

### DMAR/VT-d

A tabela DMAR tem 80 bytes, revisÃ£o 2, e informa:

- largura de endereÃ§o host `0x26` (39 bits);
- flags `0x05`: interrupt remapping disponÃ­vel, X2APIC opt-out desmarcado e DMA Control Platform Opt-In marcado;
- um DRHD `Include All` no endereÃ§o `0xFED91000`;
- escopos para IOAPIC ID 2 e HPET;
- nenhuma estrutura RMRR ou ATSR.

Ela Ã© mÃ­nima, porÃ©m internamente coerente para a mÃ¡quina atual, que usa somente a RX 7800 XT e tem a iGPU desativada. O Windows reporta `AvailableSecurityProperties = 1,3,5,6,7,8`, incluindo suporte ao hipervisor, proteÃ§Ã£o DMA, MBEC e virtualizaÃ§Ã£o de APIC. Isso reduz a probabilidade de a DMAR ser inteiramente invÃ¡lida.

### MADT/APIC â€” inconsistÃªncia concreta

A MADT anuncia 16 processadores Local APIC habilitados:

- ACPI Processor UID: `0..15`
- Local APIC IDs: `0,2,4,6,8,10,12,14,1,3,5,7,9,11,13,15`

A ordem de APIC IDs Ã© normal para listar primeiro um thread de cada nÃºcleo e depois os siblings. O problema estÃ¡ nos 16 registros Local APIC NMI:

- NMI Processor UID: `1..16`
- LINT: `1`

Assim, o processador ativo de UID `0` nÃ£o recebe associaÃ§Ã£o NMI e o registro final aponta para UID `16`, que nÃ£o estÃ¡ habilitado na MADT. O DSDT contÃ©m um template genÃ©rico PR00..PR23, portanto o objeto PR16 existe, mas nÃ£o representa uma CPU ativa neste boot.

A especificaÃ§Ã£o ACPI exige que o campo do NMI corresponda ao `_UID`/Processor ID do processador; `0xFF` seria o valor para aplicar a todos. A sequÃªncia `1..16` diante de CPUs ativas `0..15` Ã©, portanto, um deslocamento de uma unidade no firmware.

O CpuSsdt tambÃ©m contÃ©m um erro de cÃ³pia em PR16: calcula `PF16` usando `PF15` no operando esquerdo. PR16 estÃ¡ inativo nesta CPU de 16 threads, entÃ£o esse segundo defeito provavelmente nÃ£o participa do boot atual, mas mostra baixa qualidade na geraÃ§Ã£o das tabelas de CPU.

## Comportamento observado no Windows

- VT-x, SLAT, proteÃ§Ã£o DMA, MBEC e APIC virtualization sÃ£o detectados como disponÃ­veis.
- VBS e os serviÃ§os de seguranÃ§a virtualizada estÃ£o desativados no boot funcional.
- NÃ£o hÃ¡ eventos do provedor `Microsoft-Windows-Hyper-V-Hypervisor` registrados para a falha.
- NÃ£o existe minidump/MEMORY.DMP correspondente.
- Os resets registrados tÃªm `BugcheckCode = 0` e `BootAppStatus = 0`.

Isso Ã© compatÃ­vel com travamento/reset muito cedo, antes de o kernel registrar um bugcheck completo. NÃ£o prova que a MADT seja a causa, mas torna firmware/topologia/entrada no hipervisor mais plausÃ­vel que um driver comum carregado posteriormente.

## â€œDrivers de 1960â€

Os binÃ¡rios locais `hvloader.dll`, `hvix64.exe`, `hvax64.exe`, `hvcrash.sys`, `hvservice.sys` e `hvsocket.sys` sÃ£o versÃµes atuais da sÃ©rie Windows `10.0.26100.x` e tÃªm assinatura Microsoft.

Datas absurdas mostradas por certas ferramentas ao ler o campo PE/COFF nÃ£o representam necessariamente a data real do arquivo. Em builds determinÃ­sticos/reprodutÃ­veis do Windows, o campo pode ser derivado de um hash. Esta pista nÃ£o indica, por si sÃ³, driver antigo ou corrompido.

## Dump integral da BIOS em execuÃ§Ã£o

O FPT 15.0.20.1419 identificou o chip SPI fÃ­sico como Winbond `EF4018`, 16 MiB, com Flash Descriptor vÃ¡lido. Foram realizadas trÃªs leituras integrais consecutivas:

| Arquivo | Tamanho | SHA-256 |
|---|---:|---|
| `polestar_full_1.bin` | 16.777.216 | `68E9A8113DDDA6E192AA72417E69BD83A3E37DC10D4F1421F0D3B282E49231BD` |
| `polestar_full_2.bin` | 16.777.216 | `68E9A8113DDDA6E192AA72417E69BD83A3E37DC10D4F1421F0D3B282E49231BD` |
| `polestar_full_3.bin` | 16.777.216 | `68E9A8113DDDA6E192AA72417E69BD83A3E37DC10D4F1421F0D3B282E49231BD` |

As trÃªs leituras sÃ£o idÃªnticas. O dump e o log do FPT foram preservados em `firmware/manifests/runtime-2026-08-24/`.

ComparaÃ§Ã£o com HM570111:

- Descriptor: byte por byte idÃªntico;
- cÃ³digo BIOS de `0x560000` atÃ© `0xFFFFFF`: byte por byte idÃªntico;
- diferenÃ§as BIOS restritas a `0x50008F..0x55FFFF`, que contÃ©m NVRAM e seu espelho;
- diferenÃ§as CSME restritas aos dados persistentes internos `0x1FA000..0x278307`.

Logo, a BIOS executÃ¡vel instalada Ã© essencialmente a HM570111; o hash integral diferente decorre de NVRAM e estado persistente legÃ­timo da placa.

## Valores ativos extraÃ­dos do NVRAM

O UEFIExtract A75 revelou duas cÃ³pias AMI NVAR em `0x500078` e `0x530078`. As variÃ¡veis relevantes tÃªm o mesmo SHA-256 nos dois espelhos e os valores ativos sÃ£o:

| Ajuste | VarStore/offset | Valor ativo |
|---|---:|---:|
| Intel VMX | `CpuSetup + 0xB9` | `1` |
| VT-d global | `SaSetup + 0x87` | `1` |
| X2APIC Opt Out | `SaSetup + 0x91` | `0` |
| DMA Control Guarantee | `SaSetup + 0x92` | `1` |
| IGD/IPU/IOP/ITBT VT-d | `SaSetup + 0x93..0x96` | `1` |
| MSI/FADT | `Setup + 0x6E8` | `1` |
| IOMMU preboot | `Setup + 0x8D3` | `0` |
| IOAPIC IRQ 24â€“119 | `PchSetup + 0x5FF` | `1` |
| CFG Lock | `CpuSetup + 0x43` | `0` |

Isso confirma diretamente que VMX e VT-d estÃ£o ligados. A falha nÃ£o Ã© ausÃªncia de virtualizaÃ§Ã£o; ocorre quando o hipervisor Microsoft assume a topologia e o modelo de interrupÃ§Ãµes da plataforma.

## Origem exata do erro MADT

A MADT estÃ¡ embutida como a segunda seÃ§Ã£o Raw do arquivo UEFI Freeform GUID `7E374E25-8E01-4FEE-87F2-390C23C606CD`.

O template reserva 16 entradas Processor Local APIC com:

- Processor UID `1..16`;
- APIC ID `0xFF`;
- flags desativadas.

Durante o boot, o firmware atualiza essas entradas para:

- Processor UID `0..15`;
- APIC IDs reais `0,2,4,6,8,10,12,14,1,3,5,7,9,11,13,15`;
- flags habilitadas.

PorÃ©m, as 16 entradas Local APIC NMI do mesmo template permanecem inalteradas em `1..16`. A transformaÃ§Ã£o de boot, portanto, corrige a base das entradas de processador, mas esquece as entradas NMI. O resultado entregue ao Windows associa NMI aos UIDs `1..16`, deixa a CPU ativa UID `0` sem NMI e aponta a Ãºltima entrada para a CPU inexistente UID `16`.

A cadeia defeituosa de 96 bytes aparece exatamente nas trÃªs imagens fornecidas:

- HM570111;
- HM570307;
- BIOSATUALIZADA.

Isso explica por que trocar entre essas versÃµes nÃ£o corrige o Hyper-V e Ã© coerente com o problema ocorrer em instalaÃ§Ãµes limpas e em vÃ¡rias unidades da placa.

## Por que Linux pode funcionar

O cÃ³digo x86 atual do Linux em `arch/x86/kernel/acpi/boot.c`, funÃ§Ã£o `acpi_parse_lapic_nmi`, valida o tamanho da entrada e apenas avisa se o LINT nÃ£o for 1. Ele nÃ£o valida nem usa o Processor UID da entrada Local APIC NMI. Assim, o Linux pode ignorar na prÃ¡tica o deslocamento `1..16` e continuar inicializando KVM.

A especificaÃ§Ã£o ACPI exige que o UID corresponda ao processador descrito na MADT/namespace; `0xFF` Ã© o valor global para todos os processadores. A Microsoft documenta que o Windows usa a MADT para descrever o modelo de interrupÃ§Ãµes da plataforma. O Hyper-V assumir APIC/interrupt remapping antes do kernel normal torna a falha precoce coerente com essa tabela invÃ¡lida.

Fontes:

- [ACPI 6.6 â€” Local APIC NMI](https://uefi.org/specs/ACPI/6.6/05_ACPI_Software_Programming_Model.html)
- [Linux x86 ACPI boot parser](https://github.com/torvalds/linux/blob/master/arch/x86/kernel/acpi/boot.c)
- [Microsoft â€” ACPI System Description Tables](https://learn.microsoft.com/en-us/windows-hardware/drivers/bringup/acpi-system-description-tables)
- [Microsoft â€” Hyper-V Architecture](https://learn.microsoft.com/en-us/windows-server/virtualization/hyper-v/architecture)

## Patch mÃ­nimo construÃ­do

O patch modifica somente os 16 bytes de Processor UID das entradas Local APIC NMI no template:

```text
01,02,03,04,05,06,07,08,09,0A,0B,0C,0D,0E,0F,10
                         â†“
00,01,02,03,04,05,06,07,08,09,0A,0B,0C,0D,0E,0F
```

Foi construÃ­do um candidato layout-preserved diretamente sobre o dump validado:

`firmware/patches/candidates/polestar-hyperv-madt-nmi-zero-based-layout-preserved.bin`

SHA-256:

`4F99E06399972E31D7D86383D8B81E451C7F75A5D5A00DB8CD8A34AFA25E8E73`

MÃ©todo:

1. validar tamanho e SHA-256 do dump original;
2. validar offset, tamanho e SHA-256 do payload LZMA;
3. descomprimir os 12.320.784 bytes;
4. exigir uma Ãºnica ocorrÃªncia da cadeia NMI no offset `0xA571B4`;
5. alterar exatamente os 16 offsets de UID;
6. recomprimir com `LzmaCompress.exe` oficial do TianoCore, dicionÃ¡rio de 16 MiB;
7. preencher os 40 bytes restantes com `FF`, preservando todos os cabeÃ§alhos, tamanhos e offsets;
8. reabrir a imagem com UEFIExtract A75.

ValidaÃ§Ã£o lÃ³gica:

- tamanho final: 16.777.216 bytes;
- Descriptor: idÃªntico;
- CSME: idÃªntico;
- NVRAM e seus dois espelhos: idÃªnticos;
- 1.949 elementos folha antes e depois;
- exatamente um elemento folha diferente: a MADT de 300 bytes;
- a MADT corrigida contÃ©m NMI UIDs `0..15`;
- nenhum mÃ³dulo executÃ¡vel, microcode, tabela DMAR, DSDT/SSDT ou pad-file foi alterado;
- o parser moderno concluiu com sucesso;
- uma segunda construÃ§Ã£o independente produziu exatamente o mesmo SHA-256;
- o diff dos relatÃ³rios estruturais contÃ©m somente os CRCs encadeados da MADT, do arquivo Freeform e de seus contÃªineres pais;
- as entradas NVAR jÃ¡ marcadas como invÃ¡lidas/obsoletas pelo parser sÃ£o idÃªnticas no original e no candidato.

Uma MADT runtime prevista, com os mesmos APIC IDs observados e UIDs NMI corrigidos, passa no checksum ACPI e nÃ£o possui CPU sem NMI nem NMI apontando para CPU inexistente.

## Caminho real de inicializaÃ§Ã£o do hipervisor Microsoft

O componente que toma controle do processador nÃ£o Ã© um driver `.sys`. O caminho relevante Ã©:

```text
UEFI -> bootmgfw.efi -> winload.efi -> hvloader.dll -> hvix64.exe -> partiÃ§Ã£o raiz do Windows
```

`hvix64.exe` Ã© a imagem Intel do hipervisor. `vmbus.sys`, `vid.sys`, `hvservice.sys`, drivers sintÃ©ticos e drivers fÃ­sicos pertencem Ã  partiÃ§Ã£o raiz e sÃ³ se tornam relevantes depois que o hipervisor jÃ¡ foi lanÃ§ado. A prÃ³pria arquitetura publicada pela Microsoft coloca o hipervisor abaixo da partiÃ§Ã£o raiz e o VMBus dentro da pilha de virtualizaÃ§Ã£o dessa partiÃ§Ã£o.

Estado local dos componentes principais:

| Componente | VersÃ£o apresentada | SHA-256 | Assinatura |
|---|---|---|---|
| `winload.efi` | `10.0.26100.8875` | `5B36477FCF3F235C57756C929009186672012B26B164B9E12440CE6A427A3575` | Microsoft vÃ¡lida |
| `hvloader.dll` | `10.0.26100.8875` | `BEC3D62260239D869D3DE684D2CFAB1D7FF762A1927456E934DDAC15522AEC09` | Microsoft vÃ¡lida |
| `hvix64.exe` | `10.0.26100.9168` | `BCB0FC2D234E2A9D84577C8CFADA7E8D47E02BD7B55817BCCDCBF4FB789D8D21` | Microsoft vÃ¡lida |
| `ntoskrnl.exe` | `10.0.26100.9168` | `13AA072103656881BAB86C09AC0F8362265783BBFB428E85FF060E6018EC2488` | Microsoft vÃ¡lida |

O diretÃ³rio WinSxS do componente `10.0.26100.9168` contÃ©m `hvloader.dll` e `hvix64.exe` com exatamente os mesmos hashes instalados em System32. Portanto, a diferenÃ§a visual `8875/9168` nÃ£o Ã© evidÃªncia de mistura de arquivos: o servicing store os trata como o mesmo conjunto 9168.

O WinSxS ainda preserva o conjunto anterior `26100.8875`. A inspeÃ§Ã£o comparativa mostra que tanto 8875 quanto 9168 jÃ¡ contÃªm as rotas `MinimalLoop` de APIC, diagnÃ³stico de FMS e a opÃ§Ã£o de desabilitar MBEC. Isso nÃ£o exclui regressÃµes em versÃµes mais antigas do Windows, mas nÃ£o hÃ¡ sinal de que esses caminhos tenham surgido apenas no update 9168.

ServiÃ§os relacionados:

- `vmbus.sys`: `Start=0`, System Bus Extender;
- `vid.sys`: `Start=1`;
- `hvservice.sys`: `Start=3`;
- `netvsc`, `hyperkbd`, `hypervideo` e `vmgid`: `Start=3`;
- `hvcrash.sys`: `Start=4`, desativado.

Mesmo `vmbus.sys`, apesar de marcado boot-start, sÃ³ pode executar como driver da partiÃ§Ã£o raiz. Uma reinicializaÃ§Ã£o dentro do lanÃ§amento de `hvix64.exe`, antes de bugcheck/eventos, nÃ£o pode ser causada por `netvsc`, `vid`, `hvservice` ou outro driver normal que ainda nÃ£o recebeu execuÃ§Ã£o. Isso responde diretamente Ã  hipÃ³tese do â€œdriver especÃ­ficoâ€: existe uma pilha de drivers Hyper-V, mas o binÃ¡rio que pode reiniciar a mÃ¡quina nessa fase Ã© o prÃ³prio hipervisor, carregado por `hvloader.dll`, nÃ£o um `.sys` substituÃ­vel.

Fontes:

- [Microsoft â€” Hyper-V Architecture](https://learn.microsoft.com/en-us/windows-server/virtualization/hyper-v/architecture)
- [Microsoft â€” requisitos de hardware do Hyper-V](https://learn.microsoft.com/en-us/windows-server/virtualization/hyper-v/host-hardware-requirements)

## Engenharia reversa de `hvloader.dll` e `hvix64.exe`

Foi criado `archive/experiments/legacy-scripts/inspect_hyperv_pe.py` para inspecionar PE, imports, identidade PDB, strings e instruÃ§Ãµes privilegiadas. Os PDBs pÃºblicos correspondentes nÃ£o estavam disponÃ­veis no servidor pÃºblico de sÃ­mbolos da Microsoft, entÃ£o nenhuma funÃ§Ã£o interna sem sÃ­mbolo foi nomeada como se estivesse confirmada.

Identidades PDB:

- `hvloader.pdb/F77B5B3673248C477F15B2447194D8A61`;
- `hvix64.pdb/BDAA486DC5225639DF5DC7356376DCE31`.

O `hvloader.dll` importa diretamente de `winload`:

- `BlUtlGetAcpiTable` e `BlUtlPopulateAcpiTableCache`;
- `BlGetProcessorApicIds` e `BlGetLogicalProcessorCount`;
- `OslLoadMicrocodeUpdate`;
- `BlArchGetCpuVendor`.

Ele contÃ©m diagnÃ³sticos especÃ­ficos para inconsistÃªncias MADT/DMAR, inclusive IOAPIC da DMAR ausente na MADT, IOAPIC conflitante, RID sob mais de uma IOMMU e DRHD `Include-All` malformado. A DMAR desta placa passa as verificaÃ§Ãµes estruturais visÃ­veis: IOAPIC ID 2 coincide com a MADT, hÃ¡ apenas um DRHD Include-All e a largura de 39 bits coincide com o CPUID.

### ConfiguraÃ§Ã£o Microsoft anterior ao kernel: `IgnoreMemPart`

A chave local `HKLM\SYSTEM\CurrentControlSet\Control\Hypervisor` contÃ©m apenas `IgnoreMemPart=1`. Isso nÃ£o Ã© um driver de terceiros. A anÃ¡lise do `hvloader.dll` instalado localizou a string em VA `0x180020A30`, referenciada pela funÃ§Ã£o em `0x18000AB64`, chamada por `HvlLoadHypervisor`, `HvlPreloadHypervisor` e `HvlExchangeDispatchInterface`. O fluxo chama `OslGetControlSubkey("Hypervisor")`, lÃª o DWORD e, se ele for nÃ£o zero no ambiente normal de boot, pula `BlMmOpenPartition("\\KernelObjects\\MemoryPartitionHypervisorMetadata")`. Depois ele consulta tambÃ©m `MetadataMemoryPartition`.

Portanto, o valor altera de fato a preparaÃ§Ã£o de memÃ³ria do hipervisor antes do kernel. NÃ£o hÃ¡ documentaÃ§Ã£o pÃºblica da Microsoft que defina seu contrato, e o valor `1` pode ser uma mitigaÃ§Ã£o intencional do Windows. Ele foi classificado como hipÃ³tese secundÃ¡ria: somente se a matriz BCD inteira falhar, testar `0` isoladamente e restaurar `1` em seguida. Foram criados scripts reversÃ­veis com backup integral da chave e `dry-run` padrÃ£o; nenhum valor foi alterado durante esta anÃ¡lise.

InstruÃ§Ãµes encontradas no cÃ³digo executÃ¡vel:

| BinÃ¡rio | `CPUID` | `RDMSR` | `WRMSR` | `VMXON` | ObservaÃ§Ã£o |
|---|---:|---:|---:|---:|---|
| `hvloader.dll` | 30 | 28 | 14 | 1 | faz uma tentativa real de `VMXON` em RVA `0x1C705` e testa o resultado |
| `hvix64.exe` | 94 | 252 | 296 | 1 | inicializa VMCS, EPT, VPID, APIC e processadores auxiliares |

Strings de diagnÃ³stico presentes no `hvix64.exe` incluem:

- processadores que nÃ£o respondem e falha ao adicionar processador lÃ³gico;
- `AP microcode update status`;
- machine check antes de a raiz estar pronta, seguido de reboot;
- falha de carregamento de MSR na entrada VM;
- `MinimalLoop` reiniciando por acesso APIC, INIT ou violaÃ§Ã£o EPT;
- broadcast NMI vindo do IOAPIC;
- falhas de IOMMU/interrupt remapping;
- `Processor FMS is unknown! MSRs accesses may fault.`.

Essas mensagens provam que hÃ¡ caminhos internos de reinicializaÃ§Ã£o sem bugcheck normal exatamente nas Ã¡reas suspeitas, mas **nÃ£o provam qual mensagem ocorreu nesta mÃ¡quina**. A string de FMS, em especial, nÃ£o possui referÃªncia direta recuperada. HÃ¡ uma sequÃªncia ampla de valores family/model que inclui `0x068D`, mas sem referÃªncia de cÃ³digo ela nÃ£o foi tratada como whitelist. Portanto, nÃ£o hÃ¡ base para afirmar que todo Tiger Lake-H model 8D seja rejeitado; a diferenÃ§a de stepping ainda pode afetar MSRs, mas nÃ£o Ã© uma rejeiÃ§Ã£o simples confirmada.

## Tiger Lake ES: stepping e microcode

O CPUID atual Ã© `000806D0`: family 6, model 8D, stepping 0. A especificaÃ§Ã£o de produÃ§Ã£o da Intel lista Tiger Lake H81 como `000806D1`; ela nÃ£o lista `806D0`. Isso confirma que o processador Ã© um stepping prÃ©-produÃ§Ã£o, nÃ£o apenas um nome genÃ©rico estranho no SMBIOS.

O repositÃ³rio pÃºblico atual de microcode da Intel contÃ©m `06-8d-01` para o stepping de produÃ§Ã£o e nÃ£o contÃ©m `06-8d-00`. O microcode `0x50` do D0 nesta BIOS Ã©, portanto, um payload ES/OEM nÃ£o publicado no pacote pÃºblico. O fato de uma revisÃ£o histÃ³rica D1 tambÃ©m ter nÃºmero `0x50` nÃ£o torna os payloads equivalentes: a assinatura completa inclui stepping e platform ID.

Fontes:

- [Intel â€” 11th Generation Core Processor Specification Update](https://cdrdv2-public.intel.com/631123/631123_032.pdf)
- [Intel â€” pacote pÃºblico de microcode](https://github.com/intel/Intel-Linux-Processor-Microcode-Data-Files)

## CPUID: topologia coerente e uma combinaÃ§Ã£o AVX-512 incoerente

O script `archive/experiments/legacy-scripts/dump_cpuid_windows.py` executou CPUID preso sucessivamente a todos os 16 processadores lÃ³gicos. Depois de mascarar apenas o APIC ID esperado, os 16 LPs produziram o mesmo fingerprint de recursos. A topologia da folha `0xB` tambÃ©m Ã© coerente: 2 threads por nÃºcleo, 16 threads por pacote, total 8C/16T. Isso reduz a hipÃ³tese de um Ãºnico nÃºcleo anunciar CPUID diferente.

HÃ¡, porÃ©m, uma inconsistÃªncia objetiva:

| Campo | Valor |
|---|---|
| `CPUID.7.0.EBX` | `0x239CA7EB` |
| `CPUID.7.0.EDX` | `0xFC100510` |
| `CPUID.7.0.EBX[16]` AVX512F | `0` |
| `CPUID.7.0.EBX[31]` AVX512VL | `0` |
| `CPUID.7.0.EDX[8]` AVX512_VP2INTERSECT | `1` |
| `CPUID.0xD.0.EAX` | `0x00000207` |
| estados XCR0 5, 6 e 7 de AVX-512 | todos `0` |

A Intel define EDX bit 8 como `AVX512_VP2INTERSECT`; as formas de 128/256 bits exigem tambÃ©m AVX512VL e as formas de 512 bits exigem AVX512F. Nesta mÃ¡quina nenhuma base estÃ¡ exposta e nem existem os estados opmask/ZMM em XCR0. O recurso estÃ¡, portanto, Ã³rfÃ£o e inutilizÃ¡vel.

Isso coincide com o NVRAM ativo:

- `CpuSetup+0x229 = 0`: AVX habilitado;
- `CpuSetup+0x22A = 1`: opÃ§Ã£o AMI `AVX3` desabilitada;
- o IFR declara `AVX3 Enabled=0` como default, mas a NVRAM atual contÃ©m `1`.

A hipÃ³tese mais simples Ã© que o cÃ³digo de setup oculte AVX-512 de modo incompleto no ES e esqueÃ§a o bit VP2INTERSECT. Um hipervisor que salva, normaliza e valida CPUID/XSTATE para todos os LPs pode encontrar essa combinaÃ§Ã£o antes do kernel. O teste correto nÃ£o Ã© editar `hvix64.exe`: Ã© habilitar temporariamente `AVX3` na BIOS, repetir o dump CPUID e verificar se AVX512F/VL, VP2INTERSECT e XSTATE 5â€“7 passam a aparecer juntos. Se todos desaparecerem juntos com outra configuraÃ§Ã£o, tambÃ©m Ã© coerente.

Uma checagem das dependÃªncias vizinhas nÃ£o encontrou outra combinaÃ§Ã£o quebrada: PKU estÃ¡ acompanhado pelo estado PKRU em XCR0 bit 9; CET Shadow Stack e IBT estÃ£o anunciados e os estados CET de usuÃ¡rio/supervisor aparecem em `CPUID.0xD.1:ECX` bits 11 e 12. Assim, a inconsistÃªncia observada nÃ£o Ã© um falso positivo causado por interpretar todo estado supervisor como ausente em `CPUID.0xD.0`; ela permanece especÃ­fica Ã  mÃ¡scara AVX-512/VP2INTERSECT.

Fonte: [Intel â€” Architecture Instruction Set Extensions Programming Reference](https://cdrdv2-public.intel.com/843860/architecture-instruction-set-extensions-programming-reference-dec-24.pdf).

## Segunda passagem pelas tabelas de plataforma

- DMAR: HAW 39 bits igual ao CPUID; IOAPIC ID 2 igual Ã  MADT; DRHD Include-All em `FED91000`; nenhuma duplicidade de RID visÃ­vel.
- WSMT: flags `0x7`, com buffers fixos, proteÃ§Ã£o de ponteiros aninhados e proteÃ§Ã£o de recursos do sistema.
- FADT: revisÃ£o 6, checksum vÃ¡lido, reset por `0xCF9`, MSI suportado; nÃ£o Ã© Hardware Reduced e nÃ£o anuncia Low Power S0 Idle.
- MCFG: checksum vÃ¡lido, segmento 0, janela `C0000000`, buses 0â€“7. O alcance Ã© pequeno, mas nÃ£o hÃ¡ evidÃªncia de que participe do reset no primeiro `VMXON`.
- NÃ£o hÃ¡ SRAT/SLIT; para um pacote e um nÃ³ NUMA isso nÃ£o Ã© um erro.

Esses resultados nÃ£o absolvem VT-d: a transiÃ§Ã£o de interrupt remapping ainda Ã© cÃ³digo ativo do hipervisor. Eles apenas eliminam os erros DMAR mais Ã³bvios que o prÃ³prio `hvloader` diagnostica.

## Matriz de diagnÃ³stico criada, ainda nÃ£o aplicada

O protocolo completo estÃ¡ em `docs/hyperv-test-matrix.md`. O script `archive/experiments/legacy-scripts/prepare-hyperv-diagnostic-matrix.ps1` Ã© `dry-run` por padrÃ£o e cria, somente com `-Apply` elevado:

1. baseline com hipervisor ligado e VSM desligado;
2. IOMMU desabilitada para o hipervisor;
3. x2APIC desabilitado e APIC legado forÃ§ado;
4. apenas um processador lÃ³gico iniciado pelo hipervisor;
5. combinaÃ§Ã£o mÃ­nima de um CPU + xAPIC legado + IOMMU desligada;
6. MBEC por hardware desabilitado pelo load option encontrado no `hvloader`.
7. XSAVE desabilitado para isolar a combinaÃ§Ã£o CPUID/XSTATE incoerente.
8. captura de `ntbtlog.txt`, nomes de drivers na tela e bugcheck sem reinÃ­cio automÃ¡tico;
9. vAPIC desabilitado pelo elemento BCD `hypervisorusevapic` (`0x26000116`);
10. interrupÃ§Ãµes postadas desabilitadas;
11. virtualizaÃ§Ã£o de IPI desabilitada;
12. SLAT/EPT desabilitado;
13. destino fÃ­sico do APIC forÃ§ado;
14. scheduler clÃ¡ssico do hipervisor;
15. live handoff da IOMMU desabilitado;
16. IOMMU escalÃ¡vel desabilitada;
17. fonte de tempo de referÃªncia forÃ§ada para ACPI PM Timer;
18. sincronizaÃ§Ã£o de TSC forÃ§ada.

O BCD Ã© exportado antes, `{current}` permanece com Hyper-V desligado e como padrÃ£o, o menu dura 15 segundos e nenhuma entrada perigosa Ã© agendada automaticamente. Um segundo script remove apenas os GUIDs gravados no manifesto. As opÃ§Ãµes pÃºblicas `hypervisornumproc`, `hypervisoriommupolicy`, `x2apicpolicy`, `uselegacyapicmode` e `xsavedisable` estÃ£o documentadas pela Microsoft: [BCDEdit /set](https://learn.microsoft.com/en-us/windows-hardware/drivers/devtest/bcdedit--set).

Como eixo separado da matriz, os scripts `prepare-hyperv-ignoremempart-test.ps1` e `restore-hyperv-ignoremempart-test.ps1` permitem comparar o valor local `IgnoreMemPart=1` com `0`, sempre preservando um `.reg` e um manifesto. Esse teste Ã© global, nÃ£o pertence a uma entrada BCD, e fica deliberadamente por Ãºltimo por nÃ£o haver contrato pÃºblico para o valor.

## Esgotamento adicional: opÃ§Ãµes reais do hipervisor

A anÃ¡lise estÃ¡tica do `hvloader.dll` instalado confirmou que `hypervisorloadoptions` Ã© lido do elemento BCD `0x22000117` e tambÃ©m da string de Registro `Hypervisorloadoptions`. O conteÃºdo Ã© normalizado e repassado ao hipervisor. O mesmo conjunto de tokens aparece em `hvloader.dll` e `hvix64.exe`, incluindo:

- `DISABLEPOSTEDINTERRUPTS`;
- `DISABLEIPIVIRTUALIZATION`;
- `DISABLESCALABLEIOMMU`;
- `IOMMULIVEHANDOFF=DISABLE`;
- `DISABLEHARDWAREMBEC`;
- `REFERENCETIMESOURCE=HPET` e `REFERENCETIMESOURCE=PMTIMER`;
- `SYNCTSC`.

Os dois primeiros sÃ£o particularmente relevantes porque a MADT defeituosa, a enumeraÃ§Ã£o APIC intercalada e o reset sem bugcheck convergem no caminho APIC/VMX. `IOMMULIVEHANDOFF=DISABLE` Ã© consumido diretamente pelo `hvloader`; os demais tokens sÃ£o opÃ§Ãµes internas transferidas ao `hvix64`. Eles sÃ£o experimentais e servem para diagnÃ³stico, nÃ£o como configuraÃ§Ãµes permanentes sem resultado positivo.

O IFR da BIOS nÃ£o oferece controles para vAPIC, posted interrupts ou IPI virtualization. Ele expÃµe somente VMX, VT-d, `X2APIC Opt Out` e `Control Iommu Pre-boot Behavior`. Este Ãºltimo jÃ¡ estÃ¡ em `0` (IOMMU desabilitada no ambiente prÃ©-boot), portanto `IOMMULIVEHANDOFF=DISABLE` tem prioridade baixa; vAPIC/posted interrupts/IPI nÃ£o possuem equivalente visÃ­vel no Setup e precisam ser isolados pelo BCD.

`HypervisorUseVapic` tambÃ©m foi confirmado em cÃ³digo: primeiro o loader tenta o elemento BCD booleano `0x26000116`, depois usa o DWORD de mesmo nome no Registro como fallback. A prÃ³pria documentaÃ§Ã£o Microsoft de validaÃ§Ã£o BCD do BitLocker mapeia esse identificador para o nome amigÃ¡vel `hypervisorusevapic`: [BCD settings and BitLocker](https://learn.microsoft.com/en-us/windows/security/operating-system-security/data-protection/bitlocker/bcd-settings-and-bitlocker).

## TemporizaÃ§Ã£o: estÃ¡tica coerente, teste dinÃ¢mico ainda possÃ­vel

O CPUID atual informa `Invariant TSC=1`. A folha `0x15` contÃ©m denominador 2, numerador 162 e cristal de 38,4 MHz, resultando em TSC de 3.110.400.000 Hz. A folha `0x16` informa base de 3.100 MHz, diferenÃ§a de apenas 0,3355%. A HPET aponta para `FED00000`, a FADT fornece PM Timer de 24 bits em `0x1808` e ambas tÃªm checksum vÃ¡lido.

NÃ£o hÃ¡, portanto, inconsistÃªncia estÃ¡tica de relÃ³gio semelhante Ã  encontrada em AVX-512. Ainda pode existir skew entre LPs durante o bring-up; o prÃ³prio `hvix64` contÃ©m mensagens `TscSync Failed` e `TscSync Unstable`. Por isso `PMTIMER` e `SYNCTSC` permanecem na Ãºltima onda da matriz, depois de APIC/VMX/IOMMU.

## Drivers Microsoft e atualizaÃ§Ã£o de microcode

Foi inventariada a pilha Microsoft relevante. `vmbus.sys`, `storvsc.sys` e `vpci.sys` sÃ£o `BOOT_START`; `Vid.sys` Ã© `SYSTEM_START`; `intelppm.sys` Ã© PnP/demand start. Todos os arquivos verificados possuem assinatura Microsoft vÃ¡lida. O inventÃ¡rio com versÃ£o, hash e grupo estÃ¡ em `evidence/hyperv/hyperv-root-driver-inventory.json`.

HÃ¡ vÃ¡rios eventos Kernel-Power 41, todos com `BugcheckCode=0`, `WHEABootErrorCount=0` e sem minidump correspondente. Isso nÃ£o prova sozinho a fase exata, mas Ã© incompatÃ­vel com a hipÃ³tese comum de um `.sys` da partiÃ§Ã£o raiz gerar um BSOD registrado. A entrada `HV 08 CAPTURA BOOTLOG` passa a ser a prova operacional: se o horÃ¡rio de `C:\Windows\ntbtlog.txt` nÃ£o mudar apÃ³s o reset, o kernel nÃ£o chegou Ã  fase de logar drivers; se mudar, o Ãºltimo `Loaded driver` delimita a fase.

`mcupdate_GenuineIntel.dll` tambÃ©m Ã© assinado pela Microsoft, mas o Registro de hardware mostra `Update Revision=0x50` e `Previous Update Revision=0x50`. Assim, o Windows nÃ£o substituiu o payload da BIOS nesta inicializaÃ§Ã£o. O dump contÃ©m microcode D0 `0x50`, de 17/12/2020, em todas as variantes fornecidas; nÃ£o existe um D0 mais novo entre elas. Os drivers de processador exibirem datas histÃ³ricas de INF e binÃ¡rios do hipervisor exibirem timestamps PE incomuns nÃ£o significa que sejam cÃ³digo de 1960/2006/2009.

`sfc /verifyonly` foi tentado, mas a sessÃ£o atual nÃ£o Ã© elevada e o utilitÃ¡rio recusou a execuÃ§Ã£o antes de verificar arquivos. Isso nÃ£o Ã© um resultado de corrupÃ§Ã£o. Se a captura `HV 08` provar que o kernel chegou a carregar drivers, executar depois, em terminal Administrador, `sfc /verifyonly` e `DISM /Online /Cleanup-Image /ScanHealth`; se nÃ£o houver `ntbtlog`, essas verificaÃ§Ãµes nÃ£o explicam o reset prÃ©-kernel.

## ComparaÃ§Ã£o mÃ³dulo a mÃ³dulo das BIOS

O comparador `archive/experiments/legacy-scripts/compare_uefi_code_modules.py` agrupa PE32/TE pelo nome do mÃ³dulo, ignorando Ã­ndices de caminho que mudam com NVRAM. Resultados gravados em JSON:

- runtime versus `HM570111`: 309 de 309 mÃ³dulos executÃ¡veis idÃªnticos; zero mudou;
- `HM570111` versus `HM570307`: 17 de 309 mudaram; 292 sÃ£o idÃªnticos;
- `HM570111` versus `BIOSATUALIZADA`: layouts incompatÃ­veis, 309 contra 115 chaves e 334 diferenÃ§as na uniÃ£o.

Entre 111 e 307, o Ãºnico mÃ³dulo alterado que participa claramente do prÃ©-memory platform init Ã© `PlatformInitPreMem` TE, com mesmo tamanho de 42.944 bytes mas hash diferente. As rotas ACPI/DMAR que geram as tabelas permanecem idÃªnticas e ambas as versÃµes apresentam o mesmo erro NMI `1..16`. Transplantar `PlatformInitPreMem` sem conhecer as diferenÃ§as de placa Ã© mais arriscado que o patch de 16 bytes da MADT e nÃ£o possui evidÃªncia causal. `BIOSATUALIZADA` nÃ£o Ã© do mesmo empacotamento/FSP e nÃ£o serve como doadora de mÃ³dulos ou imagem integral.

## Possibilidades restantes, em ordem tÃ©cnica

1. **MADT/AP startup/APIC:** defeito confirmado na tabela e compatÃ­vel com os caminhos `MinimalLoop`, NMI e AP que reiniciam dentro de `hvix64.exe`. Ã‰ o candidato firmware principal.
2. **MÃ¡scara AVX3/CPUID/XSTATE:** segundo defeito confirmado, com teste de BIOS reversÃ­vel e barato antes de flash.
3. **Capacidades VMX/MSRs especÃ­ficas do D0:** Linux/KVM provar VMX/EPT bÃ¡sico nÃ£o garante que todos os controles exigidos pelo Hyper-V sejam idÃªnticos em todos os LPs. O coletor Linux criado lÃª `IA32_VMX_*` em cada CPU.
4. **x2APIC/APIC virtualization fora da MADT:** o Windows reporta APIC virtualization disponÃ­vel, mas a transiÃ§Ã£o ainda pode falhar no ES ou no firmware. A entrada xAPIC legado isola isso.
5. **DMAR/VT-d/interrupt remapping:** a tabela Ã© internamente coerente, mas o caminho de ativaÃ§Ã£o continua testÃ¡vel com IOMMU desligada.
6. **Drivers `.sys` da partiÃ§Ã£o raiz:** probabilidade muito baixa para este sintoma, porque a falha reproduz em instalaÃ§Ã£o limpa e pode ocorrer antes que esses drivers executem.
7. **`IgnoreMemPart=1`:** configuraÃ§Ã£o Microsoft confirmada no caminho de preload e memÃ³ria do hipervisor; plausÃ­vel como desvio especÃ­fico desta instalaÃ§Ã£o, porÃ©m de prioridade baixa e sem documentaÃ§Ã£o pÃºblica. O teste `0` deve ser isolado e revertido.
8. **Compatibilidade por geraÃ§Ã£o do Hyper-V:** o WinSxS atual sÃ³ permite comparar revisÃµes do mesmo ramo 26100, e ambas contÃªm as rotas suspeitas. Se o hardware continuar falhando apÃ³s todos os isoladores, um Windows 10 22H2 ou Windows 11 23H2 oficial em SSD separado pode servir como bisect de versÃ£o. Ele nÃ£o deve substituir nem alterar a instalaÃ§Ã£o atual; se uma geraÃ§Ã£o antiga iniciar, o alvo passa a ser uma diferenÃ§a de validaÃ§Ã£o do `hvix64`, nÃ£o um driver fÃ­sico.

NÃ£o Ã© tecnicamente razoÃ¡vel â€œmascarar D0 como D1â€ por ACPI. Family/model/stepping vÃªm da instruÃ§Ã£o CPUID. Um spoof real exigiria microcode compatÃ­vel ou outra camada de virtualizaÃ§Ã£o anterior ao Hyper-V e poderia induzir o Windows a tocar MSRs/erratas do D1 que nÃ£o existem no D0. As correÃ§Ãµes aceitÃ¡veis sÃ£o, em ordem: ajustar configuraÃ§Ã£o existente, corrigir ACPI/DMAR, e sÃ³ entÃ£o modificar cÃ³digo de firmware com uma diferenÃ§a mÃ­nima e verificÃ¡vel.

## ValidaÃ§Ã£o prÃ©-flash da MADT por OpenCore

Foi montada uma Ã¡rvore OpenCore 1.0.7 que aplica a correÃ§Ã£o somente em memÃ³ria. O patch Ã© limitado Ã  tabela `APIC` de 300 bytes, ao OEM Table ID exato, Ã  sequÃªncia completa dos 16 registros NMI e a uma Ãºnica substituiÃ§Ã£o. A implementaÃ§Ã£o oficial recalcula o checksum apÃ³s uma substituiÃ§Ã£o bem-sucedida.

TambÃ©m foi criado um controle negativo com a mesma configuraÃ§Ã£o e o patch desativado. Assim, um boot positivo pode distinguir a correÃ§Ã£o MADT de um efeito genÃ©rico do OpenCore. Todas as configuraÃ§Ãµes passaram no `ocvalidate`; o instalador foi testado somente em `dry-run` contra a partiÃ§Ã£o `BIOS_BACKUP` e confirmou os hashes dos trÃªs dumps antes de planejar qualquer alteraÃ§Ã£o.

O coletor `dump_acpi_windows.py` usa `GetSystemFirmwareTable` e, no boot atual sem OpenCore, reproduziu exatamente o SHA-256 anterior da MADT e a incompatibilidade CPUs `0..15` / NMIs `1..16`. O protocolo seguro estÃ¡ em `OPENCORE_MADT_TEST.md`. Esse teste deve preceder qualquer gravaÃ§Ã£o da candidata de firmware.

## Estado de confianÃ§a

1. **Defeito estrutural MADT `1..16` versus `0..15`: confirmado.**
2. **Origem no template e transformaÃ§Ã£o incompleta do firmware: confirmada.**
3. **Linux nÃ£o depender desse UID no parser x86: confirmado no cÃ³digo.**
4. **Patch alterar apenas a MADT lÃ³gica: confirmado por extraÃ§Ã£o e hashes.**
5. **CPUID expor VP2INTERSECT sem AVX512F/VL/XSTATE: confirmado nos 16 LPs.**
6. **O reset ocorrer antes dos drivers `.sys` normais: compatÃ­vel com toda a evidÃªncia, ainda sem trace de depuraÃ§Ã£o.**
7. **A MADT ser sozinha a causa do bootloop: hipÃ³tese principal, mas nÃ£o provada; agora hÃ¡ isoladores para distinguir APIC, IOMMU, SMP, MBEC e CPUID.**

A candidata MADT continua vÃ¡lida como experimento mÃ­nimo de firmware, mas nÃ£o deve ser tratada como soluÃ§Ã£o garantida. O prÃ³ximo passo lÃ³gico antes de gravÃ¡-la Ã© testar a opÃ§Ã£o AVX3 e executar a matriz BCD; em paralelo, a coleta VMX/MSR no Linux fecha a principal lacuna que anÃ¡lise estÃ¡tica nÃ£o consegue observar.

Se todos os isoladores falharem, `docs/hyperv-debugging.md` descreve a captura do hipervisor com um segundo PC. A NIC cabeada Realtek `10EC:8168` do alvo estÃ¡ na lista oficial de dispositivos KDNET, mas `kdnet.exe`/WinDbg ainda nÃ£o estÃ£o instalados e nada foi habilitado. Essa captura Ã© o caminho para distinguir definitivamente VM-entry/MSR, AP startup, APIC, IOMMU, EPT e machine check sem inferir pela ausÃªncia de minidump.

## Antes de qualquer gravaÃ§Ã£o

O candidato **nÃ£o deve ser gravado ainda** atÃ© completar estes controles:

1. fazer trÃªs leituras externas com o programador e comparar os hashes entre si;
2. comparar o dump externo com o dump FPT para confirmar acesso integral;
3. identificar fisicamente o chip como 1,8 V ou 3,3 V antes de conectar/gravar;
4. testar a restauraÃ§Ã£o do arquivo original no programador, ao menos atÃ© a etapa de verificaÃ§Ã£o sem erro;
5. preparar a matriz BCD recuperÃ¡vel descrita em `docs/hyperv-test-matrix.md`, mantendo `{current}` com `hypervisorlaunchtype off` como padrÃ£o;
6. apÃ³s gravar, iniciar primeiro com Hyper-V desligado e capturar novamente a MADT; ela deve apresentar NMI UIDs `0..15` e checksum vÃ¡lido;
7. somente depois selecionar a entrada de teste do Hyper-V.

Se o teste falhar, restaurar o dump original `68E9A811...31BD` pelo programador. NÃ£o usar `BIOSATUALIZADA.bin` como imagem integral de recuperaÃ§Ã£o porque seu layout SPI Ã© diferente.
