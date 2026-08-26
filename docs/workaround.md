# Modo BCD normal e bypass diagnóstico

`xsavedisable=1` não desabilita apenas AVX-512. A
[Microsoft documenta](https://learn.microsoft.com/en-us/windows-hardware/drivers/devtest/bcdedit--set)
que qualquer valor diferente de zero desabilita a funcionalidade XSAVE no kernel.
Na plataforma afetada, o CPU-Z confirmou o efeito deste boot: AVX e AVX2
deixaram de aparecer, enquanto SSE, AES e SHA continuaram disponíveis.

Portanto, esta opção é um **bypass diagnóstico degradado**, não uma correção
para uso diário. O resultado localiza fortemente a falha no caminho de
inicialização/gerenciamento XSAVE/XSTATE do Windows e Hyper-V, mas não prova
qual componente individual desse contrato dispara a falha.

## O que é uma entrada BCD

Uma entrada BCD é um objeto do Windows Boot Manager com identificador próprio,
normalmente um GUID como `{01234567-89ab-cdef-0123-456789abcdef}`. Duas entradas
podem carregar a mesma instalação do Windows com parâmetros diferentes. Copiar
uma entrada não copia o Windows nem os dados; cria outra opção no menu de boot.

- `{current}` é a entrada usada para iniciar o Windows atual.
- `<HV_GUID>` abaixo é o GUID retornado por `bcdedit /copy`. Substitua o texto
  inteiro, incluindo `< >`, pelo GUID real.
- `hypervisorlaunchtype auto` significa "lançar o hipervisor Microsoft nesta
  entrada". Não liga nem desliga VT-x/VT-d na BIOS.
- `/default` escolhe a entrada usada quando o menu expira.
- `/bootsequence` escolhe uma entrada somente para o próximo boot; depois o
  Boot Manager volta automaticamente ao default.

## Configuração oficial provisória

Mantenha VMX/VT-x e VT-d habilitados na BIOS nos dois modos.

| Estado | Windows - Normal | Windows - Hyper-V diagnostic |
|---|---|---|
| VMX/VT-d na BIOS | ON | ON |
| `hypervisorlaunchtype` | `off` | `auto` |
| `xsavedisable` | ausente | `1` |
| `vsmlaunchtype` | `off` | `off` |
| XSAVE do Windows | normal | desabilitado globalmente |
| AVX/AVX2 | disponíveis | indisponíveis |
| Hyper-V | não inicia | inicia no teste observado |
| Uso | default diário | diagnóstico, WSL2/Docker quando indispensável |

`vsmlaunchtype=off` estava presente em todas as entradas da matriz, inclusive
no boot positivo. Seu efeito ainda não foi isolado. O modo diagnóstico não
garante toda carga: AVX/AVX2 ficam indisponíveis.

## Montagem segura a partir do boot diagnóstico atual

Execute em PowerShell ou Terminal elevado. Primeiro exporte o BCD:

```powershell
bcdedit /export C:\bcd-before-dual-mode.bak
```

Copie a entrada atual, que já representa o boot Hyper-V funcional:

```powershell
bcdedit /copy "{current}" /d "Windows - Hyper-V diagnostic (XSAVE off)"
```

O comando retorna um GUID. Guarde-o como `<HV_GUID>` e configure **essa cópia**:

```powershell
bcdedit /set "<HV_GUID>" hypervisorlaunchtype auto
bcdedit /set "<HV_GUID>" xsavedisable 1
bcdedit /set "<HV_GUID>" vsmlaunchtype off
```

Agora transforme a entrada em uso (`{current}`) no modo normal:

```powershell
bcdedit /set "{current}" hypervisorlaunchtype off
bcdedit /deletevalue "{current}" xsavedisable
bcdedit /set "{current}" vsmlaunchtype off
bcdedit /set "{current}" description "Windows - Normal (AVX, Hyper-V off)"
bcdedit /default "{current}"
bcdedit /timeout 8
```

Se `xsavedisable` já estiver ausente, `/deletevalue` pode informar que o
elemento não existe; isso é seguro. Confira tudo antes de reiniciar:

```powershell
bcdedit /enum "{current}"
bcdedit /enum "<HV_GUID>"
bcdedit /enum "{bootmgr}"
```

Confirme que `{current}` é o default e tem `hypervisorlaunchtype Off`, enquanto
`<HV_GUID>` tem `hypervisorlaunchtype Auto`, `xsavedisable 1` e
`vsmlaunchtype Off`. Não torne a entrada diagnóstica o default.

## Validar o boot normal

Reinicie sem selecionar a entrada diagnóstica. No Windows normal:

```powershell
(Get-CimInstance Win32_ComputerSystem).HypervisorPresent
```

O resultado esperado é `False`. CPU-Z deve voltar a mostrar AVX e AVX2. Uma
nova coleta do projeto também registra a visão do kernel:

```powershell
python tools\collect\windows\collect_platform.py normal-platform.json
```

Em `collection.windows_processor_features.features`, o esperado é XSAVE, AVX
e AVX2 com `available: true`, além de SSE/SSE2. Esses valores vêm da API
[`IsProcessorFeaturePresent`](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-isprocessorfeaturepresent).

## Usar Hyper-V somente no próximo boot

No Windows normal, substitua `<HV_GUID>` pelo GUID real:

```powershell
bcdedit /bootsequence "<HV_GUID>"
shutdown /r /t 0
```

[`/bootsequence`](https://learn.microsoft.com/en-us/windows-hardware/drivers/devtest/bcdedit--bootsequence)
vale apenas para a próxima inicialização. Ao reiniciar de novo, o Boot Manager
retorna ao default `Windows - Normal`.

No boot diagnóstico, confirme:

```powershell
(Get-CimInstance Win32_ComputerSystem).HypervisorPresent
python tools\collect\windows\collect_platform.py diagnostic-platform.json
```

O resultado observado nesta plataforma é `HypervisorPresent=True`,
XSAVE/AVX/AVX2 indisponíveis e SSE/SSE2 ainda disponíveis. Preserve as duas
coletas para comparar o CPUID visível em cada boot com a disponibilidade
efetiva em `collection.windows_processor_features`. Sob o bypass, o próprio
CPUID visível pode ser mascarado; ele não deve ser chamado de visão imutável do
hardware.

A captura confirmada deste estado está em
[`evidence/cpuid/cpuid-windows-xsavedisable-20260826.json`](../evidence/cpuid/cpuid-windows-xsavedisable-20260826.json).
Ela registrou `CPUID.1.ECX=0xE3FAE38F`, XSAVE/AVX/AVX2 indisponíveis e
SSE/SSE2 disponíveis.

## Limite causal e alvo definitivo

```text
XSAVE normal + Hyper-V       -> falha precoce
XSAVE globalmente desligado  -> Hyper-V inicia, AVX/AVX2 indisponíveis
```

O experimento não demonstra que `AVX512_VP2INTERSECT` é sozinho o gatilho. A
correção seletiva desejada continua sendo XSAVE, AVX e AVX2 ativos, enumeração
AVX-512 coerente e Hyper-V iniciando normalmente. Não use
`xsaveremovefeature` ou outros elementos XSTATE sem entender exatamente o
componente e o formato esperados pelo Windows.

O experimento MADT/OpenCore permanece separado em
[`opencore-madt-experiment.md`](opencore-madt-experiment.md).
