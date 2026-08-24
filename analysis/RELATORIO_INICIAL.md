# Polestar HM570 - inventario inicial de firmware

Data da analise: 2026-08-24

## Maquina em execucao

- BIOS SMBIOS: `THM570111`
- Placa: `INTEL HM570`
- CPU: `Genuine Intel(R) CPU 0000 @ 2.60GHz`
- Assinatura CPUID: `000806D0`
- Microcode carregado pelo Windows: revisao `0x50`
- VT-x exposto pelo firmware: sim
- SLAT exposto pelo firmware: sim
- VM Monitor Mode Extensions: sim
- VBS no boot funcional: desabilitado

## Imagens encontradas

| Imagem | Tamanho | SHA-256 |
|---|---:|---|
| BIOSATUALIZADA.bin | 16 MiB | `AD7ADFC9E82A280445D977104D3226D49E895B1AB5413A45A7324ACA34598F6A` |
| HM570111.bin | 16 MiB | `16529D3B622D150CB2E2EEDA95347C68A878532D39B8B3D9C1F4084A4CFFCCBE` |
| HM570307.bin | 16 MiB | `BBB237F0D1FC85BC44B674BB138F6C8AD0646F8D38AF6576F521AEF8FB3EDCF1` |

A segunda copia de `HM570111.bin` e identica a primeira.

## Estrutura Intel

| Imagem | Descriptor | CSME/ME | Regiao BIOS | CSME |
|---|---:|---:|---:|---|
| BIOSATUALIZADA | 4 KiB | 4092 KiB | 12 MiB | 15.0.35.1932, TGP/EBG-H B |
| HM570111 | 4 KiB | 5116 KiB | 11 MiB | 15.0.35.2039, TGP/EBG-H B |
| HM570307 | 4 KiB | 5116 KiB | 11 MiB | 15.0.21.1503, TGP/EBG-H A |

As imagens nao devem ter regioes misturadas. A `HM570307` usa configuracao de
chipset/CSME diferente da placa `THM570111` em execucao.

## Microcodes

Todas as imagens incluem microcode para o ES `806D0`, revisao `0x50`, datado de
2020-12-17. A ausencia de microcode para o processador ES nao e, portanto, a
explicacao principal do bootloop do Hyper-V.

As imagens `HM570111` e `HM570307` incluem tambem `806D1` revisao `0x3C`; a
`BIOSATUALIZADA` inclui `806D1` revisao `0x24`.

## Observacoes relevantes ao Hyper-V

- O Windows confirma VT-x, SLAT e VM Monitor Mode Extensions.
- Nao ha evento de inicializacao bem-sucedida do provedor Hyper-V-Hypervisor no
  log atual.
- As imagens 111 e 307 possuem os mesmos binarios principais de VT-d em DXE/SMM
  pelos CRCs observados; trocar para 307 nao e um teste seguro nem promissor.
- A proxima evidencia necessaria e um dump da flash em execucao, seguido das
  tabelas ACPI geradas em runtime e do erro exato do boot com hypervisor.
