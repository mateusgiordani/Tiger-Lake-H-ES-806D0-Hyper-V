# Teste reversÃ­vel da MADT com OpenCore

## Objetivo

Testar a correÃ§Ã£o mais promissora sem gravar a BIOS. O OpenCore substitui em memÃ³ria somente a sequÃªncia dos 16 registros `Local APIC NMI` da MADT:

- firmware atual: CPUs `0..15`, NMIs `1..16`;
- tabela corrigida: CPUs `0..15`, NMIs `0..15`.

O filtro exige simultaneamente assinatura `APIC`, comprimento `300`, OEM Table ID exato `41 20 4D 20 49 20 00 00`, sequÃªncia completa de 96 bytes e `Count=1`. O prÃ³prio OpenCore recalcula o checksum da tabela depois da substituiÃ§Ã£o.

HÃ¡ dois modos de configuraÃ§Ã£o:

- `PATCH ENABLED`: correÃ§Ã£o MADT ativa;
- `CONTROL DISABLED`: mesmo OpenCore e mesmas opÃ§Ãµes, mas patch desativado.

Esse controle permite separar uma correÃ§Ã£o causada pela MADT de uma mudanÃ§a genÃ©rica introduzida pela cadeia de boot do OpenCore.

## Estado preparado

- OpenCore oficial: versÃ£o `1.0.7 RELEASE`;
- ZIP original SHA-256: `2FFAB6EBF58C7AEFB0BCB3A1A385D207746823D6DD87D44BD666E1286939943E`;
- MADT capturada SHA-256: `8156FC0F85D4910F72D105C2B12AA92853EC6FB1DEEE35C9E7C3B6C3BD6C9612`;
- MADT corrigida prevista SHA-256: `DEC804620606536ED5BEFD269E0EB4646732057CD355A9BE2006FDB67C119067`;
- os trÃªs `config*.plist` passaram no `ocvalidate` 1.0.7 sem problemas;
- nenhum kext, spoof de SMBIOS, patch de kernel ou propriedade PCI estÃ¡ ativo;
- gravaÃ§Ã£o de NVRAM pelo perfil foi minimizada: `WriteFlash=false`, `UpdateNVRAM=false`, `RequestBootVarRouting=false`, `LauncherOption=Disabled`;
- nada foi copiado ao pendrive ainda.

Arquivos principais:

- `firmware/patches/opencore-madt-test/EFI` â€” Ã¡rvore pronta;
- `firmware/patches/opencore-madt-test/manifest.json` â€” hashes e bytes exatos;
- `archive/experiments/legacy-scripts/build_opencore_madt_test.py` â€” gerador e validador da MADT;
- `archive/experiments/legacy-scripts/deploy_opencore_madt_usb.py` â€” instalaÃ§Ã£o/restauraÃ§Ã£o reversÃ­vel;
- `archive/experiments/legacy-scripts/dump_acpi_windows.py` â€” leitura direta da tabela entregue ao Windows.

## PrÃ©-requisitos da janela de reboot

1. Salvar a chave de recuperaÃ§Ã£o do BitLocker/Criptografia do dispositivo.
2. Suspender temporariamente o BitLocker. Uma cadeia UEFI diferente pode alterar mediÃ§Ãµes do TPM e pedir a chave de recuperaÃ§Ã£o.
3. Desativar temporariamente o Secure Boot na BIOS, pois o `BOOTx64.efi` usado neste diagnÃ³stico nÃ£o estÃ¡ assinado pela Microsoft.
4. Confirmar que a entrada normal do Windows continua com `hypervisorlaunchtype off`.
5. NÃ£o apagar os trÃªs dumps da BIOS do pendrive.

Com PowerShell elevado, a suspensÃ£o pode ser feita conscientemente antes da janela:

```powershell
Get-BitLockerVolume -MountPoint C:
Suspend-BitLocker -MountPoint C: -RebootCount 0
```

NÃ£o execute a segunda linha sem ter a chave de recuperaÃ§Ã£o salva.

## InstalaÃ§Ã£o preservando o shell FPT

O pendrive atual tem duas partiÃ§Ãµes no mesmo SanDisk:

- `G:` â€” FAT32 `BIOS_BACKUP`, inicializÃ¡vel, com os trÃªs dumps e o shell/FPT;
- `H:` â€” exFAT `PS5_DATA`.

O script aceita somente a raiz com label `BIOS_BACKUP` e somente se os trÃªs dumps tiverem o hash conhecido. Primeiro faÃ§a a simulaÃ§Ã£o:

```powershell
Set-Location (git rev-parse --show-toplevel)
python archive\experiments\legacy-scripts\deploy_opencore_madt_usb.py --destination G:\
```

Durante a janela de reboot, para aplicar:

```powershell
python archive\experiments\legacy-scripts\deploy_opencore_madt_usb.py --destination G:\ --apply
```

O `EFI` atual do shell/FPT serÃ¡ renomeado para `EFI-FPT-BACKUP`; nada nele serÃ¡ apagado. A configuraÃ§Ã£o inicial serÃ¡ `PATCH ENABLED`.

## Fase A: provar a tabela antes de ligar o Hyper-V

1. Reinicie pelo menu de boot UEFI e escolha o SanDisk/OpenCore.
2. No picker do OpenCore, escolha o Windows normal, ainda com Hyper-V desligado.
3. Se o Windows nÃ£o aparecer, nÃ£o use ferramentas de reset de NVRAM; desligue, remova o pendrive e volte pelo boot normal.
4. No Windows, execute:

