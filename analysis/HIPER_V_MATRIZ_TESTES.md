# Matriz de diagnóstico do boot do Hyper-V

## Estado atual

Nenhum teste desta matriz foi aplicado. Os scripts são `dry-run` por padrão e não habilitam recursos opcionais do Windows, não alteram a BIOS e não reiniciam a máquina.

O objetivo é descobrir em qual contrato de plataforma o hipervisor falha antes de gravar uma BIOS modificada. A entrada atual do Windows permanece como padrão, com `hypervisorlaunchtype off`; todas as entradas perigosas exigem escolha manual no menu.

## Preparação, somente quando houver janela para reiniciar

1. Salvar a chave de recuperação do BitLocker. O script se recusa a alterar o BCD se a proteção do volume do sistema estiver ativa.
2. Confirmar que `{current}` inicia normalmente com Hyper-V desligado.
3. Se o recurso do Hyper-V ainda não estiver instalado, habilitá-lo com **sem reiniciar**. A criação do BCD deve ser feita antes do primeiro boot com o recurso ligado.
4. Abrir PowerShell como Administrador.
5. Conferir primeiro o `dry-run`:

   ```powershell
   & '.\analysis\scripts\prepare-hyperv-diagnostic-matrix.ps1'
   ```

6. Quando estiver pronto para a janela de testes:

   ```powershell
   & '.\analysis\scripts\prepare-hyperv-diagnostic-matrix.ps1' -Apply
   ```

O script exporta o BCD, cria um manifesto JSON com todos os GUIDs, mantém `{current}` como padrão seguro e mostra um menu por 15 segundos. Ele não agenda uma entrada de teste para o próximo boot.

## Ordem recomendada

Antes desta matriz, prefira o patch MADT em memória descrito em `OPENCORE_MADT_TEST.md`. Ele testa a candidata de BIOS sem flash e possui um controle negativo com a mesma cadeia OpenCore. A matriz continua útil se o patch isolado falhar ou revelar uma segunda condição necessária.

A matriz tem duas ondas. Não é necessário testar uma entrada novamente depois de um reset.

### Onda 1: maior poder de separação

| Ordem | Entrada | O que isola | Interpretação se iniciar |
|---:|---|---|---|
| 1 | `HV 08 CAPTURA BOOTLOG` | Distingue reset pré-kernel de falha durante drivers | `ntbtlog.txt` atualizado ou bugcheck visível prova que o kernel começou; ausência reforça falha dentro de `hvix64` |
| 2 | `HV 05 MINIMO` | 1 CPU, xAPIC legado e IOMMU desligada | O VMX básico funciona; a falha está em SMP/APIC/IOMMU, não no primeiro VMXON |
| 3 | `HV 04 UM LP` | Inicialização dos processadores auxiliares | Forte evidência de falha no bring-up dos APs, topologia ou MADT |
| 4 | `HV 09 SEM vAPIC` | Rota de virtual-APIC selecionada pelo loader | Direciona para APIC virtualization, separada do modo x2APIC |
| 5 | `HV 10 SEM POSTED INT` | Interrupções postadas de VMX/VT-d | Direciona para posted interrupts ou interrupt remapping |
| 6 | `HV 11 SEM IPI VIRTUAL` | Virtualização de IPI | Direciona para a entrega de IPIs e bring-up dos APs |
| 7 | `HV 03 xAPIC LEGADO` | x2APIC e modo APIC estendido | Direciona para a transição x2APIC do hipervisor |
| 8 | `HV 13 APIC DEST FISICO` | Destino lógico versus físico | Direciona para roteamento de interrupções/APIC IDs |
| 9 | `HV 02 SEM IOMMU` | DMAR, VT-d e interrupt remapping | Direciona para DMAR/VT-d, mesmo com a tabela aparentemente coerente |
| 10 | `HV 12 SEM SLAT EPT` | EPT/SLAT | Direciona para controles VMX de EPT do stepping ES |
| 11 | `HV 06 SEM MBEC HW` | Caminho de MBEC por hardware | Direciona para enumeração CPUID/VMX de MBEC do ES |
| 12 | `HV 07 SEM XSAVE` | Estado estendido XSAVE/XSTATE | Direciona para a combinação CPUID/XSTATE incoerente do ES |
| 13 | `HV 14 SCHED CLASSICO` | Scheduler Core e topologia SMT | Direciona para a interpretação de threads/cores pelo scheduler |

### Onda 2: opções internas experimentais

