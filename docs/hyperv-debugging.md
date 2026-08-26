# Depuração futura do reset precoce do Hyper-V

## Quando usar

Use esta etapa somente para localizar a divergência entre o baseline que falha
com MBEC por hardware ativo e o boot que passa com
`DISABLEHARDWAREMBEC`. A matriz BCD já isolou MBEC; o dado que falta é o último
ponto executado dentro de `hvloader.dll`/`hvix64.exe` e os controles VMX
efetivamente selecionados.

Nada desta preparação foi aplicado. A máquina não possui `kdnet.exe` nem WinDbg instalados neste momento.

## Hardware já verificado

O adaptador físico cabeado é:

```text
Realtek PCIe GbE Family Controller
PCI\VEN_10EC&DEV_8168&SUBSYS_012310EC&REV_15
```

Vendor `10EC`, device `8168` aparece na lista oficial de NICs compatíveis com KDNET no Windows 11. Usar esse Ethernet físico; Wi-Fi, Tailscale, Radmin e adaptadores virtuais não servem para o transporte pré-kernel.

Fonte: [Microsoft — NICs Ethernet compatíveis com KDNET](https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/supported-ethernet-nics-for-network-kernel-debugging-in-windows-11).

## Pré-requisitos

1. Um segundo PC Windows na mesma rede cabeada, que continuará ligado executando o WinDbg.
2. WinDbg/Debugging Tools atuais nos dois PCs. A distribuição atual inclui `kdnet.exe` e `VerifiedNicList.xml`.
3. Chave de recuperação do BitLocker salva e proteção suspensa durante a alteração do BCD.
4. Matriz BCD já criada, com `{current}` ainda como padrão seguro e `hypervisorlaunchtype off`.
5. Backup do BCD imediatamente antes de ativar a depuração.

## Configuração recomendada

No PC host, escolher um IP IPv4 estável e uma porta UDP entre `50000` e `50039`. No alvo, em PowerShell elevado, executar a ferramenta oficial com **somente depuração do hipervisor**:

```powershell
kdnet.exe IP_DO_PC_HOST 50000 -h
```

Guardar a chave exibida. O `kdnet` configura o transporte global; depois marcar para depuração somente o GUID da entrada `HV 05 MINIMO`, obtido no manifesto da matriz:

```powershell
bcdedit /set "{GUID_DA_ENTRADA_HV_05}" hypervisordebug on
```

Não alterar o padrão `{current}` e não usar `bootsequence`. No host, iniciar o WinDbg antes de escolher manualmente a entrada de teste:

```text
windbgx.exe -k net:port=50000,key=CHAVE_GERADA
```

A Microsoft documenta `-h` como depuração do hipervisor e `bcdedit /set hypervisordebug on` como seu equivalente. Se depuração do kernel e do hipervisor forem ativadas juntas, o hipervisor usa a porta seguinte; por isso esta primeira captura deve usar apenas `-h`.

Fonte: [Microsoft — configuração automática do KDNET](https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/setting-up-a-network-debugging-connection-automatically).

## O que capturar

- todo o texto do WinDbg desde a conexão;
- endereço da última parada/exceção e módulo que o contém;
- registradores e stack disponíveis;
- se todos os 16 processadores responderam ou em qual AP parou;
- qualquer indicação de VM-entry failure, MSR load, APIC, IOMMU, EPT ou machine check;
- instante visual do alvo: antes do logo, no logo, pontos girando ou reset imediato.

Mesmo sem PDB privado da Microsoft, o RVA no `hvix64.exe` local permite correlacionar o ponto com a cópia exata já hasheada e com as rotas estáticas levantadas.

## Recuperação

Depois da captura, iniciar `{current}` seguro e remover apenas o sinalizador da entrada de teste:

```powershell
bcdedit /deletevalue "{GUID_DA_ENTRADA_HV_05}" hypervisordebug
```

Manter o backup do BCD e a chave do KDNET junto do log. Se a rede não conectar antes do reset, não repetir indefinidamente: revisar o `VerifiedNicList.xml` da versão instalada e partir para transporte serial somente se a placa expuser UART funcional.