```powershell
python archive\experiments\legacy-scripts\dump_acpi_windows.py `
  --output .\archive\experiments\acpi-after-opencore-patch.dat `
  --json .\archive\experiments\acpi-after-opencore-patch.json
```

SÃ³ prossiga se o JSON mostrar:

- `checksum_valid: true`;
- `local_apic_uids: 0..15`;
- `local_apic_nmi_uids: 0..15`;
- `nmi_uid_set_matches_cpu_uid_set: true`;
- SHA-256 `DEC804620606536ED5BEFD269E0EB4646732057CD355A9BE2006FDB67C119067`.

Se qualquer item divergir, nÃ£o teste Hyper-V por essa cadeia. Restaure o pendrive e preserve o JSON para anÃ¡lise.

## Fase B: testar o Hyper-V com patch ligado

Crie a matriz BCD somente quando estiver pronto, conforme `HIPER_V_MATRIZ_TESTES.md`. A entrada segura permanece padrÃ£o e nenhuma entrada perigosa Ã© agendada automaticamente.

O teste causal principal Ã© selecionar manualmente `HV 01 BASELINE` pelo OpenCore com `PATCH ENABLED`:

- se iniciar, a correÃ§Ã£o da MADT ou a cadeia OpenCore eliminou o reset;
- se reiniciar, deixe a entrada segura iniciar no prÃ³ximo menu e colete as evidÃªncias;
- nÃ£o repita em sequÃªncia uma entrada que jÃ¡ reiniciou.

Se o baseline ainda falhar, use sob o patch, nesta ordem: `HV 04 UM LP`, `HV 09 SEM vAPIC`, `HV 10 SEM POSTED INT`, `HV 11 SEM IPI VIRTUAL`, `HV 03 xAPIC LEGADO`, `HV 02 SEM IOMMU`. Um resultado positivo aqui indicaria uma falha composta, nÃ£o apenas a MADT.

## Fase C: controle negativo

FaÃ§a esta fase somente se o Hyper-V iniciar com o patch ligado. JÃ¡ no Windows seguro, selecione o controle:

```powershell
python archive\experiments\legacy-scripts\deploy_opencore_madt_usb.py `
  --destination G:\ --action disable-patch

python archive\experiments\legacy-scripts\deploy_opencore_madt_usb.py `
  --destination G:\ --action disable-patch --apply
```

Reinicie pela mesma cadeia OpenCore e tente a mesma entrada Hyper-V:

- patch ligado inicia e controle desligado reinicia: forte evidÃªncia causal para a MADT;
- ambos iniciam: o OpenCore altera outra condiÃ§Ã£o de UEFI/memÃ³ria e a MADT nÃ£o foi isolada;
- ambos reiniciam: a correÃ§Ã£o da MADT nÃ£o basta.

Para religar o patch:

```powershell
python archive\experiments\legacy-scripts\deploy_opencore_madt_usb.py `
  --destination G:\ --action enable-patch --apply
```

Um resultado positivo sÃ³ deve ser chamado de reproduzido depois de dois boots com patch ligado e pelo menos um controle desligado.

## Restaurar o pendrive

Primeiro faÃ§a a simulaÃ§Ã£o e depois a restauraÃ§Ã£o:

```powershell
python archive\experiments\legacy-scripts\deploy_opencore_madt_usb.py `
  --destination G:\ --action restore

python archive\experiments\legacy-scripts\deploy_opencore_madt_usb.py `
  --destination G:\ --action restore --apply
```

O OpenCore usado serÃ¡ preservado como `EFI-OPENCORE-MADT-SAVED`; o shell/FPT voltarÃ¡ a ser `EFI`. Depois, reative o BitLocker e o Secure Boot quando a cadeia original estiver confirmada:

```powershell
Resume-BitLocker -MountPoint C:
```

## CritÃ©rio para a BIOS modificada

NÃ£o grave a candidata apenas porque a MADT estÃ¡ objetivamente errada. O flash passa a ser justificÃ¡vel somente se:

1. a Fase A comprovar que o Windows recebeu a MADT corrigida;
2. Hyper-V iniciar com `PATCH ENABLED`;
3. o mesmo teste falhar com `CONTROL DISABLED`;
4. o resultado for repetido;
5. o programador externo e a recuperaÃ§Ã£o do dump original estiverem validados.

Se o patch em memÃ³ria nÃ£o resolver, preservar a BIOS original e avanÃ§ar para MSRs VMX por LP no Linux, matriz de opÃ§Ãµes internas do hipervisor e KDNET produz mais informaÃ§Ã£o que transplantar mÃ³dulos de outra BIOS.

## Fontes tÃ©cnicas

- [OpenCorePkg oficial](https://github.com/acidanthera/OpenCorePkg)
- [Manual de configuraÃ§Ã£o do OpenCore](https://github.com/acidanthera/OpenCorePkg/blob/master/Docs/Configuration.tex)
- [ImplementaÃ§Ã£o oficial do patch e recÃ¡lculo de checksum](https://raw.githubusercontent.com/acidanthera/OpenCorePkg/1.0.7/Library/OcAcpiLib/OcAcpiLib.c)
- [Microsoft GetSystemFirmwareTable](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getsystemfirmwaretable)
