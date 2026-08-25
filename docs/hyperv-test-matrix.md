# Matriz de diagnÃ³stico do boot do Hyper-V

## Estado atual

Nenhum teste desta matriz foi aplicado. Os scripts sÃ£o `dry-run` por padrÃ£o e nÃ£o habilitam recursos opcionais do Windows, nÃ£o alteram a BIOS e nÃ£o reiniciam a mÃ¡quina.

O objetivo Ã© descobrir em qual contrato de plataforma o hipervisor falha antes de gravar uma BIOS modificada. A entrada atual do Windows permanece como padrÃ£o, com `hypervisorlaunchtype off`; todas as entradas perigosas exigem escolha manual no menu.

## PreparaÃ§Ã£o, somente quando houver janela para reiniciar

1. Salvar a chave de recuperaÃ§Ã£o do BitLocker. O script se recusa a alterar o BCD se a proteÃ§Ã£o do volume do sistema estiver ativa.
2. Confirmar que `{current}` inicia normalmente com Hyper-V desligado.
3. Se o recurso do Hyper-V ainda nÃ£o estiver instalado, habilitÃ¡-lo com **sem reiniciar**. A criaÃ§Ã£o do BCD deve ser feita antes do primeiro boot com o recurso ligado.
4. Abrir PowerShell como Administrador.
5. Conferir primeiro o `dry-run`:

   ```powershell
   & 'archive\experiments\legacy-scripts\prepare-hyperv-diagnostic-matrix.ps1'
   ```

6. Quando estiver pronto para a janela de testes:

   ```powershell
   & 'archive\experiments\legacy-scripts\prepare-hyperv-diagnostic-matrix.ps1' -Apply
   ```

O script exporta o BCD, cria um manifesto JSON com todos os GUIDs, mantÃ©m `{current}` como padrÃ£o seguro e mostra um menu por 15 segundos. Ele nÃ£o agenda uma entrada de teste para o prÃ³ximo boot.

## Ordem recomendada

Antes desta matriz, prefira o patch MADT em memÃ³ria descrito em `OPENCORE_MADT_TEST.md`. Ele testa a candidata de BIOS sem flash e possui um controle negativo com a mesma cadeia OpenCore. A matriz continua Ãºtil se o patch isolado falhar ou revelar uma segunda condiÃ§Ã£o necessÃ¡ria.

A matriz tem duas ondas. NÃ£o Ã© necessÃ¡rio testar uma entrada novamente depois de um reset.

### Onda 1: maior poder de separaÃ§Ã£o

| Ordem | Entrada | O que isola | InterpretaÃ§Ã£o se iniciar |
|---:|---|---|---|
| 1 | `HV 08 CAPTURA BOOTLOG` | Distingue reset prÃ©-kernel de falha durante drivers | `ntbtlog.txt` atualizado ou bugcheck visÃ­vel prova que o kernel comeÃ§ou; ausÃªncia reforÃ§a falha dentro de `hvix64` |
| 2 | `HV 05 MINIMO` | 1 CPU, xAPIC legado e IOMMU desligada | O VMX bÃ¡sico funciona; a falha estÃ¡ em SMP/APIC/IOMMU, nÃ£o no primeiro VMXON |
| 3 | `HV 04 UM LP` | InicializaÃ§Ã£o dos processadores auxiliares | Forte evidÃªncia de falha no bring-up dos APs, topologia ou MADT |
| 4 | `HV 09 SEM vAPIC` | Rota de virtual-APIC selecionada pelo loader | Direciona para APIC virtualization, separada do modo x2APIC |
| 5 | `HV 10 SEM POSTED INT` | InterrupÃ§Ãµes postadas de VMX/VT-d | Direciona para posted interrupts ou interrupt remapping |
| 6 | `HV 11 SEM IPI VIRTUAL` | VirtualizaÃ§Ã£o de IPI | Direciona para a entrega de IPIs e bring-up dos APs |
| 7 | `HV 03 xAPIC LEGADO` | x2APIC e modo APIC estendido | Direciona para a transiÃ§Ã£o x2APIC do hipervisor |
| 8 | `HV 13 APIC DEST FISICO` | Destino lÃ³gico versus fÃ­sico | Direciona para roteamento de interrupÃ§Ãµes/APIC IDs |
| 9 | `HV 02 SEM IOMMU` | DMAR, VT-d e interrupt remapping | Direciona para DMAR/VT-d, mesmo com a tabela aparentemente coerente |
| 10 | `HV 12 SEM SLAT EPT` | EPT/SLAT | Direciona para controles VMX de EPT do stepping ES |
| 11 | `HV 06 SEM MBEC HW` | Caminho de MBEC por hardware | Direciona para enumeraÃ§Ã£o CPUID/VMX de MBEC do ES |
| 12 | `HV 07 SEM XSAVE` | Estado estendido XSAVE/XSTATE | Direciona para a combinaÃ§Ã£o CPUID/XSTATE incoerente do ES |
| 13 | `HV 14 SCHED CLASSICO` | Scheduler Core e topologia SMT | Direciona para a interpretaÃ§Ã£o de threads/cores pelo scheduler |

