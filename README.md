# Erying / Polestar HM570 Tiger Lake-H ES Hyper-V Fix

Investigação reproduzível de incompatibilidades de firmware/CPU em placas
Erying/Polestar HM570 com Tiger Lake-H Engineering Sample.

**Affected**

- HM570111
- Tiger Lake-H ES CPUID `806D0`
- `Genuine Intel CPU 0000`

**Symptom**

Hyper-V causa reset/bootloop precoce, enquanto Linux/KVM funciona.

**Known working workaround**

Causal setting for the CPUID/XSTATE bug:

```powershell
bcdedit /set "{current}" hypervisorlaunchtype auto
bcdedit /set "{current}" xsavedisable 1
```

The successful native boot also had `vsmlaunchtype=off` because the diagnostic
matrix applied it to every test entry. See [workaround.md](docs/workaround.md)
for the precise required vs observed configuration.

**Root findings**

1. MADT com mapeamento inconsistente de UID nas entradas Local APIC NMI.
2. Exposição CPUID/XSTATE incoerente: `AVX512_VP2INTERSECT=1` sem o conjunto
   AVX-512 correspondente.

## Validação

O projeto separa coleta de análise. Coletores produzem JSON normalizado e
podem incluir diagnósticos auxiliares (PKU/CET, TSC); a classificação de
compatibilidade da plataforma é responsabilidade exclusiva do validator.

```powershell
python tools/collect/windows/collect_platform.py platform.json --madt-output evidence/acpi/apic.dat
python tools/validate_platform.py platform.json --madt evidence/acpi/apic.dat --report-json report.json
python tools/validate_platform.py
python tools/validate_platform.py tests/fixtures/affected/platform.json --madt tests/fixtures/affected/madt-original.dat
python -m pip install -r requirements-dev.txt
python -m pytest
```

O comando sem argumentos usa o fixture afetado. O relatório JSON contém a
classificação, checks, issues, valores CPUID relevantes, resumo MADT, versão
do validator e recomendação. Códigos de saída: `0` limpo, `1` anomalias
detectadas, `2` dados insuficientes. O workaround só aparece quando a
assinatura `000806D0` coincide com a inconsistência CPUID/XSTATE conhecida.

## Documentação

- [Hardware e evidências](docs/hardware.md)
- [Falha do Hyper-V](docs/hyperv-failure.md)
- [Findings consolidados](docs/findings.md)
- [Workaround comprovado](docs/workaround.md)
- [Experimento MADT/OpenCore](docs/opencore-madt-experiment.md)
- [Plano de correção de firmware](docs/firmware-fix.md)
- [Fontes e reprodução dos artefatos de firmware](firmware/sources.md)
- [Log da investigação](docs/investigation-log.md)

## Organização

- `tools/collect/`: coletores por sistema operacional.
- `tools/validate_platform.py`: validação determinística.
- `tests/`: testes e fixtures de regressão.
- `evidence/`: tabelas e resultados normalizados, sem dumps SPI integrais.
- `firmware/`: manifests e patches pequenos/reproduzíveis.
- `archive/experiments/`: hipóteses, scripts antigos e artefatos rejeitados.

## Segurança de firmware

Não publique dumps SPI completos: eles podem conter NVRAM, UUID, serial e MAC.
Os backups integrais de recuperação deste trabalho ficam fora deste projeto,
em `bios-interposer-private-backups`. O patch MADT é experimental e não deve
ser gravado sem validação externa, restauração preparada e evidência causal.

Nenhuma BIOS modificada é considerada solução comprovada neste repositório.
