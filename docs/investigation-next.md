# PrÃ³ximos testes do Hyper-V

## SituaÃ§Ã£o

Nenhuma alteraÃ§Ã£o foi aplicada ao BCD, Registro ou firmware. A entrada atual continua intacta, `IgnoreMemPart` continua em `1` e nÃ£o houve reinicializaÃ§Ã£o.

HÃ¡ dois defeitos objetivos de plataforma:

1. MADT com CPUs `0..15`, mas Local APIC NMI `1..16`;
2. CPUID anuncia `AVX512_VP2INTERSECT` sem AVX512F/VL nem XSTATE 5â€“7.

HÃ¡ ainda uma lacuna: os MSRs `IA32_VMX_*` do stepping ES D0 nÃ£o podem ser lidos no Windows sem driver. O coletor Linux jÃ¡ estÃ¡ pronto.

## Prioridade nova: corrigir a MADT apenas em memÃ³ria

Antes de gravar a BIOS, foi preparado um teste reversÃ­vel com OpenCore. Ele fornece ao Windows uma MADT com os UIDs NMI corrigidos e inclui um controle idÃªntico com o patch desligado. As trÃªs configuraÃ§Ãµes passaram no `ocvalidate` 1.0.7.

O procedimento completo estÃ¡ em `docs/opencore-madt-experiment.md`. A ordem agora Ã©:

1. instalar o OpenCore preservando o `EFI` do shell/FPT;
2. iniciar o Windows seguro com Hyper-V desligado;
3. provar pela API do Windows que a MADT recebida mudou de NMI `1..16` para `0..15`;
4. sÃ³ entÃ£o testar `HV 01 BASELINE`;
5. se iniciar, repetir com o controle sem patch para provar causalidade.

AtÃ© agora apenas o `dry-run` do instalador foi executado; o pendrive, o BCD, o Registro e a BIOS continuam inalterados.

## Quando houver janela para reboot

Abra PowerShell como Administrador e faÃ§a primeiro o dry-run:

```powershell
Set-Location (git rev-parse --show-toplevel)
& 'archive\experiments\legacy-scripts\prepare-hyperv-diagnostic-matrix.ps1'
```

Para criar as entradas, sem selecionar nem agendar nenhuma:

```powershell
& 'archive\experiments\legacy-scripts\prepare-hyperv-diagnostic-matrix.ps1' -Apply
```

O script exporta o BCD e deixa `{current}` como padrÃ£o seguro com Hyper-V desligado. Escolha manualmente uma entrada no menu. Comece nesta ordem:

1. `HV 08 CAPTURA BOOTLOG`;
2. `HV 05 MINIMO`;
3. `HV 04 UM LP`;
4. `HV 09 SEM vAPIC`;
5. `HV 10 SEM POSTED INT`;
6. `HV 11 SEM IPI VIRTUAL`;
7. `HV 03 xAPIC LEGADO`;
8. `HV 13 APIC DEST FISICO`;
9. `HV 02 SEM IOMMU`;
10. `HV 12 SEM SLAT EPT`;
11. `HV 06 SEM MBEC HW`;
12. `HV 07 SEM XSAVE`;
13. `HV 14 SCHED CLASSICO`.

As entradas 15â€“18 sÃ£o a segunda onda, experimental. NÃ£o repita uma entrada que jÃ¡ reiniciou.

Depois de cada tentativa, deixe a entrada segura iniciar e colete:

```powershell
& 'archive\experiments\legacy-scripts\collect-hyperv-postboot-evidence.ps1' `
  -ManifestPath 'evidence\boot\bcd-backups\hyperv-matrix-AAAAMMDD-HHMMSS.json' `
  -SelectedEntry 'HV NN NOME'
```

## Antes da matriz, opÃ§Ã£o de BIOS barata

FaÃ§a apenas uma mudanÃ§a: defina `AVX3` como habilitado, inicie com Hyper-V desligado e rode:

```powershell
python 'archive\experiments\legacy-scripts\dump_cpuid_windows.py' > '.\archive\experiments\cpuid-avx3-enabled.json'
```

Restaure a opÃ§Ã£o se AVX512F/VL, VP2INTERSECT e XSTATE 5â€“7 continuarem incoerentes. NÃ£o combine esse teste com VT-d, HT ou nÃºmero de nÃºcleos.

## Se nenhuma entrada iniciar

No Linux:

```bash
sudo modprobe msr
sudo python3 collect_tgl_vmx_msrs_linux.py > tgl-vmx-msrs.json
```

Depois disso, a prÃ³xima prova Ã© KDNET com um segundo PC. O plano estÃ¡ em `HIPER_V_DEPURACAO_FUTURA.md`.

## Quando considerar a BIOS corrigida

Somente apÃ³s trÃªs leituras externas idÃªnticas e recuperaÃ§Ã£o testada. A candidata atual Ã©:

`firmware/patches/candidates/polestar-hyperv-madt-nmi-zero-based-layout-preserved.bin`

Ela altera somente os 16 UIDs NMI `1..16` para `0..15`. SHA-256:

`4F99E06399972E31D7D86383D8B81E451C7F75A5D5A00DB8CD8A34AFA25E8E73`

Ela Ã© um experimento mÃ­nimo, nÃ£o uma soluÃ§Ã£o comprovada. Se `UM LP`, vAPIC, posted interrupts, IPI virtual ou APIC fÃ­sico fizer o Hyper-V iniciar, o resultado justificarÃ¡ ou refutarÃ¡ esse patch antes do flash.