### Onda 2: opÃ§Ãµes internas experimentais

| Ordem | Entrada | O que isola |
|---:|---|---|
| 14 | `HV 15 SEM IOMMU HANDOFF` | Handoff de estado VT-d entre firmware/loader/hipervisor |
| 15 | `HV 16 IOMMU NAO ESCALAVEL` | Caminho de IOMMU escalÃ¡vel |
| 16 | `HV 17 TEMPO PMTIMER` | Fonte de tempo TSC versus ACPI PM Timer |
| 17 | `HV 18 SINCRONIZA TSC` | Skew de TSC durante o inÃ­cio dos LPs |
| 18 | `HV 01 BASELINE` | Controle positivo do bootloop conhecido |

ApÃ³s selecionar uma entrada e ocorrer reset, nÃ£o a selecione novamente. Aguarde o menu e deixe a entrada padrÃ£o iniciar. Anote para cada teste: chegou ao logotipo, girou os pontos, reiniciou instantaneamente, congelou, gerou bugcheck ou iniciou completamente.

Depois de `HV 08 CAPTURA BOOTLOG`, jÃ¡ no boot seguro, confira:

```powershell
Get-Item C:\Windows\ntbtlog.txt -ErrorAction SilentlyContinue | Select-Object Length,LastWriteTime
Get-Content C:\Windows\ntbtlog.txt -Tail 80 -ErrorAction SilentlyContinue
```

Se o arquivo nÃ£o existir ou conservar o horÃ¡rio anterior, nenhum driver `.sys` foi registrado naquele boot. Se houver bugcheck visÃ­vel, fotografe o cÃ³digo e os quatro parÃ¢metros; `nocrashautoreboot=yes` impede que a tela desapareÃ§a imediatamente.

O manifesto salva o estado anterior do `ntbtlog.txt`. Depois de voltar pela entrada segura, o coletor abaixo registra a comparaÃ§Ã£o, os Ãºltimos eventos Kernel-Power/bugcheck, o microcode e a chave Hypervisor sem modificar o sistema:

```powershell
& 'archive\experiments\legacy-scripts\collect-hyperv-postboot-evidence.ps1' `
  -ManifestPath 'evidence\boot\bcd-backups\hyperv-matrix-AAAAMMDD-HHMMSS.json' `
  -SelectedEntry 'HV 08 CAPTURA BOOTLOG'
```

## Eixo Microsoft adicional: `IgnoreMemPart`

O Registro atual contÃ©m somente um valor na chave `HKLM\SYSTEM\CurrentControlSet\Control\Hypervisor`: `IgnoreMemPart=1`. A engenharia reversa do `hvloader.dll` instalado confirmou que ele lÃª esse DWORD dentro de `HvlLoadHypervisor`/`HvlPreloadHypervisor`. Quando o valor Ã© diferente de zero no ambiente normal de boot, o carregador ignora a abertura de `\KernelObjects\MemoryPartitionHypervisorMetadata`.

