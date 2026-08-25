# Coleta de MSRs VMX no Ubuntu (NVMe separado)

## Objetivo

Fechar a principal lacuna que a análise estática não consegue observar: os
valores reais de `IA32_VMX_*`, `IA32_FEATURE_CONTROL`, `IA32_APIC_BASE`,
microcode e MTRR em **todos os 16 processadores lógicos** do stepping D0.

Um único AP com um controle VMX diferente já explica a falha precoce do
`hvix64.exe` durante o lançamento multiprocessador.

A inicialização pelo bootloader próprio do Ubuntu não passa pelo Windows Boot
Manager, portanto nenhum `bootsequence` pendente do BCD é executado nesse
caminho.

## Arquivos

- `archive/experiments/legacy-scripts/collect_tgl_vmx_msrs_linux.py` — coletor somente leitura
  (já existente; compara todos os LPs online);
- `archive/experiments/legacy-scripts/run-in-ubuntu.sh` — novo empacotador que roda o coletor e
  junta, na mesma sessão: topologia (`lscpu`, `/proc/cpuinfo`), microcode por
  CPU, `dmesg` filtrado, `dmidecode` e, se `acpica-tools` estiver instalado,
  um dump das tabelas ACPI vistas pelo Linux.

## Passo a passo na sessão Ubuntu

O projeto do Windows pode ser acessado montando a NVMe do Windows. Se ela
montar como somente leitura (Fast Startup do Windows ativo), copie os dois
arquivos abaixo para `~/` e rode lá; só o `.tar.gz` final precisa voltar.

```bash
cd /caminho/montado/projeto conserto bios/bios-interposer/archive/experiments/scripts
sudo bash run-in-ubuntu.sh
```

O script cria `tgl-linux-evidence-AAAAMMDD-HHMMSS.tar.gz` no diretório atual.
Nada é escrito fora dele. Não há necessidade de internet.

### Opcional, mas barato

```bash
sudo apt install acpica-tools   # habilita o dump ACPI do passo do script
```

## Protocolo de duas coletas (VMX ligado × desligado)

1. **Primeira coleta com a configuração atual (VMX habilitado)** — é o estado
   em que o Hyper-V falha; este é o dado principal e não deve ser misturado
   com nenhuma mudança de Setup. Renomear logo após o script:
   ```bash
   mv tgl-linux-evidence-*.tar.gz tgl-linux-evidence-vmx-ON.tar.gz
   ```
2. **Segunda coleta com VMX desabilitado**: no Setup AMI, alterar **somente**
   a opção de virtualização da Intel (VMX). Não tocar em VT-d, Hyper-Threading,
   contagem de núcleos ou `AVX3`. Anotar o menu/página exata da opção.
   Repetir o mesmo script e renomear:
   ```bash
   mv tgl-linux-evidence-*.tar.gz tgl-linux-evidence-vmx-OFF.tar.gz
   ```
3. **Restaurar VMX = habilitado** antes de qualquer teste seguinte no
   Windows/Hyper-V.

O que a segunda coleta separa: uma desabilitação limpa (CPUID sem o bit VMX,
`IA32_FEATURE_CONTROL` travada com `vmx_outside_smx=0`) de uma desabilitação
incompleta no estilo da máscara AVX-512 já encontrada (bit órfão). Os MSRs
`IA32_VMX_*` normalmente permanecem legíveis por RDMSR mesmo com VMX
desabilitado; qualquer diferença neles entre as duas passagens, fora
`IA32_FEATURE_CONTROL` e derivados de CPUID, é achado relevante. Comparar
também se MADT/DMAR mudam entre os dois dumps ACPI.

## De volta ao Windows

Atenção: o primeiro boot de volta pelo Windows Boot Manager pode executar o
`bootsequence` único ainda agendado (`Windows - HYPERV OPENCORE CONTROL`),
caso o controle não tenha sido executado nem cancelado. Decidir antes:
observar o resultado ou cancelar com
`bcdedit /bootsequence "{5cbe73ca-b469-11f0-9ffb-c2e7dda09ff1}" /remove`.

Copiar o `.tar.gz` para:

```text
evidence/msr/linux/
```

A análise comparativa (controles VMX contra os requisitos conhecidos do
`hvix64.exe` e contra Tiger Lake-H de produção 06-8d-01) vem depois, sem
reiniciar o Windows pelo caminho do teste enquanto o estado do BCD não for
confirmado.

## Interpretação esperada

- `identical_msr_groups` deve listar exatamente um grupo com os 16 CPUs;
  dois grupos ou um LP isolado = achado direto.
- `IA32_FEATURE_CONTROL`: `locked=1` e `vmx_outside_smx=1` em todos os LPs.
- `IA32_APIC_BASE`: BSP apenas no CPU 0; `x2apic_enabled` reflete o modo em
  que o Linux deixou o APIC (o valor em si não é defeito).
- `IA32_VMX_EPT_VPID_CAP`: ausência de `execute_only_ept` ou de páginas de
  1 GiB é compatível com parte da família, mas relevante para o Hyper-V.
- Qualquer `error` em `per_cpu` indica MSR que falta ou trava leitura no D0;
  registrar qual índice foi.
