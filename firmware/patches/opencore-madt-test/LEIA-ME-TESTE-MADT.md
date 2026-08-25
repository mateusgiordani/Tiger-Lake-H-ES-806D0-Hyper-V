# Teste reversível da MADT com OpenCore

## Objetivo

Testar a correção mais promissora sem gravar a BIOS. O OpenCore substitui em memória somente a sequência dos 16 registros `Local APIC NMI` da MADT:

- firmware atual: CPUs `0..15`, NMIs `1..16`;
- tabela corrigida: CPUs `0..15`, NMIs `0..15`.

O filtro exige simultaneamente assinatura `APIC`, comprimento `300`, OEM Table ID exato `41 20 4D 20 49 20 00 00`, sequência completa de 96 bytes e `Count=1`. O próprio OpenCore recalcula o checksum da tabela depois da substituição.

Há dois modos de configuração:

- `PATCH ENABLED`: correção MADT ativa;
- `CONTROL DISABLED`: mesmo OpenCore e mesmas opções, mas patch desativado.

Esse controle permite separar uma correção causada pela MADT de uma mudança genérica introduzida pela cadeia de boot do OpenCore.

## Estado preparado

- OpenCore oficial: versão `1.0.7 RELEASE`;
- ZIP original SHA-256: `2FFAB6EBF58C7AEFB0BCB3A1A385D207746823D6DD87D44BD666E1286939943E`;
- MADT capturada SHA-256: `8156FC0F85D4910F72D105C2B12AA92853EC6FB1DEEE35C9E7C3B6C3BD6C9612`;
- MADT corrigida prevista SHA-256: `DEC804620606536ED5BEFD269E0EB4646732057CD355A9BE2006FDB67C119067`;
- os três `config*.plist` passaram no `ocvalidate` 1.0.7 sem problemas;
- nenhum kext, spoof de SMBIOS, patch de kernel ou propriedade PCI está ativo;
- gravação de NVRAM pelo perfil foi minimizada: `WriteFlash=false`, `UpdateNVRAM=false`, `RequestBootVarRouting=false`, `LauncherOption=Disabled`;
- nada foi copiado ao pendrive ainda.

Arquivos principais:

- `analysis/opencore-madt-test/EFI` — árvore pronta;
- `analysis/opencore-madt-test/manifest.json` — hashes e bytes exatos;
- `analysis/scripts/build_opencore_madt_test.py` — gerador e validador da MADT;
- `analysis/scripts/deploy_opencore_madt_usb.py` — instalação/restauração reversível;
- `analysis/scripts/dump_acpi_windows.py` — leitura direta da tabela entregue ao Windows.

## Pré-requisitos da janela de reboot

1. Salvar a chave de recuperação do BitLocker/Criptografia do dispositivo.
2. Suspender temporariamente o BitLocker. Uma cadeia UEFI diferente pode alterar medições do TPM e pedir a chave de recuperação.
3. Desativar temporariamente o Secure Boot na BIOS, pois o `BOOTx64.efi` usado neste diagnóstico não está assinado pela Microsoft.
4. Confirmar que a entrada normal do Windows continua com `hypervisorlaunchtype off`.
5. Não apagar os três dumps da BIOS do pendrive.

Com PowerShell elevado, a suspensão pode ser feita conscientemente antes da janela:

```powershell
Get-BitLockerVolume -MountPoint C:
Suspend-BitLocker -MountPoint C: -RebootCount 0
```

Não execute a segunda linha sem ter a chave de recuperação salva.

## Instalação preservando o shell FPT

O pendrive atual tem duas partições no mesmo SanDisk:

- `G:` — FAT32 `BIOS_BACKUP`, inicializável, com os três dumps e o shell/FPT;
- `H:` — exFAT `PS5_DATA`.

O script aceita somente a raiz com label `BIOS_BACKUP` e somente se os três dumps tiverem o hash conhecido. Primeiro faça a simulação:

```powershell
Set-Location 'C:\Users\estum\OneDrive\Área de Trabalho\projeto conserto bios'
python .\analysis\scripts\deploy_opencore_madt_usb.py --destination G:\
```

Durante a janela de reboot, para aplicar:

```powershell
python .\analysis\scripts\deploy_opencore_madt_usb.py --destination G:\ --apply
```

O `EFI` atual do shell/FPT será renomeado para `EFI-FPT-BACKUP`; nada nele será apagado. A configuração inicial será `PATCH ENABLED`.

## Fase A: provar a tabela antes de ligar o Hyper-V

1. Reinicie pelo menu de boot UEFI e escolha o SanDisk/OpenCore.
2. No picker do OpenCore, escolha o Windows normal, ainda com Hyper-V desligado.
3. Se o Windows não aparecer, não use ferramentas de reset de NVRAM; desligue, remova o pendrive e volte pelo boot normal.
4. No Windows, execute:

```powershell
python .\analysis\scripts\dump_acpi_windows.py `
  --output .\analysis\acpi-after-opencore-patch.dat `
  --json .\analysis\acpi-after-opencore-patch.json
```

Só prossiga se o JSON mostrar:

- `checksum_valid: true`;
- `local_apic_uids: 0..15`;
- `local_apic_nmi_uids: 0..15`;
- `nmi_uid_set_matches_cpu_uid_set: true`;
- SHA-256 `DEC804620606536ED5BEFD269E0EB4646732057CD355A9BE2006FDB67C119067`.

Se qualquer item divergir, não teste Hyper-V por essa cadeia. Restaure o pendrive e preserve o JSON para análise.

## Fase B: testar o Hyper-V com patch ligado

Crie a matriz BCD somente quando estiver pronto, conforme `HIPER_V_MATRIZ_TESTES.md`. A entrada segura permanece padrão e nenhuma entrada perigosa é agendada automaticamente.

O teste causal principal é selecionar manualmente `HV 01 BASELINE` pelo OpenCore com `PATCH ENABLED`:

- se iniciar, a correção da MADT ou a cadeia OpenCore eliminou o reset;
- se reiniciar, deixe a entrada segura iniciar no próximo menu e colete as evidências;
- não repita em sequência uma entrada que já reiniciou.

Se o baseline ainda falhar, use sob o patch, nesta ordem: `HV 04 UM LP`, `HV 09 SEM vAPIC`, `HV 10 SEM POSTED INT`, `HV 11 SEM IPI VIRTUAL`, `HV 03 xAPIC LEGADO`, `HV 02 SEM IOMMU`. Um resultado positivo aqui indicaria uma falha composta, não apenas a MADT.

## Fase C: controle negativo

Faça esta fase somente se o Hyper-V iniciar com o patch ligado. Já no Windows seguro, selecione o controle:

```powershell
python .\analysis\scripts\deploy_opencore_madt_usb.py `
  --destination G:\ --action disable-patch

python .\analysis\scripts\deploy_opencore_madt_usb.py `
  --destination G:\ --action disable-patch --apply
```

Reinicie pela mesma cadeia OpenCore e tente a mesma entrada Hyper-V:

- patch ligado inicia e controle desligado reinicia: forte evidência causal para a MADT;
- ambos iniciam: o OpenCore altera outra condição de UEFI/memória e a MADT não foi isolada;
- ambos reiniciam: a correção da MADT não basta.

Para religar o patch:

```powershell
python .\analysis\scripts\deploy_opencore_madt_usb.py `
  --destination G:\ --action enable-patch --apply
```

Um resultado positivo só deve ser chamado de reproduzido depois de dois boots com patch ligado e pelo menos um controle desligado.

## Restaurar o pendrive

Primeiro faça a simulação e depois a restauração:

```powershell
python .\analysis\scripts\deploy_opencore_madt_usb.py `
  --destination G:\ --action restore

python .\analysis\scripts\deploy_opencore_madt_usb.py `
  --destination G:\ --action restore --apply
```

O OpenCore usado será preservado como `EFI-OPENCORE-MADT-SAVED`; o shell/FPT voltará a ser `EFI`. Depois, reative o BitLocker e o Secure Boot quando a cadeia original estiver confirmada:

```powershell
Resume-BitLocker -MountPoint C:
```

## Critério para a BIOS modificada

Não grave a candidata apenas porque a MADT está objetivamente errada. O flash passa a ser justificável somente se:

1. a Fase A comprovar que o Windows recebeu a MADT corrigida;
2. Hyper-V iniciar com `PATCH ENABLED`;
3. o mesmo teste falhar com `CONTROL DISABLED`;
4. o resultado for repetido;
5. o programador externo e a recuperação do dump original estiverem validados.

Se o patch em memória não resolver, preservar a BIOS original e avançar para MSRs VMX por LP no Linux, matriz de opções internas do hipervisor e KDNET produz mais informação que transplantar módulos de outra BIOS.

## Fontes técnicas

- [OpenCorePkg oficial](https://github.com/acidanthera/OpenCorePkg)
- [Manual de configuração do OpenCore](https://github.com/acidanthera/OpenCorePkg/blob/master/Docs/Configuration.tex)
- [Implementação oficial do patch e recálculo de checksum](https://raw.githubusercontent.com/acidanthera/OpenCorePkg/1.0.7/Library/OcAcpiLib/OcAcpiLib.c)
- [Microsoft GetSystemFirmwareTable](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getsystemfirmwaretable)