Esse valor nÃ£o Ã© documentado publicamente pela Microsoft e pode ser uma compatibilidade deliberada do prÃ³prio Windows. Por isso ele **nÃ£o** faz parte das sete entradas iniciais e nÃ£o deve ser alterado junto com outra variÃ¡vel. Se nenhuma entrada da matriz iniciar, o teste secundÃ¡rio Ã© definir temporariamente `IgnoreMemPart=0`, selecionar apenas `HV 05 MINIMO` e depois restaurar o valor original.

Os scripts sÃ£o `dry-run` por padrÃ£o, exportam a chave inteira e nÃ£o reiniciam:

```powershell
& 'archive\experiments\legacy-scripts\prepare-hyperv-ignoremempart-test.ps1'
& 'archive\experiments\legacy-scripts\prepare-hyperv-ignoremempart-test.ps1' -Apply
& 'archive\experiments\legacy-scripts\restore-hyperv-ignoremempart-test.ps1' -ManifestPath '.\archive\experiments\registry-backups\ignoremempart-test-AAAAMMDD-HHMMSS.json'
& 'archive\experiments\legacy-scripts\restore-hyperv-ignoremempart-test.ps1' -ManifestPath '.\archive\experiments\registry-backups\ignoremempart-test-AAAAMMDD-HHMMSS.json' -Apply
```

Esse experimento Ã© global para o carregador, nÃ£o por entrada BCD. A proteÃ§Ã£o continua sendo `{current}` com Hyper-V desligado como padrÃ£o. Resultado positivo apontaria para a negociaÃ§Ã£o da partiÃ§Ã£o de metadados do hipervisor; resultado negativo apenas elimina esse desvio local, sem justificar deixÃ¡-lo em zero.

## Ãrvore de decisÃ£o

- `MINIMO` inicia, mas todos os outros falham: testar separadamente BIOS com VT-d desligado, X2APIC Opt Out ligado e apenas um nÃºcleo ativo.
- `UM LP` inicia: priorizar MADT/topologia/AP bring-up; o patch dos NMI UIDs vira o candidato principal.
- `SEM vAPIC`, `SEM POSTED INT` ou `SEM IPI VIRTUAL` inicia: a falha estÃ¡ no conjunto APICv/interrupt delivery do ES; manter a opÃ§Ã£o vencedora como workaround temporÃ¡rio e sÃ³ entÃ£o decidir entre configuraÃ§Ã£o permanente ou patch de firmware.
- `xAPIC LEGADO` inicia: investigar APIC virtualization e x2APIC; testar `X2APIC Opt Out=1` na BIOS antes de alterar cÃ³digo.
- `APIC DEST FISICO` inicia: a numeraÃ§Ã£o intercalada dos APIC IDs ou o destino lÃ³gico Ã© o gatilho; o patch MADT ganha prioridade.
- `SEM IOMMU` inicia: produzir uma variante de BIOS que omita/corrija DMAR ou desabilite VT-d, em vez de tocar no microcode.
- `SEM SLAT EPT` inicia: coletar `IA32_VMX_EPT_VPID_CAP` no Linux e comparar com Tiger Lake D1; nÃ£o usar o modo sem EPT como soluÃ§Ã£o de desempenho sem medir.
- `SEM MBEC HW` inicia: coletar os MSRs VMX e comparar com Tiger Lake-H D1; nÃ£o mascarar CPUID ainda.
- `SEM XSAVE` inicia: priorizar a opÃ§Ã£o AVX3 e a mÃ¡scara CPUID/XSTATE do firmware; nÃ£o manter XSAVE desabilitado como soluÃ§Ã£o permanente.
- `SCHED CLASSICO` inicia: repetir com Hyper-Threading desligado; o problema Ã© topologia/scheduler, nÃ£o um driver fÃ­sico.
- `TEMPO PMTIMER` ou `SINCRONIZA TSC` inicia: medir TSC por LP no Linux e capturar o diagnÃ³stico `TscSync` pelo depurador antes de qualquer patch.
- Nem `MINIMO` inicia: a falha Ã© compatÃ­vel com VMX/MSR do stepping ES, estado de CPU no BSP ou MADT usada antes do kernel. Nesse caso o prÃ³ximo dado obrigatÃ³rio Ã© a coleta de MSRs no Linux e, se possÃ­vel, depuraÃ§Ã£o do hipervisor por KDNET/serial.

