# Falha de inicialização do Hyper-V

## Sintoma

Na HM570 com Tiger Lake-H ES `806D0`, o Windows inicia normalmente quando o
hipervisor não é lançado. Com a configuração Hyper-V baseline, a máquina
reinicia cedo no boot, registra Kernel-Power 41 e não produz minidump útil.

## Isolamento reproduzido

Em 26/08/2026 foi executada uma sequência A/B/A:

1. `HV06 PASS 1`: `hypervisorlaunchtype Auto`,
   `hypervisorloadoptions DISABLEHARDWAREMBEC`, XSAVE normal. Hyper-V presente,
   AVX e AVX2 executados com sucesso, WSL2 funcional.
2. `HV01 baseline FAIL`: mesmo objetivo de boot, sem o isolador MBEC. Reinício
   durante o boot, Kernel-Power 41 e nenhum minidump.
3. `HV06 PASS 2`: reaplicação do isolador MBEC. O resultado positivo se repetiu.

Artefatos: [`PASS 1`](../evidence/boot/hv06-mbec-working-pass1/),
[`baseline`](../evidence/boot/hv01-baseline-failure-20260826/) e
[`PASS 2`](../evidence/boot/hv06-mbec-working/).

## Interpretação

O resultado condiciona a falha ao caminho de MBEC por hardware usado durante o
lançamento do Hyper-V. Não prova ainda qual camada viola o contrato: silício ES,
microcode, firmware ou código/política do Hyper-V.

Um isolador anterior, `xsavedisable=1`, também permitiu iniciar o Hyper-V, mas
removeu XSAVE, AVX e AVX2 do ambiente Windows. Isso mostra que alterar o caminho
global de XSTATE evita a falha, porém não identifica sozinho o gatilho. Como
`DISABLEHARDWAREMBEC` preserva XSAVE e AVX/AVX2, ele é o workaround mínimo atual.

## Hipóteses relacionadas

- O firmware contém uma inconsistência MADT nos UIDs de Local APIC NMI. A tabela
  corrigida foi entregue ao Windows por OpenCore e não resolveu a falha.
- O CPUID bare-metal anuncia `AVX512_VP2INTERSECT` sem AVX512F/VL e sem os
  componentes XSTATE correspondentes. A anomalia existe, mas não foi provada
  como causa única.
- Os MSRs VMX coletados anunciam MBEC e XSAVES de forma homogênea entre LPs. Um
  bit permitido não comprova, por si só, que a combinação usada pelo Hyper-V
  funciona corretamente neste ES.

## Estado seguro

- VT-x/VT-d permanecem habilitados na BIOS.
- A entrada normal, com `hypervisorlaunchtype Off`, continua sendo o default.
- A entrada Hyper-V fallback usa `DISABLEHARDWAREMBEC`, sem `xsavedisable`.
- Nenhuma imagem de firmware modificada está aprovada para flash.

Consulte [`workaround.md`](workaround.md) para os scripts BCD e
[`investigation-next.md`](investigation-next.md) para a investigação restante.
