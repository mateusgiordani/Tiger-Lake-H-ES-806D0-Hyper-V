# Execução do controle causal OpenCore — 25/08/2026

## Contexto

Primeira execução real do experimento `CONTROL DISABLED` (OpenCore na mesma
cadeia, MADT original incorreta, Hyper-V baseline sem isoladores). Configuração
verificada antes: hash do `config.plist` `B537E452...` (CONTROL DISABLED).

## Linha do tempo capturada (System event log)

| Hora | Evento |
|---|---|
| 10:43:35 | Boot da entrada HV via OpenCore inicia (`ntbtlog.txt` criado) |
| 10:43:42 | Reset silencioso (~7 s), sem bugcheck, sem dump |
| 10:44–11:02 | Ciclos de reset repetidos (Eventos 41/6008 em 10:44, 10:48, 10:49, 10:53, 10:57, 11:02) |
| 10:56 | Reparo de Inicialização automático executou "reparos" |
| 11:18 | Última escrita do bootlog (sessão de recuperação/pós-reparo) |

## Evidência principal: sessão S#1 do ntbtlog

- 178 linhas; **171 drivers carregados**; último: `cdd.dll`
  (Canonical Display Driver — inicialização de sessão/win32k);
- morte por **reset silencioso** sem bugcheck registrado (sem Evento 1001,
  sem `MEMORY.DMP`, sem minidump);
- portanto o boot chegou à fase de interface/sessão, muito depois do ponto de
  falha original da cadeia nativa.

## Interpretação (matriz do README)

Controle (MADT original + OpenCore) ⇒ **reset silencioso**.
Patch (MADT corrigida + OpenCore) ⇒ **BSOD visível `0x7E/C0000005`**.

Conclusão causal: **a correção dos 16 UIDs NMI da MADT altera objetivamente o
modo de falha** — o boot avança até a fase gráfica/sessão e falha com exceção
estruturada em vez de resetar cedo. A correção é necessária mas não
suficiente; existe um segundo defeito no caminho posterior (candidatos:
consumo APICv/x2APIC do mapeamento NMI pelo hipervisor, combinação
CPUID/XSTATE AVX-512, ou contrato adicional do stepping ES).

## Dano colateral ao Windows (não relacionado ao experimento)

- Instalação de driver AMD (pacote `u0203304.inf`, 08:53–08:54) foi
  interrompida pela tempestade de resets; Reparo de Inicialização removeu a
  chave de serviço `amdkmdag` enquanto os pacotes permaneceram no
  DriverStore → tela preta/congelamento do driver de vídeo no logon em modo
  normal. Recuperação planejada: DDU em modo de segurança + reinstalação limpa
  do Adrenalin.
- `ntbtlog.txt`, eventos do dia e este relatório preservados nesta pasta.
