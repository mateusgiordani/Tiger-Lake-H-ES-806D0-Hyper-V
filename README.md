# Projeto Polestar HM570 / Tiger Lake ES — Hyper-V bootloop

## Objetivo

Investigar e, se possível, corrigir o bootloop/reset que ocorre quando o
hipervisor da Microsoft é iniciado nesta placa-mãe chinesa Polestar/Erying
HM570 com processador Tiger Lake-H Engineering Sample.

Virtualização VMX/EPT funciona no Linux/KVM. O Windows também detecta os
recursos de virtualização, mas falha muito cedo quando
`hypervisorlaunchtype=Auto`.

Este arquivo consolida o estado do projeto em **24/08/2026**. Ele deve ser lido
antes dos relatórios antigos, porque alguns documentos em `analysis/` foram
escritos antes dos testes reais com OpenCore.

## ATENÇÃO — estado operacional atual

Nenhuma BIOS modificada foi gravada.

Entretanto, no fim da sessão foi preparada uma inicialização única de controle:

- GUID de teste: `{5cbe73ca-b469-11f0-9ffb-c2e7dda09ff1}`;
- descrição: `Windows - HYPERV OPENCORE CONTROL`;
- Hyper-V: `Auto`;
- VSM: `Off`;
- sem isoladores adicionais;
- `nocrashautoreboot=yes`;
- `bootsequence` única agendada;
- pendrive OpenCore atualmente em `CONTROL DISABLED`, com a MADT **original e
  incorreta**;
- o teste ainda **não havia sido executado** quando este README foi criado.

Isso significa que o próximo carregamento do Windows Boot Manager pode entrar
diretamente no teste Hyper-V, inclusive se o boot for iniciado pelo disco
interno. O menu BCD não precisa aparecer quando existe `bootsequence`.

Se a intenção for apenas entregar o projeto para análise e não executar o
controle agora, abrir PowerShell como Administrador e cancelar antes de
reiniciar:

```powershell
bcdedit /bootsequence "{5cbe73ca-b469-11f0-9ffb-c2e7dda09ff1}" /remove
bcdedit /enum "{bootmgr}"
```

O segundo comando não deve mostrar `bootsequence`. Alternativa equivalente:

```powershell
bcdedit /deletevalue "{bootmgr}" bootsequence
```

Não excluir `{current}`. Não repetir scripts com `-Apply` sem verificar antes
`bcdedit /enum "{bootmgr}"`.

## Hardware e firmware em execução

- Placa: Polestar/Erying HM570, família de firmware `HM570111`.
- BIOS em execução: AMI `THM570111`, data SMBIOS `06/08/2023`.
- CPU: Tiger Lake-H ES, family 6, model `0x8D`, stepping 0.
- CPUID/FMS: `000806D0`.
- CPU observada: 8 núcleos / 16 threads.
- Microcode ativo: revisão `0x50`, data do payload `17/12/2020`.
- GPU usada: RX 7800 XT; iGPU desabilitada.
- SPI: Winbond/compatível ID `EF4018`, 16 MiB.
- FPT usado: Intel Flash Programming Tool `15.0.20.1419`.

O processador é realmente um stepping pré-produção D0. A documentação pública
de produção da Intel lista Tiger Lake-H `806D1`; o pacote público de microcode
da Intel não contém `06-8d-00`.

## Backup original validado

Foram feitas três leituras integrais por FPT. Os três arquivos têm 16.777.216
bytes e o mesmo SHA-256:

`68E9A8113DDDA6E192AA72417E69BD83A3E37DC10D4F1421F0D3B282E49231BD`

Arquivos:

- `backup da bios que estava rodando/polestar_full_1.bin`
- `backup da bios que estava rodando/polestar_full_2.bin`
- `backup da bios que estava rodando/polestar_full_3.bin`

O `Fpt.efi -i` está em `backup da bios que estava rodando/log.txt` e informa:

- Flash Descriptor válido;
- Descriptor `0x00000000..0x00000FFF`;
- CSME `0x00001000..0x004FFFFF`;
- BIOS `0x00500000..0x00FFFFFF`;
- 16 MiB instalados e acessíveis;
- operação FPT concluída com sucesso.

