# Próxima investigação: MBEC e controles VMX secundários

O A/B/A já separou configuração de resultado. O próximo objetivo não é procurar
mais combinações BCD: é explicar por que o lançamento do Hyper-V falha somente
quando o caminho de MBEC por hardware está ativo.

A incoerência CPUID/XSTATE de AVX-512 foi corrigida no firmware ao habilitar
AVX3 (`CpuSetup+0x22A = 0`). Isso é independente do isolador MBEC: os boots
Hyper-V bem-sucedidos ainda usam `DISABLEHARDWAREMBEC`. AVX3 não substitui esse
teste e ainda não foi experimentado sozinho com MBEC por hardware ativo.

## Pergunta principal

Qual combinação efetiva de `IA32_VMX_PROCBASED_CTLS2` o Hyper-V tenta habilitar
no Tiger Lake-H ES, especialmente MBEC junto de VMX XSAVES/XRSTORS, e em que
ponto essa combinação diverge do comportamento esperado?

## Evidência necessária

1. Decodificar os bits allowed-0/allowed-1 de `IA32_VMX_PROCBASED_CTLS2` e dos
   demais MSRs VMX já coletados, preservando os valores brutos por LP.
2. Comparar com documentação arquitetural Intel e, se disponível, com um
   Tiger Lake-H de produção equivalente.
3. Verificar microcode, revisão de silício e configuração de firmware sem inferir
   suporte funcional apenas porque um bit “may be 1” está anunciado.
4. Correlacionar o último evento de boot observável com a ativação desses
   controles. Se logging de boot não bastar, preparar uma captura de depuração
   focada em `hvloader.dll`/`hvix64.exe`.
5. Manter o A/B/A como controle: baseline deve falhar e
   `DISABLEHARDWAREMBEC` deve continuar passando antes de interpretar um novo
   isolador.

## Critério de avanço

Uma hipótese só avança se prever e explicar simultaneamente:

- a falha com MBEC por hardware e XSAVE ativos;
- o sucesso com MBEC por hardware desabilitado e XSAVE ativo;
- o sucesso, com perda de AVX/AVX2, quando XSAVE é globalmente desabilitado.

Não gravar firmware candidato nem editar binários do Hyper-V nesta etapa. Uma
eventual correção de firmware deve nascer de uma diferença reproduzível, mínima
e validada contra os três estados acima.