O plano de captura com um segundo PC estÃ¡ em `docs/hyperv-debugging.md`. O Ethernet fÃ­sico Realtek `10EC:8168` desta placa consta na lista oficial de NICs KDNET; a ferramenta ainda nÃ£o estÃ¡ instalada e nenhuma configuraÃ§Ã£o de depuraÃ§Ã£o foi aplicada.

Como bisect final de software, pode-se usar um SSD separado com imagem oficial do Windows 10 22H2 ou Windows 11 23H2, sem tocar no disco atual. Isso sÃ³ vem depois dos isoladores: uma versÃ£o antiga que inicie indicaria mudanÃ§a de validaÃ§Ã£o do hipervisor; todas falharem reforÃ§aria o contrato defeituoso do ES/firmware.

## Testes reversÃ­veis de BIOS antes de qualquer flash modificado

Fazer um por vez, sempre restaurando o valor anterior:

1. `AVX3 disable flag = 0` (habilitar AVX-512) e repetir o dump CPUID. Hoje o firmware deixa AVX-512 desabilitado, mas preserva isoladamente `AVX512_VP2INTERSECT`, combinaÃ§Ã£o incoerente.
2. `VT-d global = 0`.
3. `X2APIC Opt Out = 1`.
4. Hyper-Threading desligado.
5. Um nÃºcleo ativo.

O teste AVX3 precisa vir acompanhado de novo CPUID. O resultado esperado para uma enumeraÃ§Ã£o coerente Ã©: ou AVX-512F/VL, estados XCR0 5â€“7 e VP2INTERSECT aparecem juntos, ou todos os bits AVX-512 ficam ocultos.

## Coleta VMX no Linux

O script Ã© somente leitura e compara todos os processadores lÃ³gicos:

```bash
sudo modprobe msr
sudo python3 collect_tgl_vmx_msrs_linux.py > tgl-vmx-msrs.json
```

Arquivo: `archive/experiments/legacy-scripts/collect_tgl_vmx_msrs_linux.py`.

Ele coleta `IA32_FEATURE_CONTROL`, APIC base, microcode, MTRR e `IA32_VMX_*` de cada LP. Uma diferenÃ§a em apenas um AP, um controle VMX nÃ£o arquitetural ou ausÃªncia de MBEC/APIC virtualization pode explicar o reset durante o lanÃ§amento multiprocessador.

## RemoÃ§Ã£o da matriz

Usar o manifesto JSON criado pelo script:

```powershell
& 'archive\experiments\legacy-scripts\remove-hyperv-diagnostic-matrix.ps1' -ManifestPath 'evidence\boot\bcd-backups\hyperv-matrix-AAAAMMDD-HHMMSS.json'
& 'archive\experiments\legacy-scripts\remove-hyperv-diagnostic-matrix.ps1' -ManifestPath 'evidence\boot\bcd-backups\hyperv-matrix-AAAAMMDD-HHMMSS.json' -Apply
```

A primeira linha apenas mostra o que seria removido. A segunda remove somente os GUIDs registrados e faz outro backup do BCD antes de comeÃ§ar.

## Limites de seguranÃ§a

- NÃ£o editar nem substituir `hvix64.exe` ou `hvloader.dll`: ambos sÃ£o assinados e executados antes do kernel; alterar esses binÃ¡rios quebra a cadeia de confianÃ§a e nÃ£o corrige o contrato defeituoso da plataforma.
- NÃ£o deixar `IgnoreMemPart=0` depois do experimento: restaurar o valor original `1` pelo manifesto, mesmo se o teste continuar em bootloop.
- NÃ£o tentar transformar CPUID `806D0` em `806D1` por ACPI. Family/model/stepping vÃªm da instruÃ§Ã£o CPUID; um spoof real exigiria microcode ou uma camada anterior de virtualizaÃ§Ã£o e poderia aplicar MSRs/erratas errados.
- NÃ£o gravar a candidata MADT antes das trÃªs leituras externas idÃªnticas, confirmaÃ§Ã£o de tensÃ£o do chip e recuperaÃ§Ã£o validada com o dump original.