| Ordem | Entrada | O que isola |
|---:|---|---|
| 14 | `HV 15 SEM IOMMU HANDOFF` | Handoff de estado VT-d entre firmware/loader/hipervisor |
| 15 | `HV 16 IOMMU NAO ESCALAVEL` | Caminho de IOMMU escalável |
| 16 | `HV 17 TEMPO PMTIMER` | Fonte de tempo TSC versus ACPI PM Timer |
| 17 | `HV 18 SINCRONIZA TSC` | Skew de TSC durante o início dos LPs |
| 18 | `HV 01 BASELINE` | Controle positivo do bootloop conhecido |

Após selecionar uma entrada e ocorrer reset, não a selecione novamente. Aguarde o menu e deixe a entrada padrão iniciar. Anote para cada teste: chegou ao logotipo, girou os pontos, reiniciou instantaneamente, congelou, gerou bugcheck ou iniciou completamente.

Depois de `HV 08 CAPTURA BOOTLOG`, já no boot seguro, confira:

```powershell
Get-Item C:\Windows\ntbtlog.txt -ErrorAction SilentlyContinue | Select-Object Length,LastWriteTime
Get-Content C:\Windows\ntbtlog.txt -Tail 80 -ErrorAction SilentlyContinue
```

Se o arquivo não existir ou conservar o horário anterior, nenhum driver `.sys` foi registrado naquele boot. Se houver bugcheck visível, fotografe o código e os quatro parâmetros; `nocrashautoreboot=yes` impede que a tela desapareça imediatamente.

O manifesto salva o estado anterior do `ntbtlog.txt`. Depois de voltar pela entrada segura, o coletor abaixo registra a comparação, os últimos eventos Kernel-Power/bugcheck, o microcode e a chave Hypervisor sem modificar o sistema:

```powershell
& '.\analysis\scripts\collect-hyperv-postboot-evidence.ps1' `
  -ManifestPath '.\analysis\bcd-backups\hyperv-matrix-AAAAMMDD-HHMMSS.json' `
  -SelectedEntry 'HV 08 CAPTURA BOOTLOG'
```

## Eixo Microsoft adicional: `IgnoreMemPart`

O Registro atual contém somente um valor na chave `HKLM\SYSTEM\CurrentControlSet\Control\Hypervisor`: `IgnoreMemPart=1`. A engenharia reversa do `hvloader.dll` instalado confirmou que ele lê esse DWORD dentro de `HvlLoadHypervisor`/`HvlPreloadHypervisor`. Quando o valor é diferente de zero no ambiente normal de boot, o carregador ignora a abertura de `\KernelObjects\MemoryPartitionHypervisorMetadata`.

Esse valor não é documentado publicamente pela Microsoft e pode ser uma compatibilidade deliberada do próprio Windows. Por isso ele **não** faz parte das sete entradas iniciais e não deve ser alterado junto com outra variável. Se nenhuma entrada da matriz iniciar, o teste secundário é definir temporariamente `IgnoreMemPart=0`, selecionar apenas `HV 05 MINIMO` e depois restaurar o valor original.

Os scripts são `dry-run` por padrão, exportam a chave inteira e não reiniciam:

```powershell
& '.\analysis\scripts\prepare-hyperv-ignoremempart-test.ps1'
& '.\analysis\scripts\prepare-hyperv-ignoremempart-test.ps1' -Apply
& '.\analysis\scripts\restore-hyperv-ignoremempart-test.ps1' -ManifestPath '.\analysis\registry-backups\ignoremempart-test-AAAAMMDD-HHMMSS.json'
& '.\analysis\scripts\restore-hyperv-ignoremempart-test.ps1' -ManifestPath '.\analysis\registry-backups\ignoremempart-test-AAAAMMDD-HHMMSS.json' -Apply
```

Esse experimento é global para o carregador, não por entrada BCD. A proteção continua sendo `{current}` com Hyper-V desligado como padrão. Resultado positivo apontaria para a negociação da partição de metadados do hipervisor; resultado negativo apenas elimina esse desvio local, sem justificar deixá-lo em zero.

## Árvore de decisão

