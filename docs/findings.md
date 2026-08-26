# Findings consolidados

## Conclusão operacional

O controle A/B/A de 26/08/2026 é a evidência causal mais forte do projeto:

1. `HV06`, com `DISABLEHARDWAREMBEC`, iniciou Hyper-V e passou AVX, AVX2 e WSL2.
2. `HV01`, sem o isolador, reiniciou durante o boot e registrou Kernel-Power 41,
   sem minidump.
3. `HV06`, reaplicado sem outra mudança intencional, repetiu o resultado positivo.

Assim, a falha está condicionada ao caminho de MBEC por hardware no lançamento
do Hyper-V. A camada final responsável ainda não foi determinada.

## Matriz observada

| MBEC por hardware | XSAVE | Hyper-V | AVX/AVX2 |
|---|---|---|---|
| ativo | ativo | falha de boot | não testável nesse boot |
| desabilitado por load option | ativo | funciona | funcionam |
| ativo | globalmente desabilitado | funciona | indisponíveis |

MBEC e XSAVE são capacidades arquitetonicamente separadas. Os resultados mostram
que ambos alteram o caminho de inicialização problemático, não que sejam a mesma
função nem que uma inconsistência CPUID isolada já esteja provada como causa.

## Evidências preservadas

- [`evidence/boot/hv06-mbec-working-pass1/`](../evidence/boot/hv06-mbec-working-pass1/)
- [`evidence/boot/hv01-baseline-failure-20260826/`](../evidence/boot/hv01-baseline-failure-20260826/)
- [`evidence/boot/hv06-mbec-working/`](../evidence/boot/hv06-mbec-working/)
- [`evidence/cpuid/`](../evidence/cpuid/)
- [`evidence/msr/linux/`](../evidence/msr/linux/)

## Findings anteriores que continuam válidos

- A MADT original tem UIDs de Local APIC NMI inconsistentes; a correção entregue
  por OpenCore chegou ao Windows, mas não eliminou a falha.
- O CPUID bare-metal expõe `AVX512_VP2INTERSECT` sem o conjunto AVX-512/XSTATE
  correspondente. É uma anomalia real, mas ainda não foi demonstrada como o
  gatilho único do reset.
- Os controles VMX coletados são homogêneos entre os processadores lógicos e
  anunciam EPT, VPID, APICv, MBEC e XSAVES.
- Capturas feitas com Hyper-V ativo representam a visão da root partition e não
  substituem uma referência bare-metal.

## Decisão atual

O workaround oficial é a entrada BCD com `DISABLEHARDWAREMBEC` e XSAVE normal.
O modo `xsavedisable=1` é somente histórico/diagnóstico. Nenhuma BIOS modificada
está aprovada para flash.

A análise cronológica anterior foi preservada em
[`findings-detailed.md`](findings-detailed.md), marcada como histórica.
