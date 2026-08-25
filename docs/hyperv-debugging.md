# DepuraÃ§Ã£o futura do reset precoce do Hyper-V

## Quando usar

Usar esta etapa somente se nenhuma entrada da matriz BCD iniciar. Nesse ponto, testes de configuraÃ§Ã£o jÃ¡ terÃ£o separado AP/SMP, x2APIC, IOMMU, MBEC, XSAVE e a partiÃ§Ã£o de metadados; o dado que falta serÃ¡ o Ãºltimo ponto executado dentro de `hvloader.dll`/`hvix64.exe`.

Nada desta preparaÃ§Ã£o foi aplicado. A mÃ¡quina nÃ£o possui `kdnet.exe` nem WinDbg instalados neste momento.

## Hardware jÃ¡ verificado

O adaptador fÃ­sico cabeado Ã©:

```text
Realtek PCIe GbE Family Controller
PCI\VEN_10EC&DEV_8168&SUBSYS_012310EC&REV_15
```

Vendor `10EC`, device `8168` aparece na lista oficial de NICs compatÃ­veis com KDNET no Windows 11. Usar esse Ethernet fÃ­sico; Wi-Fi, Tailscale, Radmin e adaptadores virtuais nÃ£o servem para o transporte prÃ©-kernel.

Fonte: [Microsoft â€” NICs Ethernet compatÃ­veis com KDNET](https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/supported-ethernet-nics-for-network-kernel-debugging-in-windows-11).

## PrÃ©-requisitos

1. Um segundo PC Windows na mesma rede cabeada, que continuarÃ¡ ligado executando o WinDbg.
2. WinDbg/Debugging Tools atuais nos dois PCs. A distribuiÃ§Ã£o atual inclui `kdnet.exe` e `VerifiedNicList.xml`.
3. Chave de recuperaÃ§Ã£o do BitLocker salva e proteÃ§Ã£o suspensa durante a alteraÃ§Ã£o do BCD.
4. Matriz BCD jÃ¡ criada, com `{current}` ainda como padrÃ£o seguro e `hypervisorlaunchtype off`.
5. Backup do BCD imediatamente antes de ativar a depuraÃ§Ã£o.

## ConfiguraÃ§Ã£o recomendada

No PC host, escolher um IP IPv4 estÃ¡vel e uma porta UDP entre `50000` e `50039`. No alvo, em PowerShell elevado, executar a ferramenta oficial com **somente depuraÃ§Ã£o do hipervisor**:

```powershell
kdnet.exe IP_DO_PC_HOST 50000 -h
```

Guardar a chave exibida. O `kdnet` configura o transporte global; depois marcar para depuraÃ§Ã£o somente o GUID da entrada `HV 05 MINIMO`, obtido no manifesto da matriz:

```powershell
bcdedit /set "{GUID_DA_ENTRADA_HV_05}" hypervisordebug on
```

NÃ£o alterar o padrÃ£o `{current}` e nÃ£o usar `bootsequence`. No host, iniciar o WinDbg antes de escolher manualmente a entrada de teste:

```text
windbgx.exe -k net:port=50000,key=CHAVE_GERADA
```

A Microsoft documenta `-h` como depuraÃ§Ã£o do hipervisor e `bcdedit /set hypervisordebug on` como seu equivalente. Se depuraÃ§Ã£o do kernel e do hipervisor forem ativadas juntas, o hipervisor usa a porta seguinte; por isso esta primeira captura deve usar apenas `-h`.

Fonte: [Microsoft â€” configuraÃ§Ã£o automÃ¡tica do KDNET](https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/setting-up-a-network-debugging-connection-automatically).

## O que capturar

- todo o texto do WinDbg desde a conexÃ£o;
- endereÃ§o da Ãºltima parada/exceÃ§Ã£o e mÃ³dulo que o contÃ©m;
- registradores e stack disponÃ­veis;
- se todos os 16 processadores responderam ou em qual AP parou;
- qualquer indicaÃ§Ã£o de VM-entry failure, MSR load, APIC, IOMMU, EPT ou machine check;
- instante visual do alvo: antes do logo, no logo, pontos girando ou reset imediato.

Mesmo sem PDB privado da Microsoft, o RVA no `hvix64.exe` local permite correlacionar o ponto com a cÃ³pia exata jÃ¡ hasheada e com as rotas estÃ¡ticas levantadas.

## RecuperaÃ§Ã£o

Depois da captura, iniciar `{current}` seguro e remover apenas o sinalizador da entrada de teste:

```powershell
bcdedit /deletevalue "{GUID_DA_ENTRADA_HV_05}" hypervisordebug
```

Manter o backup do BCD e a chave do KDNET junto do log. Se a rede nÃ£o conectar antes do reset, nÃ£o repetir indefinidamente: revisar o `VerifiedNicList.xml` da versÃ£o instalada e partir para transporte serial somente se a placa expuser UART funcional.