Esses dumps são a referência de recuperação. Não substituir por
`BIOSATUALIZADA.bin`, pois ela possui particionamento/layout diferente.

## Sintoma original

- Windows normal, com Hyper-V e VSM desligados: inicia.
- Linux/KVM: virtualização funciona.
- Windows em instalação limpa, com o hipervisor Microsoft ativado: reset ou
  bootloop muito cedo.
- O problema é relatado por outros usuários da mesma placa.
- No caminho original não havia tela azul persistente, dump ou evento BugCheck.
- Os eventos Kernel-Power 41 registravam `BugcheckCode=0`.

Datas históricas exibidas em drivers Microsoft, inclusive anos como 1960, não
foram tratadas como causa. Os binários relevantes verificados são assinados
pela Microsoft e o problema também ocorre em instalação limpa.

## Defeito ACPI confirmado: mismatch da MADT

A MADT runtime original possui 16 entradas Processor Local APIC habilitadas:

- Processor UID: `0..15`;
- APIC IDs: `0,2,4,6,8,10,12,14,1,3,5,7,9,11,13,15`.

Mas os 16 registros Local APIC NMI usam:

- Processor UID: `1..16`;
- LINT: `1`.

Consequências estruturais:

- a CPU ativa UID `0` fica sem registro NMI correspondente;
- o último NMI aponta para UID `16`, que não é uma CPU ativa na MADT;
- a sequência está deslocada por uma unidade.

Esse defeito aparece nas três BIOS analisadas. A origem também foi localizada:
o template embarcado começa com CPUs/NMIs `1..16`; durante o boot o firmware
reescreve as entradas de CPU para `0..15`, mas deixa as entradas NMI em
`1..16`.

O Linux x86 não depende desse Processor UID no parser usado para Local APIC NMI,
o que explica por que Linux/KVM pode funcionar apesar da tabela inválida.

## Patch MADT mínimo construído — NÃO GRAVAR AINDA

Arquivo:

`analysis/candidates/polestar-hyperv-madt-nmi-zero-based-layout-preserved.bin`

- Tamanho: 16.777.216 bytes.
- SHA-256:
  `4F99E06399972E31D7D86383D8B81E451C7F75A5D5A00DB8CD8A34AFA25E8E73`.
- Origem: dump runtime de SHA-256 `68E9A811...31BD`.
- Alteração lógica: somente os 16 UIDs Local APIC NMI, de `1..16` para
  `0..15`.
- Descriptor, CSME, NVRAM, microcode, DMAR, DSDT/SSDT e executáveis foram
  preservados.
- UEFIExtract encontrou 1.949 folhas antes/depois; somente a folha MADT de 300
  bytes difere.
- Uma segunda construção independente gerou o mesmo hash.

Essa imagem é um experimento de firmware corretamente construído, mas **não é
uma solução comprovada**. Gravar agora apenas tornaria permanente uma MADT que
já foi testada em memória e que, sozinha, não fez o Hyper-V iniciar.

O rebuild antigo em `analysis/rejected/DO-NOT-FLASH-old-engine-rebuild/` é
explicitamente rejeitado e não deve ser gravado.

## Segundo defeito confirmado: CPUID/XSTATE incoerente

O dump CPUID foi executado nos 16 processadores lógicos. A topologia é coerente
entre eles, mas existe uma combinação de recursos inválida/inutilizável:

- `CPUID.7.0.EBX[16] AVX512F = 0`;
- `CPUID.7.0.EBX[31] AVX512VL = 0`;
- `CPUID.7.0.EDX[8] AVX512_VP2INTERSECT = 1`;
- `CPUID.0xD.0.EAX = 0x00000207`;
- estados XCR0 5, 6 e 7 necessários para AVX-512 ausentes.

O NVRAM ativo indica `CpuSetup+0x22A = 1`, opção AMI `AVX3` desabilitada. A
hipótese é que o setup esconda AVX-512 de forma incompleta neste ES e deixe o
bit VP2INTERSECT órfão.

O teste reversível ainda não realizado é habilitar temporariamente `AVX3` no
Setup, iniciar com Hyper-V desligado e repetir:

