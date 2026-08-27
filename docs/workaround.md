# Workaround BCD: Hyper-V sem MBEC por hardware

O workaround reproduzido pelo controle A/B/A mantém XSAVE, AVX e AVX2 ativos e
desabilita somente o uso de MBEC por hardware no lançamento do Hyper-V.

| Propriedade | Windows normal | Hyper-V MBEC fallback |
|---|---|---|
| `hypervisorlaunchtype` | `Off` | `Auto` |
| `hypervisorloadoptions` | ausente | `DISABLEHARDWAREMBEC` |
| `xsavedisable` | ausente | ausente |
| `vsmlaunchtype` | ausente | `Off` |
| AVX/AVX2 | disponíveis | disponíveis |
| Hyper-V/WSL2 | não iniciado | funcional no hardware testado |

O script mantém a entrada normal como padrão e nunca reinicia a máquina por
conta própria.

## Procedimento automatizado

Abra PowerShell como administrador, confirme que a chave de recuperação do
BitLocker está salva e suspenda a proteção quando aplicável. A partir da raiz do
repositório:

```powershell
.\tools\windows\bcd\setup-bcd-dual-mode.ps1
.\tools\windows\bcd\setup-bcd-dual-mode.ps1 -Apply
.\tools\windows\bcd\audit-bcd-dual-mode.ps1
```

O primeiro comando é apenas uma simulação. O segundo exporta um backup integral
do BCD, cria a entrada fallback e grava os GUIDs no estado gerenciado. O terceiro
confirma os elementos esperados antes do reboot.

O setup também aceita ser executado enquanto o Windows foi iniciado pela antiga
entrada `DISABLEHARDWAREMBEC`. Nesse caso ele copia essa entrada para preservar o
fallback e transforma a entrada atual na normal/default. Somente esse override
exato é aceito na migração; qualquer opção experimental adicional ainda aborta
antes do backup e das alterações.

Para usar a entrada Hyper-V apenas na próxima inicialização:

```powershell
.\tools\windows\bcd\schedule-hyperv-diagnostic-once.ps1 -Apply
shutdown /r /t 0
```

Depois do boot fallback, confirme:

```powershell
(Get-CimInstance Win32_ComputerSystem).HypervisorPresent
python .\tools\collect\windows\probe_avx_execution.py --json
wsl -d Ubuntu -- uname -srvm
```

Um reboot comum retorna à entrada normal porque ela continua sendo o default.

Para remover somente a entrada gerenciada, já iniciado pelo Windows normal:

```powershell
.\tools\windows\bcd\remove-bcd-dual-mode.ps1
.\tools\windows\bcd\remove-bcd-dual-mode.ps1 -Apply
```

## Equivalente manual

Faça primeiro um backup:

```powershell
bcdedit /export C:\bcd-before-hyperv-mbec-fallback.bak
bcdedit /copy "{current}" /d "Windows - Hyper-V MBEC fallback"
```

Guarde o GUID retornado como `<HV_GUID>` e aplique:

```powershell
bcdedit /set "<HV_GUID>" hypervisorlaunchtype auto
bcdedit /set "<HV_GUID>" hypervisorloadoptions DISABLEHARDWAREMBEC
bcdedit /deletevalue "<HV_GUID>" xsavedisable
bcdedit /set "<HV_GUID>" vsmlaunchtype off

bcdedit /set "{current}" hypervisorlaunchtype off
bcdedit /deletevalue "{current}" hypervisorloadoptions
bcdedit /deletevalue "{current}" xsavedisable
bcdedit /deletevalue "{current}" vsmlaunchtype
bcdedit /set "{current}" description "Windows - Normal (AVX, Hyper-V off)"
bcdedit /default "{current}"
bcdedit /timeout 8
```

`/deletevalue` pode informar que um elemento não existe; isso é esperado quando
o valor já está ausente. Não copie outros overrides experimentais para a entrada
fallback.

## Evidência e limites

O resultado foi repetido em
[`HV06 PASS 1`](../evidence/boot/hv06-mbec-working-pass1/), seguido por
[`HV01 baseline failure`](../evidence/boot/hv01-baseline-failure-20260826/) e
[`HV06 PASS 2`](../evidence/boot/hv06-mbec-working/). Nos dois passes, Hyper-V,
AVX, AVX2 e WSL2 funcionaram.

`DISABLEHARDWAREMBEC` é um workaround específico desta investigação, não uma
correção de firmware nem uma recomendação geral para outros computadores. O
bypass histórico `xsavedisable=1` confirmou que outro caminho também evitava a
falha, mas removia todas as instruções AVX visíveis ao Windows; por isso não é a
configuração oficial atual.

## O que é uma entrada BCD

Uma entrada BCD é um objeto do Windows Boot Manager que aponta para a mesma
instalação do Windows, mas pode carregar parâmetros de boot diferentes. Criar a
entrada fallback não duplica o Windows nem os arquivos do usuário.

- `{current}` identifica a entrada que iniciou o Windows atual.
- `<HV_GUID>` representa o identificador retornado por `bcdedit /copy`.
- `hypervisorlaunchtype Auto` inicia o hipervisor; isso não altera VT-x/VT-d na
  BIOS.
- `/default` define a entrada escolhida quando o tempo do menu termina.
- `/bootsequence` agenda uma entrada apenas para a próxima inicialização e depois
  retorna ao default.

Os scripts registram os GUIDs gerenciados em
`C:\ProgramData\BiosInterposer\bcd-dual-mode.json`; por isso remoção e boot
one-shot não precisam adivinhar qual entrada modificar.
