# Análise aprofundada — Polestar/Interposer HM570

> Documento histórico anterior ao controle A/B/A de MBEC. Para a conclusão e
> o workaround atuais, consulte [`findings.md`](findings.md) e
> [`workaround.md`](workaround.md). A incoerência AVX-512/VP2INTERSECT descrita
> abaixo foi depois resolvida ao habilitar AVX3; ver
> [`avx512-runtime-firmware-diff.md`](avx512-runtime-firmware-diff.md). AVX3
> ainda não foi testado sozinho com MBEC por hardware ativo.

Data da análise: 24/08/2026

## Escopo e segurança

Esta etapa foi inteiramente de leitura e análise. Não houve gravação na SPI, alteração de NVRAM, ativação do Hyper-V, mudança no BCD ou reinicialização.

O sistema em execução identifica a BIOS como `THM570111`, AMI, data SMBIOS 06/08/2023. O processador é um Tiger Lake ES, CPUID `806D0`, 8 núcleos/16 threads, com microcode ativo `0x50`.

A própria página da Erying separa placas `HM5701xx` (imagem 111) de `HM5703xx` (imagem 307) e alerta que gravar a família errada pode causar tela preta. Isso reforça a decisão de nunca usar uma imagem 307/“Lightning” inteira como atalho: qualquer candidata deste trabalho deriva do dump runtime `THM570111` da própria placa. Fonte: [Erying — Polestar 11th Gen HM570](https://www.erying.cc/sys-pd/20.html).

## Imagens analisadas

| Imagem | SHA-256 | Layout principal |
|---|---|---|
| `HM570111.bin` | `16529D3B622D150CB2E2EEDA95347C68A878532D39B8B3D9C1F4084A4CFFCCBE` | ME começa em `0x001000`; BIOS em `0x500000` |
| `HM570307.bin` | `BBB237F0D1FC85BC44B674BB138F6C8AD0646F8D38AF6576F521AEF8FB3EDCF1` | ME começa em `0x001000`; BIOS em `0x500000` |
| `BIOSATUALIZADA.bin` | `AD7ADFC9E82A280445D977104D3226D49E895B1AB5413A45A7324ACA34598F6A` | ME começa em `0x001000`; BIOS em `0x400000` |

Conclusão importante: `BIOSATUALIZADA.bin` não tem o mesmo particionamento das HM570111/HM570307. Ela não deve ser misturada por regiões nem gravada integralmente como se fosse equivalente.

## Descriptor SPI e CSME

Nas três imagens, o Intel Flash Descriptor declara acesso de leitura e escrita do host às regiões Descriptor, BIOS, ME, GbE e PDR. Isso indica um descriptor aberto na imagem. Um bloqueio adicional ainda pode ser aplicado em runtime pelo chipset/firmware.

Chips listados na tabela VSCC do projeto:

- Winbond `W25Q256` (`EF4019`)
- Macronix `MX25L256` (`C22019`)
- Winbond `W25Q128` (`EF4018`)

O código exato escrito no chip físico deve ser lido antes de selecionar o componente no programador.

| Imagem | CSME | Plataforma | Estado | FWUpdate |
|---|---|---|---|---|
| HM570111 | `15.0.35.2039` | TGP/EBG-H stepping B | Configured | No |
| HM570307 | `15.0.21.1503` | TGP/EBG-H stepping A | Initialized | No |
| BIOSATUALIZADA | `15.0.35.1932` | TGP/EBG-H stepping B | Configured | No |

O descriptor aberto e o campo CSME `FWUpdate Support: No` não são contraditórios: o primeiro controla permissões de regiões SPI; o segundo descreve o mecanismo de atualização do firmware CSME. O backup completo via FPT pode funcionar, mas precisa ser validado pelo resultado e pelo hash.

As imagens contêm Startup ACM, mas o analisador não conseguiu encontrar Key Manifest/Boot Policy Manifest válidos; as entradas FIT têm tamanho zero e os ranges AMI protegidos estão preenchidos com `FF`. Isso sugere placeholders ou uma configuração de engenharia, mas não prova sozinho que Boot Guard esteja desativado nos fusíveis.

## Microcode e VMX

As três imagens contêm microcode para CPUID `806D0`, revisão `0x50`, data 17/12/2020. O Windows também está executando a revisão `0x50`.

Portanto, a hipótese de “microcode ausente para o ES” foi refutada. Linux/KVM funcionar e o Windows reportar suporte ao hipervisor também mostram que VMX/EPT não estão simplesmente ausentes.

## Setup/IFR e defaults reais das imagens

O Setup AMI possui menus internos de engenharia e opções ocultas. Nas HM570111 e HM570307:

| Ajuste | VarStore/offset | HM570111 | HM570307 |
|---|---:|---:|---:|
| Intel VMX | `CpuSetup + 0xB9` | `1` | `1` |
| VT-d global | `SaSetup + 0x87` | `1` | `0` |
| X2APIC Opt Out | `SaSetup + 0x91` | `0` | `0` |
| DMA Control Guarantee | `SaSetup + 0x92` | `1` | `1` |
| IGD/IPU/IOP/ITBT VT-d | `SaSetup + 0x93..0x96` | `1` | `1` |
| MSI | `Setup + 0x6E8` | `1` | `1` |
| IOMMU preboot | `Setup + 0x8D3` | `0` | `0` |
| IOAPIC IRQ 24–119 | `PchSetup + 0x5FF` | `1` | `1` |
| CFG Lock | `CpuSetup + 0x43` | `0` | `0` |

Achado relevante: o IFR das duas BIOS marca VT-d como “Enabled, Default”, mas o bloco externo de defaults da HM570307 grava `0`. Logo, os defaults externos podem sobrescrever a indicação apresentada pelo formulário. Uma edição superficial no menu não garante o valor efetivo.

Os valores acima são defaults das imagens, não uma leitura da NVRAM atualmente ativa. A sessão do Windows não está elevada e o firmware não foi interrogado via EFI Shell, então os valores ativos só devem ser afirmados depois de ler a flash/NVRAM atual.

## Comparação do código HM570111 × HM570307

As duas imagens possuem 379 módulos UEFI com os mesmos GUIDs. Desses, 351 têm CRC idêntico e 28 diferem. Entre os diferentes estão Setup, NVRAM/defaults, PlatformInitPreMem e SMBIOS.

Os principais módulos de VT-d e ACPI são idênticos entre as duas imagens:

- `IntelVTdDxe` — CRC `35EAE02B`
- `PlatformVTdSampleDxe` — CRC `97898A76`
- `IntelVtdSmm` — CRC `39C20A8C`
- `IntelVTdPmrPei` — CRC `B29BD462`
- `PlatformVTdInfoSamplePei` — CRC `5E46DF0C`
- `AcpiTableDxe` — CRC `54C626B0`
- `AdvancedAcpiDxe` — CRC `8CB7D604`

Isso indica que a HM570307 não traz uma correção clara do núcleo VT-d/ACPI; a diferença mais evidente é de configuração/defaults e alguns módulos de inicialização da plataforma.

## ACPI entregue ao Windows em runtime

Todas as 28 tabelas ACPI capturadas passaram no checksum de 8 bits. Não há sinal de corrupção simples.

### DMAR/VT-d

A tabela DMAR tem 80 bytes, revisão 2, e informa:

- largura de endereço host `0x26` (39 bits);
- flags `0x05`: interrupt remapping disponível, X2APIC opt-out desmarcado e DMA Control Platform Opt-In marcado;
- um DRHD `Include All` no endereço `0xFED91000`;
- escopos para IOAPIC ID 2 e HPET;
- nenhuma estrutura RMRR ou ATSR.

Ela é mínima, porém internamente coerente para a máquina atual, que usa somente a RX 7800 XT e tem a iGPU desativada. O Windows reporta `AvailableSecurityProperties = 1,3,5,6,7,8`, incluindo suporte ao hipervisor, proteção DMA, MBEC e virtualização de APIC. Isso reduz a probabilidade de a DMAR ser inteiramente inválida.

### MADT/APIC — inconsistência concreta

A MADT anuncia 16 processadores Local APIC habilitados:

- ACPI Processor UID: `0..15`
- Local APIC IDs: `0,2,4,6,8,10,12,14,1,3,5,7,9,11,13,15`

A ordem de APIC IDs é normal para listar primeiro um thread de cada núcleo e depois os siblings. O problema está nos 16 registros Local APIC NMI:

- NMI Processor UID: `1..16`
- LINT: `1`

Assim, o processador ativo de UID `0` não recebe associação NMI e o registro final aponta para UID `16`, que não está habilitado na MADT. O DSDT contém um template genérico PR00..PR23, portanto o objeto PR16 existe, mas não representa uma CPU ativa neste boot.

A especificação ACPI exige que o campo do NMI corresponda ao `_UID`/Processor ID do processador; `0xFF` seria o valor para aplicar a todos. A sequência `1..16` diante de CPUs ativas `0..15` é, portanto, um deslocamento de uma unidade no firmware.

O CpuSsdt também contém um erro de cópia em PR16: calcula `PF16` usando `PF15` no operando esquerdo. PR16 está inativo nesta CPU de 16 threads, então esse segundo defeito provavelmente não participa do boot atual, mas mostra baixa qualidade na geração das tabelas de CPU.

## Comportamento observado no Windows

- VT-x, SLAT, proteção DMA, MBEC e APIC virtualization são detectados como disponíveis.
- VBS e os serviços de segurança virtualizada estão desativados no boot funcional.
- Não há eventos do provedor `Microsoft-Windows-Hyper-V-Hypervisor` registrados para a falha.
- Não existe minidump/MEMORY.DMP correspondente.
- Os resets registrados têm `BugcheckCode = 0` e `BootAppStatus = 0`.

Isso é compatível com travamento/reset muito cedo, antes de o kernel registrar um bugcheck completo. Não prova que a MADT seja a causa, mas torna firmware/topologia/entrada no hipervisor mais plausível que um driver comum carregado posteriormente.

## “Drivers de 1960”

Os binários locais `hvloader.dll`, `hvix64.exe`, `hvax64.exe`, `hvcrash.sys`, `hvservice.sys` e `hvsocket.sys` são versões atuais da série Windows `10.0.26100.x` e têm assinatura Microsoft.

Datas absurdas mostradas por certas ferramentas ao ler o campo PE/COFF não representam necessariamente a data real do arquivo. Em builds determinísticos/reprodutíveis do Windows, o campo pode ser derivado de um hash. Esta pista não indica, por si só, driver antigo ou corrompido.

## Dump integral da BIOS em execução

O FPT 15.0.20.1419 identificou o chip SPI físico como Winbond `EF4018`, 16 MiB, com Flash Descriptor válido. Foram realizadas três leituras integrais consecutivas:

| Arquivo | Tamanho | SHA-256 |
|---|---:|---|
| `polestar_full_1.bin` | 16.777.216 | `68E9A8113DDDA6E192AA72417E69BD83A3E37DC10D4F1421F0D3B282E49231BD` |
| `polestar_full_2.bin` | 16.777.216 | `68E9A8113DDDA6E192AA72417E69BD83A3E37DC10D4F1421F0D3B282E49231BD` |
| `polestar_full_3.bin` | 16.777.216 | `68E9A8113DDDA6E192AA72417E69BD83A3E37DC10D4F1421F0D3B282E49231BD` |

As três leituras são idênticas. O dump e o log do FPT foram preservados em `firmware/manifests/runtime-2026-08-24/`.

Comparação com HM570111:

- Descriptor: byte por byte idêntico;
- código BIOS de `0x560000` até `0xFFFFFF`: byte por byte idêntico;
- diferenças BIOS restritas a `0x50008F..0x55FFFF`, que contém NVRAM e seu espelho;
- diferenças CSME restritas aos dados persistentes internos `0x1FA000..0x278307`.

Logo, a BIOS executável instalada é essencialmente a HM570111; o hash integral diferente decorre de NVRAM e estado persistente legítimo da placa.

## Valores ativos extraídos do NVRAM

O UEFIExtract A75 revelou duas cópias AMI NVAR em `0x500078` e `0x530078`. As variáveis relevantes têm o mesmo SHA-256 nos dois espelhos e os valores ativos são:

| Ajuste | VarStore/offset | Valor ativo |
|---|---:|---:|
| Intel VMX | `CpuSetup + 0xB9` | `1` |
| VT-d global | `SaSetup + 0x87` | `1` |
| X2APIC Opt Out | `SaSetup + 0x91` | `0` |
| DMA Control Guarantee | `SaSetup + 0x92` | `1` |
| IGD/IPU/IOP/ITBT VT-d | `SaSetup + 0x93..0x96` | `1` |
| MSI/FADT | `Setup + 0x6E8` | `1` |
| IOMMU preboot | `Setup + 0x8D3` | `0` |
| IOAPIC IRQ 24–119 | `PchSetup + 0x5FF` | `1` |
| CFG Lock | `CpuSetup + 0x43` | `0` |

Isso confirma diretamente que VMX e VT-d estão ligados. A falha não é ausência de virtualização; ocorre quando o hipervisor Microsoft assume a topologia e o modelo de interrupções da plataforma.

## Origem exata do erro MADT

A MADT está embutida como a segunda seção Raw do arquivo UEFI Freeform GUID `7E374E25-8E01-4FEE-87F2-390C23C606CD`.

O template reserva 16 entradas Processor Local APIC com:

- Processor UID `1..16`;
- APIC ID `0xFF`;
- flags desativadas.

Durante o boot, o firmware atualiza essas entradas para:

- Processor UID `0..15`;
- APIC IDs reais `0,2,4,6,8,10,12,14,1,3,5,7,9,11,13,15`;
- flags habilitadas.

Porém, as 16 entradas Local APIC NMI do mesmo template permanecem inalteradas em `1..16`. A transformação de boot, portanto, corrige a base das entradas de processador, mas esquece as entradas NMI. O resultado entregue ao Windows associa NMI aos UIDs `1..16`, deixa a CPU ativa UID `0` sem NMI e aponta a última entrada para a CPU inexistente UID `16`.

A cadeia defeituosa de 96 bytes aparece exatamente nas três imagens fornecidas:

- HM570111;
- HM570307;
- BIOSATUALIZADA.

Isso explica por que trocar entre essas versões não corrige o Hyper-V e é coerente com o problema ocorrer em instalações limpas e em várias unidades da placa.

## Por que Linux pode funcionar

O código x86 atual do Linux em `arch/x86/kernel/acpi/boot.c`, função `acpi_parse_lapic_nmi`, valida o tamanho da entrada e apenas avisa se o LINT não for 1. Ele não valida nem usa o Processor UID da entrada Local APIC NMI. Assim, o Linux pode ignorar na prática o deslocamento `1..16` e continuar inicializando KVM.

A especificação ACPI exige que o UID corresponda ao processador descrito na MADT/namespace; `0xFF` é o valor global para todos os processadores. A Microsoft documenta que o Windows usa a MADT para descrever o modelo de interrupções da plataforma. O Hyper-V assumir APIC/interrupt remapping antes do kernel normal torna a falha precoce coerente com essa tabela inválida.

Fontes:

- [ACPI 6.6 — Local APIC NMI](https://uefi.org/specs/ACPI/6.6/05_ACPI_Software_Programming_Model.html)
- [Linux x86 ACPI boot parser](https://github.com/torvalds/linux/blob/master/arch/x86/kernel/acpi/boot.c)
- [Microsoft — ACPI System Description Tables](https://learn.microsoft.com/en-us/windows-hardware/drivers/bringup/acpi-system-description-tables)
- [Microsoft — Hyper-V Architecture](https://learn.microsoft.com/en-us/windows-server/virtualization/hyper-v/architecture)

## Patch mínimo construído

O patch modifica somente os 16 bytes de Processor UID das entradas Local APIC NMI no template:

```text
01,02,03,04,05,06,07,08,09,0A,0B,0C,0D,0E,0F,10
                         ↓
00,01,02,03,04,05,06,07,08,09,0A,0B,0C,0D,0E,0F
```

Foi construído um candidato layout-preserved diretamente sobre o dump
validado. O binário derivado não é redistribuído; sua identidade e receita estão
em `firmware/manifests/artifact-provenance.json`.

SHA-256:

`4F99E06399972E31D7D86383D8B81E451C7F75A5D5A00DB8CD8A34AFA25E8E73`

Método:

1. validar tamanho e SHA-256 do dump original;
2. validar offset, tamanho e SHA-256 do payload LZMA;
3. descomprimir os 12.320.784 bytes;
4. exigir uma única ocorrência da cadeia NMI no offset `0xA571B4`;
5. alterar exatamente os 16 offsets de UID;
6. recomprimir com `LzmaCompress.exe` oficial do TianoCore, dicionário de 16 MiB;
7. preencher os 40 bytes restantes com `FF`, preservando todos os cabeçalhos, tamanhos e offsets;
8. reabrir a imagem com UEFIExtract A75.

Validação lógica:

- tamanho final: 16.777.216 bytes;
- Descriptor: idêntico;
- CSME: idêntico;
- NVRAM e seus dois espelhos: idênticos;
- 1.949 elementos folha antes e depois;
- exatamente um elemento folha diferente: a MADT de 300 bytes;
- a MADT corrigida contém NMI UIDs `0..15`;
- nenhum módulo executável, microcode, tabela DMAR, DSDT/SSDT ou pad-file foi alterado;
- o parser moderno concluiu com sucesso;
- uma segunda construção independente produziu exatamente o mesmo SHA-256;
- o diff dos relatórios estruturais contém somente os CRCs encadeados da MADT, do arquivo Freeform e de seus contêineres pais;
- as entradas NVAR já marcadas como inválidas/obsoletas pelo parser são idênticas no original e no candidato.

Uma MADT runtime prevista, com os mesmos APIC IDs observados e UIDs NMI corrigidos, passa no checksum ACPI e não possui CPU sem NMI nem NMI apontando para CPU inexistente.

## Caminho real de inicialização do hipervisor Microsoft

O componente que toma controle do processador não é um driver `.sys`. O caminho relevante é:

```text
UEFI -> bootmgfw.efi -> winload.efi -> hvloader.dll -> hvix64.exe -> partição raiz do Windows
```

`hvix64.exe` é a imagem Intel do hipervisor. `vmbus.sys`, `vid.sys`, `hvservice.sys`, drivers sintéticos e drivers físicos pertencem à partição raiz e só se tornam relevantes depois que o hipervisor já foi lançado. A própria arquitetura publicada pela Microsoft coloca o hipervisor abaixo da partição raiz e o VMBus dentro da pilha de virtualização dessa partição.

Estado local dos componentes principais:

| Componente | Versão apresentada | SHA-256 | Assinatura |
|---|---|---|---|
| `winload.efi` | `10.0.26100.8875` | `5B36477FCF3F235C57756C929009186672012B26B164B9E12440CE6A427A3575` | Microsoft válida |
| `hvloader.dll` | `10.0.26100.8875` | `BEC3D62260239D869D3DE684D2CFAB1D7FF762A1927456E934DDAC15522AEC09` | Microsoft válida |
| `hvix64.exe` | `10.0.26100.9168` | `BCB0FC2D234E2A9D84577C8CFADA7E8D47E02BD7B55817BCCDCBF4FB789D8D21` | Microsoft válida |
| `ntoskrnl.exe` | `10.0.26100.9168` | `13AA072103656881BAB86C09AC0F8362265783BBFB428E85FF060E6018EC2488` | Microsoft válida |

O diretório WinSxS do componente `10.0.26100.9168` contém `hvloader.dll` e `hvix64.exe` com exatamente os mesmos hashes instalados em System32. Portanto, a diferença visual `8875/9168` não é evidência de mistura de arquivos: o servicing store os trata como o mesmo conjunto 9168.

O WinSxS ainda preserva o conjunto anterior `26100.8875`. A inspeção comparativa mostra que tanto 8875 quanto 9168 já contêm as rotas `MinimalLoop` de APIC, diagnóstico de FMS e a opção de desabilitar MBEC. Isso não exclui regressões em versões mais antigas do Windows, mas não há sinal de que esses caminhos tenham surgido apenas no update 9168.

Serviços relacionados:

- `vmbus.sys`: `Start=0`, System Bus Extender;
- `vid.sys`: `Start=1`;
- `hvservice.sys`: `Start=3`;
- `netvsc`, `hyperkbd`, `hypervideo` e `vmgid`: `Start=3`;
- `hvcrash.sys`: `Start=4`, desativado.

Mesmo `vmbus.sys`, apesar de marcado boot-start, só pode executar como driver da partição raiz. Uma reinicialização dentro do lançamento de `hvix64.exe`, antes de bugcheck/eventos, não pode ser causada por `netvsc`, `vid`, `hvservice` ou outro driver normal que ainda não recebeu execução. Isso responde diretamente à hipótese do “driver específico”: existe uma pilha de drivers Hyper-V, mas o binário que pode reiniciar a máquina nessa fase é o próprio hipervisor, carregado por `hvloader.dll`, não um `.sys` substituível.

Fontes:

- [Microsoft — Hyper-V Architecture](https://learn.microsoft.com/en-us/windows-server/virtualization/hyper-v/architecture)
- [Microsoft — requisitos de hardware do Hyper-V](https://learn.microsoft.com/en-us/windows-server/virtualization/hyper-v/host-hardware-requirements)

## Engenharia reversa de `hvloader.dll` e `hvix64.exe`

Foi criado `archive/experiments/legacy-scripts/inspect_hyperv_pe.py` para inspecionar PE, imports, identidade PDB, strings e instruções privilegiadas. Os PDBs públicos correspondentes não estavam disponíveis no servidor público de símbolos da Microsoft, então nenhuma função interna sem símbolo foi nomeada como se estivesse confirmada.

Identidades PDB:

- `hvloader.pdb/F77B5B3673248C477F15B2447194D8A61`;
- `hvix64.pdb/BDAA486DC5225639DF5DC7356376DCE31`.

O `hvloader.dll` importa diretamente de `winload`:

- `BlUtlGetAcpiTable` e `BlUtlPopulateAcpiTableCache`;
- `BlGetProcessorApicIds` e `BlGetLogicalProcessorCount`;
- `OslLoadMicrocodeUpdate`;
- `BlArchGetCpuVendor`.

Ele contém diagnósticos específicos para inconsistências MADT/DMAR, inclusive IOAPIC da DMAR ausente na MADT, IOAPIC conflitante, RID sob mais de uma IOMMU e DRHD `Include-All` malformado. A DMAR desta placa passa as verificações estruturais visíveis: IOAPIC ID 2 coincide com a MADT, há apenas um DRHD Include-All e a largura de 39 bits coincide com o CPUID.

### Configuração Microsoft anterior ao kernel: `IgnoreMemPart`

A chave local `HKLM\SYSTEM\CurrentControlSet\Control\Hypervisor` contém apenas `IgnoreMemPart=1`. Isso não é um driver de terceiros. A análise do `hvloader.dll` instalado localizou a string em VA `0x180020A30`, referenciada pela função em `0x18000AB64`, chamada por `HvlLoadHypervisor`, `HvlPreloadHypervisor` e `HvlExchangeDispatchInterface`. O fluxo chama `OslGetControlSubkey("Hypervisor")`, lê o DWORD e, se ele for não zero no ambiente normal de boot, pula `BlMmOpenPartition("\\KernelObjects\\MemoryPartitionHypervisorMetadata")`. Depois ele consulta também `MetadataMemoryPartition`.

Portanto, o valor altera de fato a preparação de memória do hipervisor antes do kernel. Não há documentação pública da Microsoft que defina seu contrato, e o valor `1` pode ser uma mitigação intencional do Windows. Ele foi classificado como hipótese secundária: somente se a matriz BCD inteira falhar, testar `0` isoladamente e restaurar `1` em seguida. Foram criados scripts reversíveis com backup integral da chave e `dry-run` padrão; nenhum valor foi alterado durante esta análise.

Instruções encontradas no código executável:

| Binário | `CPUID` | `RDMSR` | `WRMSR` | `VMXON` | Observação |
|---|---:|---:|---:|---:|---|
| `hvloader.dll` | 30 | 28 | 14 | 1 | faz uma tentativa real de `VMXON` em RVA `0x1C705` e testa o resultado |
| `hvix64.exe` | 94 | 252 | 296 | 1 | inicializa VMCS, EPT, VPID, APIC e processadores auxiliares |

Strings de diagnóstico presentes no `hvix64.exe` incluem:

- processadores que não respondem e falha ao adicionar processador lógico;
- `AP microcode update status`;
- machine check antes de a raiz estar pronta, seguido de reboot;
- falha de carregamento de MSR na entrada VM;
- `MinimalLoop` reiniciando por acesso APIC, INIT ou violação EPT;
- broadcast NMI vindo do IOAPIC;
- falhas de IOMMU/interrupt remapping;
- `Processor FMS is unknown! MSRs accesses may fault.`.

Essas mensagens provam que há caminhos internos de reinicialização sem bugcheck normal exatamente nas áreas suspeitas, mas **não provam qual mensagem ocorreu nesta máquina**. A string de FMS, em especial, não possui referência direta recuperada. Há uma sequência ampla de valores family/model que inclui `0x068D`, mas sem referência de código ela não foi tratada como whitelist. Portanto, não há base para afirmar que todo Tiger Lake-H model 8D seja rejeitado; a diferença de stepping ainda pode afetar MSRs, mas não é uma rejeição simples confirmada.

## Tiger Lake ES: stepping e microcode

O CPUID atual é `000806D0`: family 6, model 8D, stepping 0. A especificação de produção da Intel lista Tiger Lake H81 como `000806D1`; ela não lista `806D0`. Isso confirma que o processador é um stepping pré-produção, não apenas um nome genérico estranho no SMBIOS.

O repositório público atual de microcode da Intel contém `06-8d-01` para o stepping de produção e não contém `06-8d-00`. O microcode `0x50` do D0 nesta BIOS é, portanto, um payload ES/OEM não publicado no pacote público. O fato de uma revisão histórica D1 também ter número `0x50` não torna os payloads equivalentes: a assinatura completa inclui stepping e platform ID.

Fontes:

- [Intel — 11th Generation Core Processor Specification Update](https://cdrdv2-public.intel.com/631123/631123_032.pdf)
- [Intel — pacote público de microcode](https://github.com/intel/Intel-Linux-Processor-Microcode-Data-Files)

## CPUID: topologia coerente e uma combinação AVX-512 incoerente

O script `archive/experiments/legacy-scripts/dump_cpuid_windows.py` executou CPUID preso sucessivamente a todos os 16 processadores lógicos. Depois de mascarar apenas o APIC ID esperado, os 16 LPs produziram o mesmo fingerprint de recursos. A topologia da folha `0xB` também é coerente: 2 threads por núcleo, 16 threads por pacote, total 8C/16T. Isso reduz a hipótese de um único núcleo anunciar CPUID diferente.

Há, porém, uma inconsistência objetiva:

| Campo | Valor |
|---|---|
| `CPUID.7.0.EBX` | `0x239CA7EB` |
| `CPUID.7.0.EDX` | `0xFC100510` |
| `CPUID.7.0.EBX[16]` AVX512F | `0` |
| `CPUID.7.0.EBX[31]` AVX512VL | `0` |
| `CPUID.7.0.EDX[8]` AVX512_VP2INTERSECT | `1` |
| `CPUID.0xD.0.EAX` | `0x00000207` |
| estados XCR0 5, 6 e 7 de AVX-512 | todos `0` |

A Intel define EDX bit 8 como `AVX512_VP2INTERSECT`; as formas de 128/256 bits exigem também AVX512VL e as formas de 512 bits exigem AVX512F. Nesta máquina nenhuma base está exposta e nem existem os estados opmask/ZMM em XCR0. O recurso está, portanto, órfão e inutilizável.

Isso coincide com o NVRAM ativo:

- `CpuSetup+0x229 = 0`: AVX habilitado;
- `CpuSetup+0x22A = 1`: opção AMI `AVX3` desabilitada;
- o IFR declara `AVX3 Enabled=0` como default, mas a NVRAM atual contém `1`.

A hipótese mais simples é que o código de setup oculte AVX-512 de modo incompleto no ES e esqueça o bit VP2INTERSECT. Um hipervisor que salva, normaliza e valida CPUID/XSTATE para todos os LPs pode encontrar essa combinação antes do kernel. O teste correto não é editar `hvix64.exe`: é habilitar temporariamente `AVX3` na BIOS, repetir o dump CPUID e verificar se AVX512F/VL, VP2INTERSECT e XSTATE 5–7 passam a aparecer juntos. Se todos desaparecerem juntos com outra configuração, também é coerente.

Uma checagem das dependências vizinhas não encontrou outra combinação quebrada: PKU está acompanhado pelo estado PKRU em XCR0 bit 9; CET Shadow Stack e IBT estão anunciados e os estados CET de usuário/supervisor aparecem em `CPUID.0xD.1:ECX` bits 11 e 12. Assim, a inconsistência observada não é um falso positivo causado por interpretar todo estado supervisor como ausente em `CPUID.0xD.0`; ela permanece específica à máscara AVX-512/VP2INTERSECT.

Fonte: [Intel — Architecture Instruction Set Extensions Programming Reference](https://cdrdv2-public.intel.com/843860/architecture-instruction-set-extensions-programming-reference-dec-24.pdf).

## Segunda passagem pelas tabelas de plataforma

- DMAR: HAW 39 bits igual ao CPUID; IOAPIC ID 2 igual à MADT; DRHD Include-All em `FED91000`; nenhuma duplicidade de RID visível.
- WSMT: flags `0x7`, com buffers fixos, proteção de ponteiros aninhados e proteção de recursos do sistema.
- FADT: revisão 6, checksum válido, reset por `0xCF9`, MSI suportado; não é Hardware Reduced e não anuncia Low Power S0 Idle.
- MCFG: checksum válido, segmento 0, janela `C0000000`, buses 0–7. O alcance é pequeno, mas não há evidência de que participe do reset no primeiro `VMXON`.
- Não há SRAT/SLIT; para um pacote e um nó NUMA isso não é um erro.

Esses resultados não absolvem VT-d: a transição de interrupt remapping ainda é código ativo do hipervisor. Eles apenas eliminam os erros DMAR mais óbvios que o próprio `hvloader` diagnostica.

## Matriz de diagnóstico criada, ainda não aplicada

O protocolo completo está em `docs/hyperv-test-matrix.md`. O script `archive/experiments/legacy-scripts/prepare-hyperv-diagnostic-matrix.ps1` é `dry-run` por padrão e cria, somente com `-Apply` elevado:

1. baseline com hipervisor ligado e VSM desligado;
2. IOMMU desabilitada para o hipervisor;
3. x2APIC desabilitado e APIC legado forçado;
4. apenas um processador lógico iniciado pelo hipervisor;
5. combinação mínima de um CPU + xAPIC legado + IOMMU desligada;
6. MBEC por hardware desabilitado pelo load option encontrado no `hvloader`.
7. XSAVE desabilitado globalmente para isolar o caminho de inicialização
   XSAVE/XSTATE; um resultado positivo não identifica sozinho qual componente
   incoerente é o gatilho e deixa AVX/AVX2 indisponíveis.
8. captura de `ntbtlog.txt`, nomes de drivers na tela e bugcheck sem reinício automático;
9. vAPIC desabilitado pelo elemento BCD `hypervisorusevapic` (`0x26000116`);
10. interrupções postadas desabilitadas;
11. virtualização de IPI desabilitada;
12. SLAT/EPT desabilitado;
13. destino físico do APIC forçado;
14. scheduler clássico do hipervisor;
15. live handoff da IOMMU desabilitado;
16. IOMMU escalável desabilitada;
17. fonte de tempo de referência forçada para ACPI PM Timer;
18. sincronização de TSC forçada.

O BCD é exportado antes, `{current}` permanece com Hyper-V desligado e como padrão, o menu dura 15 segundos e nenhuma entrada perigosa é agendada automaticamente. Um segundo script remove apenas os GUIDs gravados no manifesto. As opções públicas `hypervisornumproc`, `hypervisoriommupolicy`, `x2apicpolicy`, `uselegacyapicmode` e `xsavedisable` estão documentadas pela Microsoft: [BCDEdit /set](https://learn.microsoft.com/en-us/windows-hardware/drivers/devtest/bcdedit--set).

Como eixo separado da matriz, os scripts `prepare-hyperv-ignoremempart-test.ps1` e `restore-hyperv-ignoremempart-test.ps1` permitem comparar o valor local `IgnoreMemPart=1` com `0`, sempre preservando um `.reg` e um manifesto. Esse teste é global, não pertence a uma entrada BCD, e fica deliberadamente por último por não haver contrato público para o valor.

## Esgotamento adicional: opções reais do hipervisor

A análise estática do `hvloader.dll` instalado confirmou que `hypervisorloadoptions` é lido do elemento BCD `0x22000117` e também da string de Registro `Hypervisorloadoptions`. O conteúdo é normalizado e repassado ao hipervisor. O mesmo conjunto de tokens aparece em `hvloader.dll` e `hvix64.exe`, incluindo:

- `DISABLEPOSTEDINTERRUPTS`;
- `DISABLEIPIVIRTUALIZATION`;
- `DISABLESCALABLEIOMMU`;
- `IOMMULIVEHANDOFF=DISABLE`;
- `DISABLEHARDWAREMBEC`;
- `REFERENCETIMESOURCE=HPET` e `REFERENCETIMESOURCE=PMTIMER`;
- `SYNCTSC`.

Os dois primeiros são particularmente relevantes porque a MADT defeituosa, a enumeração APIC intercalada e o reset sem bugcheck convergem no caminho APIC/VMX. `IOMMULIVEHANDOFF=DISABLE` é consumido diretamente pelo `hvloader`; os demais tokens são opções internas transferidas ao `hvix64`. Eles são experimentais e servem para diagnóstico, não como configurações permanentes sem resultado positivo.

O IFR da BIOS não oferece controles para vAPIC, posted interrupts ou IPI virtualization. Ele expõe somente VMX, VT-d, `X2APIC Opt Out` e `Control Iommu Pre-boot Behavior`. Este último já está em `0` (IOMMU desabilitada no ambiente pré-boot), portanto `IOMMULIVEHANDOFF=DISABLE` tem prioridade baixa; vAPIC/posted interrupts/IPI não possuem equivalente visível no Setup e precisam ser isolados pelo BCD.

`HypervisorUseVapic` também foi confirmado em código: primeiro o loader tenta o elemento BCD booleano `0x26000116`, depois usa o DWORD de mesmo nome no Registro como fallback. A própria documentação Microsoft de validação BCD do BitLocker mapeia esse identificador para o nome amigável `hypervisorusevapic`: [BCD settings and BitLocker](https://learn.microsoft.com/en-us/windows/security/operating-system-security/data-protection/bitlocker/bcd-settings-and-bitlocker).

## Temporização: estática coerente, teste dinâmico ainda possível

O CPUID atual informa `Invariant TSC=1`. A folha `0x15` contém denominador 2, numerador 162 e cristal de 38,4 MHz, resultando em TSC de 3.110.400.000 Hz. A folha `0x16` informa base de 3.100 MHz, diferença de apenas 0,3355%. A HPET aponta para `FED00000`, a FADT fornece PM Timer de 24 bits em `0x1808` e ambas têm checksum válido.

Não há, portanto, inconsistência estática de relógio semelhante à encontrada em AVX-512. Ainda pode existir skew entre LPs durante o bring-up; o próprio `hvix64` contém mensagens `TscSync Failed` e `TscSync Unstable`. Por isso `PMTIMER` e `SYNCTSC` permanecem na última onda da matriz, depois de APIC/VMX/IOMMU.

## Drivers Microsoft e atualização de microcode

Foi inventariada a pilha Microsoft relevante. `vmbus.sys`, `storvsc.sys` e `vpci.sys` são `BOOT_START`; `Vid.sys` é `SYSTEM_START`; `intelppm.sys` é PnP/demand start. Todos os arquivos verificados possuem assinatura Microsoft válida. O inventário com versão, hash e grupo está em `evidence/hyperv/hyperv-root-driver-inventory.json`.

Há vários eventos Kernel-Power 41, todos com `BugcheckCode=0`, `WHEABootErrorCount=0` e sem minidump correspondente. Isso não prova sozinho a fase exata, mas é incompatível com a hipótese comum de um `.sys` da partição raiz gerar um BSOD registrado. A entrada `HV 08 CAPTURA BOOTLOG` passa a ser a prova operacional: se o horário de `C:\Windows\ntbtlog.txt` não mudar após o reset, o kernel não chegou à fase de logar drivers; se mudar, o último `Loaded driver` delimita a fase.

`mcupdate_GenuineIntel.dll` também é assinado pela Microsoft, mas o Registro de hardware mostra `Update Revision=0x50` e `Previous Update Revision=0x50`. Assim, o Windows não substituiu o payload da BIOS nesta inicialização. O dump contém microcode D0 `0x50`, de 17/12/2020, em todas as variantes fornecidas; não existe um D0 mais novo entre elas. Os drivers de processador exibirem datas históricas de INF e binários do hipervisor exibirem timestamps PE incomuns não significa que sejam código de 1960/2006/2009.

`sfc /verifyonly` foi tentado, mas a sessão atual não é elevada e o utilitário recusou a execução antes de verificar arquivos. Isso não é um resultado de corrupção. Se a captura `HV 08` provar que o kernel chegou a carregar drivers, executar depois, em terminal Administrador, `sfc /verifyonly` e `DISM /Online /Cleanup-Image /ScanHealth`; se não houver `ntbtlog`, essas verificações não explicam o reset pré-kernel.

## Comparação módulo a módulo das BIOS

O comparador `archive/experiments/legacy-scripts/compare_uefi_code_modules.py` agrupa PE32/TE pelo nome do módulo, ignorando índices de caminho que mudam com NVRAM. Resultados gravados em JSON:

- runtime versus `HM570111`: 309 de 309 módulos executáveis idênticos; zero mudou;
- `HM570111` versus `HM570307`: 17 de 309 mudaram; 292 são idênticos;
- `HM570111` versus `BIOSATUALIZADA`: layouts incompatíveis, 309 contra 115 chaves e 334 diferenças na união.

Entre 111 e 307, o único módulo alterado que participa claramente do pré-memory platform init é `PlatformInitPreMem` TE, com mesmo tamanho de 42.944 bytes mas hash diferente. As rotas ACPI/DMAR que geram as tabelas permanecem idênticas e ambas as versões apresentam o mesmo erro NMI `1..16`. Transplantar `PlatformInitPreMem` sem conhecer as diferenças de placa é mais arriscado que o patch de 16 bytes da MADT e não possui evidência causal. `BIOSATUALIZADA` não é do mesmo empacotamento/FSP e não serve como doadora de módulos ou imagem integral.

## Possibilidades restantes, em ordem técnica

1. **Inicialização XSAVE/XSTATE:** `xsavedisable=1` permite o boot, mas
   desabilita XSAVE globalmente e remove AVX/AVX2. Isso confirma o caminho
   causal geral, não o componente exato.
2. **MADT/AP startup/APIC:** defeito confirmado na tabela; corrigi-lo muda o
   modo de falha, mas não basta para iniciar o Hyper-V.
3. **Máscara AVX3/CPUID/XSTATE:** `VP2INTERSECT` órfão é uma inconsistência
   confirmada e um gatilho candidato, ainda não isolado.
4. **Capacidades VMX/MSRs específicas do D0:** Linux/KVM provar VMX/EPT básico não garante que todos os controles exigidos pelo Hyper-V sejam idênticos em todos os LPs. O coletor Linux criado lê `IA32_VMX_*` em cada CPU.
5. **x2APIC/APIC virtualization fora da MADT:** o Windows reporta APIC virtualization disponível, mas a transição ainda pode falhar no ES ou no firmware. A entrada xAPIC legado isola isso.
6. **DMAR/VT-d/interrupt remapping:** a tabela é internamente coerente, mas o caminho de ativação continua testável com IOMMU desligada.
7. **Drivers `.sys` da partição raiz:** probabilidade muito baixa para este sintoma, porque a falha reproduz em instalação limpa e pode ocorrer antes que esses drivers executem.
8. **`IgnoreMemPart=1`:** configuração Microsoft confirmada no caminho de preload e memória do hipervisor; plausível como desvio específico desta instalação, porém de prioridade baixa e sem documentação pública. O teste `0` deve ser isolado e revertido.
9. **Compatibilidade por geração do Hyper-V:** o WinSxS atual só permite comparar revisões do mesmo ramo 26100, e ambas contêm as rotas suspeitas. Se o hardware continuar falhando após todos os isoladores, um Windows 10 22H2 ou Windows 11 23H2 oficial em SSD separado pode servir como bisect de versão. Ele não deve substituir nem alterar a instalação atual; se uma geração antiga iniciar, o alvo passa a ser uma diferença de validação do `hvix64`, não um driver físico.

Não é tecnicamente razoável “mascarar D0 como D1” por ACPI. Family/model/stepping vêm da instrução CPUID. Um spoof real exigiria microcode compatível ou outra camada de virtualização anterior ao Hyper-V e poderia induzir o Windows a tocar MSRs/erratas do D1 que não existem no D0. As correções aceitáveis são, em ordem: ajustar configuração existente, corrigir ACPI/DMAR, e só então modificar código de firmware com uma diferença mínima e verificável.

## Validação pré-flash da MADT por OpenCore

Foi montada uma árvore OpenCore 1.0.7 que aplica a correção somente em memória. O patch é limitado à tabela `APIC` de 300 bytes, ao OEM Table ID exato, à sequência completa dos 16 registros NMI e a uma única substituição. A implementação oficial recalcula o checksum após uma substituição bem-sucedida.

Também foi criado um controle negativo com a mesma configuração e o patch desativado. Assim, um boot positivo pode distinguir a correção MADT de um efeito genérico do OpenCore. Todas as configurações passaram no `ocvalidate`; o instalador foi testado somente em `dry-run` contra a partição `BIOS_BACKUP` e confirmou os hashes dos três dumps antes de planejar qualquer alteração.

O coletor `dump_acpi_windows.py` usa `GetSystemFirmwareTable` e, no boot atual sem OpenCore, reproduziu exatamente o SHA-256 anterior da MADT e a incompatibilidade CPUs `0..15` / NMIs `1..16`. O protocolo seguro está em `OPENCORE_MADT_TEST.md`. Esse teste deve preceder qualquer gravação da candidata de firmware.

## Estado de confiança

1. **Defeito estrutural MADT `1..16` versus `0..15`: confirmado.**
2. **Origem no template e transformação incompleta do firmware: confirmada.**
3. **Linux não depender desse UID no parser x86: confirmado no código.**
4. **Patch alterar apenas a MADT lógica: confirmado por extração e hashes.**
5. **CPUID expor VP2INTERSECT sem AVX512F/VL/XSTATE: confirmado nos 16 LPs.**
6. **O reset ocorrer antes dos drivers `.sys` normais: compatível com toda a evidência, ainda sem trace de depuração.**
7. **A MADT ser sozinha a causa do bootloop: refutado pelo teste; a correção
   muda o modo de falha, mas não inicia o Hyper-V.**
8. **Desabilitar XSAVE globalmente permitir o boot: confirmado, junto com a
   perda de AVX/AVX2; isso localiza o caminho XSTATE sem identificar o gatilho
   individual.**

A candidata MADT permanece apenas como experimento mínimo reproduzível. Não
deve ser gravada nem tratada como solução. O próximo objetivo é obter Hyper-V
com XSAVE/AVX/AVX2 ativos e isolar seletivamente o contrato XSTATE que falha.

Se todos os isoladores falharem, `docs/hyperv-debugging.md` descreve a captura do hipervisor com um segundo PC. A NIC cabeada Realtek `10EC:8168` do alvo está na lista oficial de dispositivos KDNET, mas `kdnet.exe`/WinDbg ainda não estão instalados e nada foi habilitado. Essa captura é o caminho para distinguir definitivamente VM-entry/MSR, AP startup, APIC, IOMMU, EPT e machine check sem inferir pela ausência de minidump.

## Antes de qualquer gravação

O candidato **não deve ser gravado ainda** até completar estes controles:

1. fazer três leituras externas com o programador e comparar os hashes entre si;
2. comparar o dump externo com o dump FPT para confirmar acesso integral;
3. identificar fisicamente o chip como 1,8 V ou 3,3 V antes de conectar/gravar;
4. testar a restauração do arquivo original no programador, ao menos até a etapa de verificação sem erro;
5. preparar a matriz BCD recuperável descrita em `docs/hyperv-test-matrix.md`, mantendo `{current}` com `hypervisorlaunchtype off` como padrão;
6. após gravar, iniciar primeiro com Hyper-V desligado e capturar novamente a MADT; ela deve apresentar NMI UIDs `0..15` e checksum válido;
7. somente depois selecionar a entrada de teste do Hyper-V.

Se o teste falhar, restaurar o dump original `68E9A811...31BD` pelo programador. Não usar `BIOSATUALIZADA.bin` como imagem integral de recuperação porque seu layout SPI é diferente.