```powershell
python '.\analysis\scripts\dump_cpuid_windows.py' > '.\analysis\cpuid-avx3-enabled.json'
```

Não combinar esse teste com mudanças de VT-d, HT, quantidade de núcleos ou BCD.

## VMX, microcode e DMAR

- VMX e VT-d estão habilitados no NVRAM ativo.
- Linux/KVM prova VMX/EPT básico, mas não todas as combinações de controles
  exigidas pelo Hyper-V.
- Todas as BIOS fornecidas contêm microcode D0 revisão `0x50`; o Windows também
  permanece em `0x50`.
- Não foi encontrado microcode público mais novo para `806D0`.
- DMAR runtime tem 80 bytes, checksum válido, HAW 39 bits, um DRHD Include-All
  em `0xFED91000`, IOAPIC ID 2 e nenhum RMRR/ATSR.
- A DMAR passa as incoerências estruturais óbvias, mas ativação de interrupt
  remapping ainda pode falhar dinamicamente.

A principal lacuna restante são os MSRs `IA32_VMX_*` em cada LP. O coletor
Linux está pronto:

```bash
sudo modprobe msr
sudo python3 collect_tgl_vmx_msrs_linux.py > tgl-vmx-msrs.json
```

Script: `analysis/scripts/collect_tgl_vmx_msrs_linux.py`.

## Teste reversível da MADT com OpenCore

Foi preparado OpenCore oficial 1.0.7 RELEASE, sem kexts, spoof de SMBIOS ou
patch de kernel. O patch é restrito à tabela APIC de 300 bytes, ao OEM Table ID
exato e à sequência completa dos 16 registros NMI. O OpenCore recalcula o
checksum.

Hashes principais:

- ZIP OpenCore oficial:
  `2FFAB6EBF58C7AEFB0BCB3A1A385D207746823D6DD87D44BD666E1286939943E`;
- MADT runtime original:
  `8156FC0F85D4910F72D105C2B12AA92853EC6FB1DEEE35C9E7C3B6C3BD6C9612`;
- MADT corrigida entregue pelo OpenCore:
  `DEC804620606536ED5BEFD269E0EB4646732057CD355A9BE2006FDB67C119067`;
- config `PATCH ENABLED`:
  `A541BA6A79F73F9A5A932BFE105B712B446553C579A2DAAC8F4FADC5765D6B64`;
- config `CONTROL DISABLED`:
  `B537E45232F88F8D9124AB94E68D5F29381EC6D6CC47472BA6C0138F62B511C8`.

O Windows iniciou com segurança pelo OpenCore, Hyper-V desligado, e
`dump_acpi_windows.py` confirmou pela API `GetSystemFirmwareTable`:

- checksum válido;
- CPUs `0..15`;
- NMI UIDs `0..15`;
- SHA-256 exato `DEC804...067`.

Portanto, **está provado que a correção MADT foi realmente entregue ao
Windows**. Isso não prova que ela seja suficiente para iniciar Hyper-V.

## Resultados reais dos boots Hyper-V

### 1. Caminho original, sem OpenCore

MADT original `1..16`, Hyper-V ligado: reset/bootloop precoce, sem dump e sem
BugCheck registrado.

### 2. OpenCore + MADT corrigida + Hyper-V baseline

O modo de falha mudou para uma tela azul Windows visível:

`SYSTEM_THREAD_EXCEPTION_NOT_HANDLED (0x7E)`

Na repetição com parâmetros visíveis:

```text
0xFFFFFFFFC0000005
0xFFFFF807694E1A96
0xFFFFF38B0C606F58
0xFFFFF38B0C606760
```

`0xC0000005` é `STATUS_ACCESS_VIOLATION`. O segundo parâmetro é o endereço da
instrução; os dois seguintes são exception record e context record.

### 3. MADT corrigida + `hypervisornumproc=1`

Resultado: mesmo tipo de falha.

```text
0xFFFFFFFFC0000005
0xFFFFF8044BE01A96
0xFFFFB68F95006F58
0xFFFFB68F95006760
```

Conclusão limitada: restringir o hipervisor a um LP não resolveu.

### 4. MADT corrigida + `hypervisorusevapic=no`

