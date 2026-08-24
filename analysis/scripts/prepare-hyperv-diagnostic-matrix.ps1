param(
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'

$matrix = @(
    [ordered]@{
        Name = 'Windows - HV 01 BASELINE'
        Purpose = 'Hypervisor Microsoft ligado, VSM desligado, sem isoladores adicionais.'
        Settings = [ordered]@{}
    },
    [ordered]@{
        Name = 'Windows - HV 02 SEM IOMMU'
        Purpose = 'Isola DMAR, VT-d e interrupt remapping do lancamento inicial.'
        Settings = [ordered]@{ hypervisoriommupolicy = 'disable' }
    },
    [ordered]@{
        Name = 'Windows - HV 03 xAPIC LEGADO'
        Purpose = 'Isola a transicao x2APIC e a virtualizacao de APIC.'
        Settings = [ordered]@{
            x2apicpolicy = 'disable'
            uselegacyapicmode = 'yes'
        }
    },
    [ordered]@{
        Name = 'Windows - HV 04 UM LP'
        Purpose = 'Testa se a falha ocorre ao iniciar processadores auxiliares.'
        Settings = [ordered]@{ hypervisornumproc = '1' }
    },
    [ordered]@{
        Name = 'Windows - HV 05 MINIMO'
        Purpose = 'Combina um processador, xAPIC legado e IOMMU desligada.'
        Settings = [ordered]@{
            hypervisoriommupolicy = 'disable'
            x2apicpolicy = 'disable'
            uselegacyapicmode = 'yes'
            hypervisornumproc = '1'
            onecpu = 'yes'
        }
    },
    [ordered]@{
        Name = 'Windows - HV 06 SEM MBEC HW'
        Purpose = 'Isola a rota MBEC anunciada pelo processador ES.'
        Settings = [ordered]@{ hypervisorloadoptions = 'DISABLEHARDWAREMBEC' }
    },
    [ordered]@{
        Name = 'Windows - HV 07 SEM XSAVE'
        Purpose = 'Isola a enumeracao CPUID/XSTATE incoerente do processador ES.'
        Settings = [ordered]@{ xsavedisable = '1' }
    },
    [ordered]@{
        Name = 'Windows - HV 08 CAPTURA BOOTLOG'
        Purpose = 'Mostra bugcheck e registra ntbtlog.txt se o kernel chegar a carregar drivers.'
        Settings = [ordered]@{
            bootlog = 'yes'
            nocrashautoreboot = 'yes'
            sos = 'yes'
        }
    },
    [ordered]@{
        Name = 'Windows - HV 09 SEM vAPIC'
        Purpose = 'Desliga somente a rota de APIC virtual lida pelo hvloader (BCD 0x26000116).'
        Settings = [ordered]@{ hypervisorusevapic = 'no' }
    },
    [ordered]@{
        Name = 'Windows - HV 10 SEM POSTED INT'
        Purpose = 'Isola interrupcoes postadas de VMX/VT-d no hipervisor.'
        Settings = [ordered]@{ hypervisorloadoptions = 'DISABLEPOSTEDINTERRUPTS' }
    },
    [ordered]@{
        Name = 'Windows - HV 11 SEM IPI VIRTUAL'
        Purpose = 'Isola a virtualizacao de IPI/APIC do stepping ES.'
        Settings = [ordered]@{ hypervisorloadoptions = 'DISABLEIPIVIRTUALIZATION' }
    },
    [ordered]@{
        Name = 'Windows - HV 12 SEM SLAT EPT'
        Purpose = 'Forca o hipervisor a nao usar SLAT/EPT; teste de compatibilidade, nao solucao final.'
        Settings = [ordered]@{ hypervisordisableslat = 'yes' }
    },
    [ordered]@{
        Name = 'Windows - HV 13 APIC DEST FISICO'
        Purpose = 'Forca destino fisico do APIC sem alterar o modo x2APIC.'
        Settings = [ordered]@{ usephysicaldestination = 'yes' }
    },
    [ordered]@{
        Name = 'Windows - HV 14 SCHED CLASSICO'
        Purpose = 'Isola o scheduler Core padrao e a interpretacao SMT/topologia.'
        Settings = [ordered]@{ hypervisorschedulertype = 'classic' }
    },
    [ordered]@{
        Name = 'Windows - HV 15 SEM IOMMU HANDOFF'
        Purpose = 'Desliga o handoff vivo de IOMMU reconhecido diretamente pelo hvloader.'
        Settings = [ordered]@{ hypervisorloadoptions = 'IOMMULIVEHANDOFF=DISABLE' }
    },
    [ordered]@{
        Name = 'Windows - HV 16 IOMMU NAO ESCALAVEL'
        Purpose = 'Evita o caminho de IOMMU escalavel; opcao interna experimental.'
        Settings = [ordered]@{ hypervisorloadoptions = 'DISABLESCALABLEIOMMU' }
    },
    [ordered]@{
        Name = 'Windows - HV 17 TEMPO PMTIMER'
        Purpose = 'Forca a fonte de tempo de referencia ACPI PM Timer; opcao interna experimental.'
        Settings = [ordered]@{ hypervisorloadoptions = 'REFERENCETIMESOURCE=PMTIMER' }
    },
    [ordered]@{
        Name = 'Windows - HV 18 SINCRONIZA TSC'
        Purpose = 'Forca a sincronizacao de TSC entre LPs; opcao interna experimental.'
        Settings = [ordered]@{ hypervisorloadoptions = 'SYNCTSC' }
    }
)

if (-not $Apply) {
    Write-Host 'DRY RUN: nenhuma alteracao foi feita no BCD.'
    Write-Host 'A execucao elevada com -Apply fara backup do BCD e mantera {current} como padrao seguro, Hyper-V OFF.'
    Write-Host 'Entradas manuais que seriam criadas:'
    foreach ($test in $matrix) {
        $rendered = if ($test.Settings.Count) {
            ($test.Settings.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join ', '
        } else {
            'sem isoladores'
        }
        Write-Host "  $($test.Name): $rendered"
        Write-Host "    $($test.Purpose)"
    }
    exit 0
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Execute este script em um PowerShell elevado (Administrador).'
}

$bitLockerCommand = Get-Command Get-BitLockerVolume -ErrorAction SilentlyContinue
if ($bitLockerCommand) {
    $systemVolume = Get-BitLockerVolume -MountPoint $env:SystemDrive
    if ($systemVolume.ProtectionStatus -eq 'On') {
        throw 'BitLocker esta protegido. Salve a chave de recuperacao e suspenda a protecao manualmente antes de alterar o BCD.'
    }
}

function Invoke-BcdEdit {
    param(
        [Parameter(Mandatory)] [string[]]$BcdArguments,
        [switch]$AllowFailure
    )
    $output = (& bcdedit.exe @BcdArguments 2>&1) -join "`n"
    $exitCode = $LASTEXITCODE
    if (($exitCode -ne 0) -and (-not $AllowFailure)) {
        throw "bcdedit $($BcdArguments -join ' ') falhou ($exitCode):`n$output"
    }
    return [pscustomobject]@{ ExitCode = $exitCode; Output = $output }
}

function Remove-BcdValueIfPresent {
    param([Parameter(Mandatory)] [string]$Identifier, [Parameter(Mandatory)] [string]$Element)
    [void](Invoke-BcdEdit -BcdArguments @('/deletevalue', $Identifier, $Element) -AllowFailure)
}

$analysisDir = Split-Path -Parent $PSScriptRoot
$backupDir = Join-Path $analysisDir 'bcd-backups'
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupPath = Join-Path $backupDir "bcd-before-hyperv-matrix-$stamp.bcd"
$manifestPath = Join-Path $backupDir "hyperv-matrix-$stamp.json"

[void](Invoke-BcdEdit -BcdArguments @('/export', $backupPath))

# The machine must always return to this entry without human intervention.
[void](Invoke-BcdEdit -BcdArguments @('/set', '{current}', 'hypervisorlaunchtype', 'off'))
[void](Invoke-BcdEdit -BcdArguments @('/set', '{current}', 'vsmlaunchtype', 'off'))
[void](Invoke-BcdEdit -BcdArguments @('/default', '{current}'))
[void](Invoke-BcdEdit -BcdArguments @('/set', '{bootmgr}', 'displaybootmenu', 'yes'))
[void](Invoke-BcdEdit -BcdArguments @('/timeout', '15'))

$inheritedElements = @(
    'hypervisoriommupolicy',
    'x2apicpolicy',
    'uselegacyapicmode',
    'hypervisornumproc',
    'hypervisorloadoptions',
    'hypervisorusevapic',
    'hypervisordisableslat',
    'hypervisorschedulertype',
    'xsavedisable',
    'onecpu',
    'numproc',
    'usephysicaldestination',
    'bootlog',
    'nocrashautoreboot',
    'sos'
)
$created = @()

try {
    foreach ($test in $matrix) {
        $copy = Invoke-BcdEdit -BcdArguments @('/copy', '{current}', '/d', $test.Name)
        $match = [regex]::Match($copy.Output, '\{[0-9A-Fa-f-]{36}\}')
        if (-not $match.Success) {
            throw "Nao foi possivel extrair o identificador da nova entrada: $($copy.Output)"
        }
        $identifier = $match.Value
        $created += [pscustomobject]@{
            Name = $test.Name
            Purpose = $test.Purpose
            Identifier = $identifier
            Settings = $test.Settings
        }

        foreach ($element in $inheritedElements) {
            Remove-BcdValueIfPresent -Identifier $identifier -Element $element
        }
        [void](Invoke-BcdEdit -BcdArguments @('/set', $identifier, 'hypervisorlaunchtype', 'auto'))
        [void](Invoke-BcdEdit -BcdArguments @('/set', $identifier, 'vsmlaunchtype', 'off'))
        foreach ($setting in $test.Settings.GetEnumerator()) {
            [void](Invoke-BcdEdit -BcdArguments @('/set', $identifier, [string]$setting.Key, [string]$setting.Value))
        }
        [void](Invoke-BcdEdit -BcdArguments @('/displayorder', $identifier, '/addlast') -AllowFailure)
    }
} catch {
    foreach ($entry in $created) {
        [void](Invoke-BcdEdit -BcdArguments @('/delete', $entry.Identifier) -AllowFailure)
    }
    throw
}

$manifest = [ordered]@{
    CreatedAt = (Get-Date).ToString('o')
    BcdBackup = $backupPath
    SafeDefault = '{current}'
    SafeDefaultHypervisor = 'off'
    TimeoutSeconds = 15
    TestEntries = $created
    PreTestEvidence = [ordered]@{
        LastBootUpTime = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToString('o')
        Ntbtlog = if (Test-Path -LiteralPath "$env:SystemRoot\ntbtlog.txt") {
            $bootLog = Get-Item -LiteralPath "$env:SystemRoot\ntbtlog.txt"
            [ordered]@{
                Exists = $true
                Length = $bootLog.Length
                LastWriteTime = $bootLog.LastWriteTime.ToString('o')
            }
        } else {
            [ordered]@{ Exists = $false }
        }
    }
}
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

Write-Host "Backup integral do BCD: $backupPath"
Write-Host "Manifesto das entradas: $manifestPath"
Write-Host 'Padrao seguro: {current}, Hyper-V OFF, menu de 15 segundos.'
Write-Host 'Nenhuma entrada de teste foi agendada para o proximo boot; escolha uma manualmente no menu.'
foreach ($entry in $created) {
    Write-Host "  $($entry.Identifier)  $($entry.Name)"
}
