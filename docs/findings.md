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
- [`evidence/boot/hyperv-avx512-working-20260827/`](../evidence/boot/hyperv-avx512-working-20260827/)
- [`evidence/cpuid/`](../evidence/cpuid/)
- [`evidence/msr/linux/`](../evidence/msr/linux/)

## Observação posterior: AVX-512 funcional

No boot de 27/08/2026, a entrada `HV 06 SEM MBEC HW` apresentou
`HypervisorPresent=True` e executou instruções AVX, AVX2 e AVX-512F em processos
isolados. O CPUID visível à root partition anunciou AVX512F, AVX512VL,
VP2INTERSECT e componentes XSTATE 5–7 coerentes e idênticos nos 16 LPs. O
validator 0.5.0 classificou essa captura como `Not affected`/`CLEAN`.

Esse resultado prova que Hyper-V e AVX-512 podem coexistir nesta plataforma
quando MBEC por hardware está desabilitado. A comparação do SPI runtime isolou
`CpuSetup+0x22A: 1 → 0` (AVX3 habilitado) como a mudança decisiva para a
enumeração AVX-512; outras opções BIOS também mudaram, então não houve A/B de
variável única. O boot continua com `DISABLEHARDWAREMBEC`. AVX3 sozinho não foi
testado como correção do boot Hyper-V com MBEC por hardware. Evidência em
[`hyperv-avx512-working-20260827`](../evidence/boot/hyperv-avx512-working-20260827/)
e [`avx512-runtime-firmware-diff.md`](avx512-runtime-firmware-diff.md).

## Findings anteriores que continuam válidos

- A MADT original tem UIDs de Local APIC NMI inconsistentes; a correção entregue
  por OpenCore chegou ao Windows, mas não eliminou a falha.
- Com AVX3 desabilitado, o CPUID bare-metal expunha `AVX512_VP2INTERSECT` sem
  o conjunto AVX-512/XSTATE correspondente. Habilitar AVX3 restaurou enumeração
  coerente. A anomalia era real, mas ainda não foi demonstrada como o gatilho
  único do reset do Hyper-V.
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
