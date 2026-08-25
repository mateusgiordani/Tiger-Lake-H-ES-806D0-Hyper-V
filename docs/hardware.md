# Coleta de MSRs VMX no Ubuntu (NVMe separado)

## Objetivo

Fechar a principal lacuna que a anÃ¡lise estÃ¡tica nÃ£o consegue observar: os
valores reais de `IA32_VMX_*`, `IA32_FEATURE_CONTROL`, `IA32_APIC_BASE`,
microcode e MTRR em **todos os 16 processadores lÃ³gicos** do stepping D0.

Um Ãºnico AP com um controle VMX diferente jÃ¡ explica a falha precoce do
`hvix64.exe` durante o lanÃ§amento multiprocessador.

A inicializaÃ§Ã£o pelo bootloader prÃ³prio do Ubuntu nÃ£o passa pelo Windows Boot
Manager, portanto nenhum `bootsequence` pendente do BCD Ã© executado nesse
caminho.

## Arquivos

- `archive/experiments/legacy-scripts/collect_tgl_vmx_msrs_linux.py` â€” coletor somente leitura
  (jÃ¡ existente; compara todos os LPs online);
- `archive/experiments/legacy-scripts/run-in-ubuntu.sh` â€” novo empacotador que roda o coletor e
  junta, na mesma sessÃ£o: topologia (`lscpu`, `/proc/cpuinfo`), microcode por
  CPU, `dmesg` filtrado, `dmidecode` e, se `acpica-tools` estiver instalado,
  um dump das tabelas ACPI vistas pelo Linux.

## Passo a passo na sessÃ£o Ubuntu

O projeto do Windows pode ser acessado montando a NVMe do Windows. Se ela
montar como somente leitura (Fast Startup do Windows ativo), copie os dois
arquivos abaixo para `~/` e rode lÃ¡; sÃ³ o `.tar.gz` final precisa voltar.

```bash
cd /caminho/montado/projeto conserto bios/bios-interposer/archive/experiments/scripts
sudo bash run-in-ubuntu.sh
```

O script cria `tgl-linux-evidence-AAAAMMDD-HHMMSS.tar.gz` no diretÃ³rio atual.
Nada Ã© escrito fora dele. NÃ£o hÃ¡ necessidade de internet.

### Opcional, mas barato

```bash
sudo apt install acpica-tools   # habilita o dump ACPI do passo do script
```

## Protocolo de duas coletas (VMX ligado Ã— desligado)

1. **Primeira coleta com a configuraÃ§Ã£o atual (VMX habilitado)** â€” Ã© o estado
   em que o Hyper-V falha; este Ã© o dado principal e nÃ£o deve ser misturado
   com nenhuma mudanÃ§a de Setup. Renomear logo apÃ³s o script:
   ```bash
   mv tgl-linux-evidence-*.tar.gz tgl-linux-evidence-vmx-ON.tar.gz
   ```
2. **Segunda coleta com VMX desabilitado**: no Setup AMI, alterar **somente**
   a opÃ§Ã£o de virtualizaÃ§Ã£o da Intel (VMX). NÃ£o tocar em VT-d, Hyper-Threading,
   contagem de nÃºcleos ou `AVX3`. Anotar o menu/pÃ¡gina exata da opÃ§Ã£o.
   Repetir o mesmo script e renomear:
   ```bash
   mv tgl-linux-evidence-*.tar.gz tgl-linux-evidence-vmx-OFF.tar.gz
   ```
3. **Restaurar VMX = habilitado** antes de qualquer teste seguinte no
   Windows/Hyper-V.

O que a segunda coleta separa: uma desabilitaÃ§Ã£o limpa (CPUID sem o bit VMX,
`IA32_FEATURE_CONTROL` travada com `vmx_outside_smx=0`) de uma desabilitaÃ§Ã£o
incompleta no estilo da mÃ¡scara AVX-512 jÃ¡ encontrada (bit Ã³rfÃ£o). Os MSRs
`IA32_VMX_*` normalmente permanecem legÃ­veis por RDMSR mesmo com VMX
desabilitado; qualquer diferenÃ§a neles entre as duas passagens, fora
`IA32_FEATURE_CONTROL` e derivados de CPUID, Ã© achado relevante. Comparar
tambÃ©m se MADT/DMAR mudam entre os dois dumps ACPI.

## De volta ao Windows

AtenÃ§Ã£o: o primeiro boot de volta pelo Windows Boot Manager pode executar o
`bootsequence` Ãºnico ainda agendado (`Windows - HYPERV OPENCORE CONTROL`),
caso o controle nÃ£o tenha sido executado nem cancelado. Decidir antes:
observar o resultado ou cancelar com
`bcdedit /bootsequence "{5cbe73ca-b469-11f0-9ffb-c2e7dda09ff1}" /remove`.

Copiar o `.tar.gz` para:

```text
evidence/msr/linux/
```

A anÃ¡lise comparativa (controles VMX contra os requisitos conhecidos do
`hvix64.exe` e contra Tiger Lake-H de produÃ§Ã£o 06-8d-01) vem depois, sem
reiniciar o Windows pelo caminho do teste enquanto o estado do BCD nÃ£o for
confirmado.

## InterpretaÃ§Ã£o esperada

- `identical_msr_groups` deve listar exatamente um grupo com os 16 CPUs;
  dois grupos ou um LP isolado = achado direto.
- `IA32_FEATURE_CONTROL`: `locked=1` e `vmx_outside_smx=1` em todos os LPs.
- `IA32_APIC_BASE`: BSP apenas no CPU 0; `x2apic_enabled` reflete o modo em
  que o Linux deixou o APIC (o valor em si nÃ£o Ã© defeito).
- `IA32_VMX_EPT_VPID_CAP`: ausÃªncia de `execute_only_ept` ou de pÃ¡ginas de
  1 GiB Ã© compatÃ­vel com parte da famÃ­lia, mas relevante para o Hyper-V.
- Qualquer `error` em `per_cpu` indica MSR que falta ou trava leitura no D0;
  registrar qual Ã­ndice foi.
