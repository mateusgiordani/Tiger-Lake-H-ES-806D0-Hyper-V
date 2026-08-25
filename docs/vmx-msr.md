# Análise da coleta VMX/MSR no Linux — Polestar HM570 Tiger Lake ES D0

Data da análise: 25/08/2026

## Procedência das evidências

Duas inicializações KDE neon 24.04 (kernel `6.14.0-37-generic`) pela NVMe
Ubuntu, com bootloader independente do Windows Boot Manager. Coleta somente
leitura por `archive/experiments/legacy-scripts/run-in-ubuntu.sh`.

| Execução | Configuração | Pasta | SHA-256 do tgl-vmx-msrs.json |
|---|---|---|---|
| 08:29 | VMX habilitado (estado em que o Hyper-V falha) | `vmx-ON` | `34B6B6687FA716B0FD618228C5D38DA29F8E36C67A859779408D5D8D22147CDE` |
| 08:39 | VMX desabilitado no Setup | `vmx-OFF` | `D084D8F4FA1809C5FC30E70494160EAE01C20C4298D6E2367959AFB53B1F664C` |

Analisador: `archive/experiments/legacy-scripts/analyze_linux_msr.py`.

## Resultado principal — VMX-ON

### Uniformidade entre os 16 processadores lógicos

`identical_msr_groups = [[0..15]]`: **um único grupo com todos os LPs**,
depois de normalizar TSC e o bit BSP do APIC base. Nenhum AP diverge em
nenhum controle VMX, FEATURE_CONTROL, MTRR ou PAT.

**A hipótese de um AP com controles VMX diferentes está refutada.**

### Identidade e microcode

- CPUID `000806D0` (family 6, model 141 = 0x8D, stepping 0), "Genuine Intel(R) CPU 0000";
- microcode `0x50` nos 16 LPs (`IA32_BIOS_SIGN_ID` e `/proc/cpuinfo`);
- `IA32_FEATURE_CONTROL` em todos: `locked=1`, `vmx_outside_smx=1`,
  `senter_global_enable=0` — estado correto e aberto para hipervisor.

### Capacidades VMX relevantes ao Hyper-V (cpu0; idênticas nos demais)

| Área | Valor | Avaliação |
|---|---|---|
| `VMX_BASIC` | revisão VMCS `0x13`, região 1280 B, memtype **WB (6)**, endereços >32 bits OK, *true controls* OK | normal |
| Pin-based may-1 | external-int exiting, NMI exiting, virtual NMIs, VNMI, **process posted interrupts** | completo |
| Proc-based 2 may-1 | APIC-access virt., EPT, RDTSCP, x2APIC virt., VPID, unrestricted guest, **APIC-reg virt.**, **virtual-interrupt delivery**, INVPCID, VMFUNC, VMCS shadowing, PML, EPT-VE, XSaves, **MBEC**, TSC scaling | suíte APICv completa |
| `EPT_VPID_CAP` | execute-only, walk length 4, UC+WB, páginas 2 MB **e 1 GB**, INVEPT single/all, INVVPID all-types (inclusive individual address e retaining-globals) | nada faltando |
| Entry/Exit may-1 | IA32e guest, load EFER/PAT/PERF_GLOBAL_CTRL, ack-intr-on-exit, host 64-bit | completo |
| `VMX_MISC` | preempt rate 7, CR3 targets 4, **sem** EPTP-switch via VMFUNC | opcional ausente |

Itens ausentes opcionais: SPP, duty cycling, bus-lock detection, UMWAIT
(`user_wait_pause`), EPTP switching, `EXIT_CTLS2`. Nenhum deles é requisito
do caminho de lançamento do `hvix64.exe`.

Erros de leitura uniformes em todos os LPs (benignos): `IA32_TSX_CTRL`
(ES/microcode sem TSX) e `IA32_VMX_EXIT_CTLS2` (recurso posterior a TGL).

### Topologia observada pelo Linux

Ordem de APIC IDs `0,2,4,...,14,1,3,...,15` — exatamente a mesma ordem que o
firmware grava na MADT; 8 cores × 2 threads; microcode `0x50` em todos.

### Comportamento x2APIC na sessão Linux

O Linux ativou **x2APIC com interrupt remapping** (`DMAR-IR: Enabled IRQ
remapping in x2apic mode`; queued invalidation; IOAPIC ID 2). A transição
física x2APIC + IR funciona nesta placa. O `dmesg` confirma ainda a MADT com
`LAPIC_NMI acpi_id[0x01]..[0x10]` — o defeito 1..16 visto também pelo Linux.
Nota: `GDS: Vulnerable: No microcode` — esperado neste payload ES; sem relação
com o bootloop.

## Comparação VMX-OFF × VMX-ON

Única diferença MSR em cpu0 (e em todos os LPs):

| MSR | VMX-ON | VMX-OFF |
|---|---|---|
| `IA32_FEATURE_CONTROL` | `0x0000000000000005` (locked + vmx-outside-smx) | `0x0000000000000001` (locked apenas) |

Além disso: flag `vmx` some do CPUID; todos os MSRs de capacidade
`IA32_VMX_*` permanecem idênticos (normal: descrevem o silício, não o estado).
Nenhum bit órfão apareceu na desabilitação — o caminho OFF é limpo, diferente
da máscara AVX-512 incompleta já documentada.

Conclusões adicionais:

1. A opção de Setup testada altera exatamente o prometido e restaura de forma
   confiável (base segura para o teste AVX3 isolado).
2. As capacidades VMX não dependem do toggle — a avaliação acima vale
   permanentemente para esta peça.

## Impacto nas hipóteses do projeto

| Hipótese (README) | Status após esta coleta |
|---|---|
| 3. Capacidades VMX/MSRs específicas do D0 insuficientes | **Refutada** para tudo que o Hyper-V consome no lançamento |
| Divergência entre APs durante MP launch | **Refutada** |
| 1. Defeito MADT/AP startup/APIC como causa primária | Segue principal; agora com detalhe: o Linux roda x2APIC+IR ignorando o campo UID dos NMIs, enquanto o Hyper-V consome esse mapeamento durante a própria transição APICv/x2APIC |
| 2. Máscara AVX3/CPUID/XSTATE | Continua segunda hipótese confirmada, teste ainda pendente |

A combinação "MADT corrigida entregue + Hyper-V ainda falhando com
`C0000005` no mesmo deslocamento" sugere um segundo contrato violado. Os
candidatos naturais, em ordem:

1. **Controle OpenCore pendente** (entrada one-shot armada): separa efeito da
   correção MADT de efeito genérico da cadeia UEFI/memory map.
2. **Teste BIOS AVX3 isolado** + repetir `dump_cpuid_windows.py`.
3. **Matriz BCD**, priorizando `HV 03 xAPIC LEGADO` (força caminho sem x2APIC,
   onde as entradas LAPIC NMI legadas são consumidas diretamente), depois
   `HV 05 MINIMO` e `HV 07 SEM XSAVE`.
4. KDNET conforme `HIPER_V_DEPURACAO_FUTURA.md` se todos falharem.

Nada aqui altera as regras de gravação: a candidata continua proibida até os
controles causais e a validação de programador externo.
