# Erying / Polestar HM570 Tiger Lake-H ES Hyper-V investigation

Investigação reproduzível da falha de inicialização do Hyper-V em placas
Erying/Polestar HM570 com Tiger Lake-H ES (`CPUID 806D0`, `Genuine Intel CPU
0000`). Linux/KVM funciona; o Hyper-V reinicia o Windows durante o boot quando
o caminho de MBEC por hardware está ativo.

## Resultado atual

O controle A/B/A de 26/08/2026 isolou o comportamento:

| Configuração | Resultado |
|---|---|
| MBEC por hardware ativo + XSAVE ativo | falha de boot |
| `DISABLEHARDWAREMBEC` + XSAVE ativo | Hyper-V, AVX, AVX2 e WSL2 funcionam |
| MBEC por hardware ativo + `xsavedisable=1` | Hyper-V funciona, mas AVX/AVX2 somem |

Os dois boots com `DISABLEHARDWAREMBEC`, separados por um retorno à configuração
baseline que falhou, tornam o caminho de MBEC por hardware o isolador mais forte
até agora. Isso não determina se a causa final está no silício ES, microcode,
firmware ou na interação com a implementação do Hyper-V.

Evidência primária:

- [`HV06 PASS 1`](evidence/boot/hv06-mbec-working-pass1/)
- [`HV01 baseline failure`](evidence/boot/hv01-baseline-failure-20260826/)
- [`HV06 PASS 2`](evidence/boot/hv06-mbec-working/)

## Workaround atual

Mantenha VT-x/VT-d habilitados na BIOS. A configuração gerenciada cria:

- `Windows - Normal (AVX, Hyper-V off)`, como entrada padrão;
- `Windows - Hyper-V MBEC fallback`, com Hyper-V ligado,
  `hypervisorloadoptions DISABLEHARDWAREMBEC`, XSAVE normal e AVX/AVX2 ativos.

O antigo bypass `xsavedisable=1` permanece apenas como evidência histórica e
isolador diagnóstico. Ele não deve ser usado como solução diária. O procedimento
seguro, com backup, auditoria e boot one-shot, está em
[`docs/workaround.md`](docs/workaround.md).

## Validação

```powershell
python tools/collect/windows/collect_platform.py platform.json --madt-output evidence/acpi/apic.dat
python tools/validate_platform.py platform.json --madt evidence/acpi/apic.dat --report-json report.json
python -m pip install -r requirements-dev.txt
python -m pytest
```

O validator separa o estado observado da causa atribuída. Ele só classifica um
bypass XSAVE como confirmado quando a própria coleta contém o estado BCD
correspondente.

## Próxima investigação

Comparar os controles VMX secundários efetivamente usados no lançamento do
Hyper-V, especialmente a combinação entre MBEC e VMX XSAVES/XRSTORS. Nenhuma
imagem de firmware modificada é considerada solução comprovada.

## Documentação

- [Workaround BCD atual](docs/workaround.md)
- [Findings consolidados](docs/findings.md)
- [Próxima investigação](docs/investigation-next.md)
- [Narrativa da falha do Hyper-V](docs/hyperv-failure.md)
- [Hardware e evidências](docs/hardware.md)
- [Fontes e reprodução de artefatos de firmware](firmware/sources.md)
- [Log da investigação](docs/investigation-log.md)

## Segurança e privacidade

Dumps SPI completos não são publicados: podem conter NVRAM, UUID, serial e MAC.
Os backups integrais ficam em armazenamento privado. Caminhos locais e nomes de
host são removidos dos artefatos publicados; use caminhos relativos à raiz do
repositório ao reproduzir os procedimentos.