O script removeu `hypervisornumproc` e todos os outros isoladores antes de
aplicar somente `hypervisorusevapic=no`.

Resultado:

```text
0xFFFFFFFFC0000005
0xFFFFF80549813A96
0xFFFFE50663606F58
0xFFFFE50663606760
```

Conclusão limitada: desligar vAPIC não resolveu.

Nos três bugchecks o endereço da instrução termina no mesmo deslocamento de
página `0xA96`, e exception/context record mantêm os mesmos deslocamentos
finais. Isso é compatível com a mesma região/fase de código, mas **não permite
identificar uma função ou driver** sem dump, símbolos e base ASLR daquela
inicialização.

Após os testes não havia:

- `C:\Windows\MEMORY.DMP`;
- minidump;
- `C:\Windows\ntbtlog.txt`;
- LiveKernelReports;
- evento BugCheck 1001 correspondente.

Somente Kernel-Power 41 foi gravado depois do desligamento forçado. A falha é
cedo demais para a infraestrutura normal de dump/bootlog.

`nocrashautoreboot=yes` foi configurado propositalmente nas entradas de teste.
Por isso a tela azul fica parada em “Você pode reiniciar”; isso não é um novo
travamento do OpenCore.

## Experimento causal que falta

Ainda não foi comparado Hyper-V pela **mesma cadeia OpenCore** com a MADT
original. Essa é a lacuna mais importante:

1. OpenCore + `PATCH ENABLED` + Hyper-V baseline -> `0x7E/C0000005`.
2. OpenCore + `CONTROL DISABLED` + Hyper-V baseline -> preparado, resultado
   ainda desconhecido.

Interpretação planejada:

- controle volta ao reset silencioso: a correção MADT faz o boot avançar, mas
  existe um segundo defeito;
- controle também mostra o mesmo `0x7E`: a mudança de apresentação veio da
  cadeia OpenCore e ainda não há benefício causal demonstrado para o patch;
- controle inicia: o patch MADT interfere negativamente e deve ser revisto.

O pendrive está agora em `CONTROL DISABLED`, hash ativo
`B537E452...B511C8`, e o BCD desse teste está agendado conforme a seção de
alerta no início deste README.

## Estado do BCD e recuperação

- BitLocker em `C:`: totalmente descriptografado, proteção desligada.
- Secure Boot: desligado durante os testes.
- `{current}` permanece o padrão seguro:
  - `hypervisorlaunchtype Off`;
  - `vsmlaunchtype Off`.
- Entrada reutilizada nos testes:
  `{5cbe73ca-b469-11f0-9ffb-c2e7dda09ff1}`.
- Cada script exportou o BCD antes e depois e gerou manifesto JSON em
  `analysis/bcd-backups/`.

Manifestos principais, em ordem:

- `hyperv-madt-atomic-onetime-20260824-181207.json`;
- `hyperv-7e-capture-onetime-20260824-182449.json`;
- `hyperv-one-lp-onetime-20260824-183609.json`;
- `hyperv-no-vapic-onetime-20260824-185832.json`;
- `hyperv-opencore-control-onetime-20260824-193148.json`.

O BCD do Windows está na ESP do disco Netac, disco 1 partição 1. A ESP do disco
Lexar/KDE não contém o Windows Boot Manager.

## O que foi descartado ou rebaixado

- Virtualização simplesmente desabilitada: refutado; VMX/VT-d estão ativos e
  Linux/KVM funciona.
- Microcode ausente: refutado; BIOS e Windows usam D0 revisão `0x50`.
- Driver comum de terceiros: probabilidade muito baixa; ocorre em instalação
  limpa e antes de bootlog/dump.
- Datas “1960” dos drivers: artefatos de INF/build, não evidência causal.
- `hypervisornumproc=1`: não resolveu.
- `hypervisorusevapic=no`: não resolveu.
- Gravar uma BIOS HM570307/Lightning inteira: perigoso e sem justificativa.
- Usar `BIOSATUALIZADA.bin` como recuperação ou doadora: layout incompatível.
- Mascarar CPUID D0 como D1 por ACPI: tecnicamente não funciona; CPUID vem da
  instrução do processador.