- `MINIMO` inicia, mas todos os outros falham: testar separadamente BIOS com VT-d desligado, X2APIC Opt Out ligado e apenas um núcleo ativo.
- `UM LP` inicia: priorizar MADT/topologia/AP bring-up; o patch dos NMI UIDs vira o candidato principal.
- `SEM vAPIC`, `SEM POSTED INT` ou `SEM IPI VIRTUAL` inicia: a falha está no conjunto APICv/interrupt delivery do ES; manter a opção vencedora como workaround temporário e só então decidir entre configuração permanente ou patch de firmware.
- `xAPIC LEGADO` inicia: investigar APIC virtualization e x2APIC; testar `X2APIC Opt Out=1` na BIOS antes de alterar código.
- `APIC DEST FISICO` inicia: a numeração intercalada dos APIC IDs ou o destino lógico é o gatilho; o patch MADT ganha prioridade.
- `SEM IOMMU` inicia: produzir uma variante de BIOS que omita/corrija DMAR ou desabilite VT-d, em vez de tocar no microcode.
- `SEM SLAT EPT` inicia: coletar `IA32_VMX_EPT_VPID_CAP` no Linux e comparar com Tiger Lake D1; não usar o modo sem EPT como solução de desempenho sem medir.
- `SEM MBEC HW` inicia: coletar os MSRs VMX e comparar com Tiger Lake-H D1; não mascarar CPUID ainda.
- `SEM XSAVE` inicia: priorizar a opção AVX3 e a máscara CPUID/XSTATE do firmware; não manter XSAVE desabilitado como solução permanente.
- `SCHED CLASSICO` inicia: repetir com Hyper-Threading desligado; o problema é topologia/scheduler, não um driver físico.
- `TEMPO PMTIMER` ou `SINCRONIZA TSC` inicia: medir TSC por LP no Linux e capturar o diagnóstico `TscSync` pelo depurador antes de qualquer patch.
- Nem `MINIMO` inicia: a falha é compatível com VMX/MSR do stepping ES, estado de CPU no BSP ou MADT usada antes do kernel. Nesse caso o próximo dado obrigatório é a coleta de MSRs no Linux e, se possível, depuração do hipervisor por KDNET/serial.

O plano de captura com um segundo PC está em `analysis/HIPER_V_DEPURACAO_FUTURA.md`. O Ethernet físico Realtek `10EC:8168` desta placa consta na lista oficial de NICs KDNET; a ferramenta ainda não está instalada e nenhuma configuração de depuração foi aplicada.

Como bisect final de software, pode-se usar um SSD separado com imagem oficial do Windows 10 22H2 ou Windows 11 23H2, sem tocar no disco atual. Isso só vem depois dos isoladores: uma versão antiga que inicie indicaria mudança de validação do hipervisor; todas falharem reforçaria o contrato defeituoso do ES/firmware.

## Testes reversíveis de BIOS antes de qualquer flash modificado

Fazer um por vez, sempre restaurando o valor anterior:

1. `AVX3 disable flag = 0` (habilitar AVX-512) e repetir o dump CPUID. Hoje o firmware deixa AVX-512 desabilitado, mas preserva isoladamente `AVX512_VP2INTERSECT`, combinação incoerente.
2. `VT-d global = 0`.
3. `X2APIC Opt Out = 1`.
4. Hyper-Threading desligado.
5. Um núcleo ativo.

O teste AVX3 precisa vir acompanhado de novo CPUID. O resultado esperado para uma enumeração coerente é: ou AVX-512F/VL, estados XCR0 5–7 e VP2INTERSECT aparecem juntos, ou todos os bits AVX-512 ficam ocultos.

## Coleta VMX no Linux

O script é somente leitura e compara todos os processadores lógicos:

```bash
sudo modprobe msr
sudo python3 collect_tgl_vmx_msrs_linux.py > tgl-vmx-msrs.json
```

Arquivo: `analysis/scripts/collect_tgl_vmx_msrs_linux.py`.

Ele coleta `IA32_FEATURE_CONTROL`, APIC base, microcode, MTRR e `IA32_VMX_*` de cada LP. Uma diferença em apenas um AP, um controle VMX não arquitetural ou ausência de MBEC/APIC virtualization pode explicar o reset durante o lançamento multiprocessador.

## Remoção da matriz

Usar o manifesto JSON criado pelo script:

```powershell
& '.\analysis\scripts\remove-hyperv-diagnostic-matrix.ps1' -ManifestPath '.\analysis\bcd-backups\hyperv-matrix-AAAAMMDD-HHMMSS.json'
& '.\analysis\scripts\remove-hyperv-diagnostic-matrix.ps1' -ManifestPath '.\analysis\bcd-backups\hyperv-matrix-AAAAMMDD-HHMMSS.json' -Apply
```

A primeira linha apenas mostra o que seria removido. A segunda remove somente os GUIDs registrados e faz outro backup do BCD antes de começar.

## Limites de segurança

- Não editar nem substituir `hvix64.exe` ou `hvloader.dll`: ambos são assinados e executados antes do kernel; alterar esses binários quebra a cadeia de confiança e não corrige o contrato defeituoso da plataforma.
- Não deixar `IgnoreMemPart=0` depois do experimento: restaurar o valor original `1` pelo manifesto, mesmo se o teste continuar em bootloop.
- Não tentar transformar CPUID `806D0` em `806D1` por ACPI. Family/model/stepping vêm da instrução CPUID; um spoof real exigiria microcode ou uma camada anterior de virtualização e poderia aplicar MSRs/erratas errados.
- Não gravar a candidata MADT antes das três leituras externas idênticas, confirmação de tensão do chip e recuperação validada com o dump original.
