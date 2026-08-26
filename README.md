# Erying / Polestar HM570 Tiger Lake-H ES Hyper-V Fix

Investigação reproduzível de incompatibilidades de firmware/CPU em placas
Erying/Polestar HM570 com Tiger Lake-H Engineering Sample.

**Affected**

- HM570111
- Tiger Lake-H ES CPUID `806D0`
- `Genuine Intel CPU 0000`

**Symptom**

Hyper-V causa reset/bootloop precoce, enquanto Linux/KVM funciona.

**Diagnostic bypass, not a daily-use fix**

Desabilitar globalmente o XSAVE do kernel permitiu o boot nativo do Hyper-V,
localizando fortemente a falha no caminho de inicialização XSAVE/XSTATE. O
mesmo boot tornou AVX e AVX2 indisponíveis para aplicativos Windows. Isso não
prova que o bit órfão `AVX512_VP2INTERSECT` seja sozinho o gatilho exato.

Mantenha VT-x/VT-d habilitados na BIOS e use duas entradas BCD: uma entrada
normal como default, com Hyper-V desligado e AVX disponível, e uma entrada
diagnóstica não default, com Hyper-V ligado e `xsavedisable=1`. Consulte
[workaround.md](docs/workaround.md) para o procedimento com backup e o fluxo
one-shot por `/bootsequence`.

**Root findings**

1. MADT com mapeamento inconsistente de UID nas entradas Local APIC NMI.
2. Exposição CPUID/XSTATE incoerente: `AVX512_VP2INTERSECT=1` sem o conjunto
   AVX-512 correspondente.

## Validação

O projeto separa coleta de análise. Coletores produzem JSON normalizado e
podem incluir diagnósticos auxiliares (PKU/CET, TSC e disponibilidade efetiva
de XSAVE/AVX no Windows); a classificação é responsabilidade do validator.

```powershell
python tools/collect/windows/collect_platform.py platform.json --madt-output evidence/acpi/apic.dat
python tools/validate_platform.py platform.json --madt evidence/acpi/apic.dat --report-json report.json
python tools/validate_platform.py
python tools/validate_platform.py tests/fixtures/affected/platform.json --madt tests/fixtures/affected/madt-original.dat
python -m pip install -r requirements-dev.txt
python -m pytest
```

O comando sem argumentos usa o fixture afetado. O relatório JSON contém
classificação, checks, issues, valores CPUID, resumo MADT, versão do validator
e, quando aplicável, uma mitigação estritamente diagnóstica. Códigos de saída:
`0` limpo, `1` anomalias detectadas, `2` dados insuficientes. O validator nunca
recomenda `xsavedisable=1` para uso diário.

## Documentação

- [Hardware e evidências](docs/hardware.md)
- [Falha do Hyper-V](docs/hyperv-failure.md)
- [Findings consolidados](docs/findings.md)
- [Modo BCD normal e bypass diagnóstico](docs/workaround.md)
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
Os backups integrais de recuperação ficam fora deste projeto, em armazenamento
privado. Nenhuma BIOS modificada é considerada solução comprovada neste
repositório.