## Próximos passos tecnicamente úteis

Ordem recomendada para revisão por outro modelo:

1. Decidir se cancela ou executa o controle negativo já agendado.
2. Interpretar o controle antes de qualquer nova opção BCD ou flash.
3. Testar a opção BIOS `AVX3` isoladamente e repetir o CPUID.
4. Inicializar Linux e coletar todos os `IA32_VMX_*` por LP.
5. Se ainda necessário, testar xAPIC legado/IOMMU/posted interrupts/IPI
   virtualization, um por vez; não confundir esses isoladores com correções da
   MADT.
6. Configurar KDNET/depuração do hipervisor com um segundo computador. Sem
   dump, esse é o caminho para mapear a exceção e distinguir VM-entry, MSR,
   AP startup, APIC, IOMMU, EPT ou machine check.
7. Considerar Windows 10 22H2 ou Windows 11 23H2 em SSD separado somente como
   bisect de geração do Hyper-V, sem alterar a instalação principal.
8. Gravar a candidata MADT somente se houver evidência causal clara e depois
   de validar programador, tensão do chip e restauração externa.

## Perguntas abertas para o próximo analista/modelo

1. A correção MADT altera causalmente o modo de falha, ou isso vem apenas do
   OpenCore/memory map UEFI?
2. Qual binário contém o endereço de exceção nas três inicializações? É
   `winload`, `hvloader`, `hvix64`, kernel/HAL ou outro módulo?
3. É possível obter uma captura pré-kernel/hipervisor por KDNET nesta NIC
   Realtek `10EC:8168` sem depender do dump local?
4. A combinação órfã `AVX512_VP2INTERSECT` pode quebrar normalização
   CPUID/XSTATE do Hyper-V antes da partição raiz?
5. Algum `IA32_VMX_*` do stepping D0 difere dos requisitos usados pelo
   `hvix64.exe` atual?
6. Existe outra inconsistência entre MADT, DMAR, namespace ACPI e topologia que
   o Linux ignora, mas o Hyper-V consome?
7. Há maneira segura de desabilitar a exposição incorreta de VP2INTERSECT no
   firmware, sem spoof de stepping e sem transplantar módulos de outra placa?

## Arquivos importantes

- `analysis/RELATORIO_APROFUNDADO.md`: análise estática detalhada anterior aos
  testes reais.
- `analysis/OPENCORE_MADT_TEST.md`: construção e protocolo OpenCore.
- `analysis/PROXIMOS_TESTES_HYPER_V.md`: plano original; parte da ordem está
  superada pelos resultados deste README.
- `analysis/HIPER_V_MATRIZ_TESTES.md`: opções BCD preparadas.
- `analysis/HIPER_V_DEPURACAO_FUTURA.md`: plano KDNET.
- `analysis/acpi-runtime/`: tabelas ACPI runtime originais.
- `analysis/acpi-after-opencore-patch.dat`: MADT corrigida realmente entregue
  ao Windows.
- `analysis/cpuid-windows-current.json`: CPUID por LP.
- `analysis/hyperv-root-driver-inventory.json`: inventário dos drivers
  Microsoft.
- `analysis/runtime-dump-2026-08-24/`: extração estruturada do dump original.
- `analysis/candidates/`: candidata MADT e relatório.
- `analysis/bcd-backups/`: backups e manifestos dos testes.
- `analysis/scripts/`: coletores e scripts reversíveis.

## Regras de segurança para continuidade

- Não gravar BIOS enquanto o controle causal estiver pendente.
- Não usar reset repetidamente durante programação SPI.
- Antes de flash externo, identificar se o chip é 1,8 V ou 3,3 V.
- Fazer no mínimo três leituras externas idênticas e comparar com o dump FPT.
- Testar leitura, apagamento, gravação e verificação do dump original antes da
  candidata.
- Nunca apagar `{current}` nem ativar Hyper-V nele.
- Agendar somente uma entrada de teste por vez.
- Confirmar `bootsequence` antes de reiniciar e removê-la se o teste for
  adiado.
- Após qualquer falha, iniciar pelo caminho interno seguro e coletar evidências
  antes de preparar outro teste.
