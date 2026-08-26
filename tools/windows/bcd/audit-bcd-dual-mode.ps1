param(
    [string]$StatePath
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'BcdCommon.ps1')

function Invoke-BcdDualModeAudit {
param(
    [string]$StatePath
)

Assert-IsAdministrator
if (-not $StatePath) {
    $StatePath = Get-BcdStatePath
}
$state = Read-BcdState -StatePath $StatePath

$normal = Invoke-BcdEdit -BcdArguments @('/enum', [string]$state.NormalIdentifier, '/v')
$diagnostic = Invoke-BcdEdit -BcdArguments @('/enum', [string]$state.DiagnosticIdentifier, '/v')
$bootManager = Invoke-BcdEdit -BcdArguments @('/enum', '{bootmgr}', '/v')

$checks = @(
    [pscustomobject]@{
        Name = 'Normal: hypervisorloadoptions ausente'
        Passed = $normal.Output -notmatch '(?im)^hypervisorloadoptions\s+'
    },
    [pscustomobject]@{
        Name = 'Normal: Hyper-V desligado'
        Passed = $normal.Output -match '(?im)^hypervisorlaunchtype\s+Off\s*$'
    },
    [pscustomobject]@{
        Name = 'Normal: vsmlaunchtype ausente'
        Passed = $normal.Output -notmatch '(?im)^vsmlaunchtype\s+'
    },
    [pscustomobject]@{
        Name = 'Normal: xsavedisable ausente'
        Passed = $normal.Output -notmatch '(?im)^xsavedisable\s+'
    },
    [pscustomobject]@{
        Name = 'Diagnostico: Hyper-V automatico'
        Passed = $diagnostic.Output -match '(?im)^hypervisorlaunchtype\s+Auto\s*$'
    },
    [pscustomobject]@{
        Name = 'Diagnostico: VSM desligado'
        Passed = $diagnostic.Output -match '(?im)^vsmlaunchtype\s+Off\s*$'
    },
    [pscustomobject]@{
        Name = 'Fallback: MBEC por hardware desabilitado'
        Passed = $diagnostic.Output -match '(?im)^hypervisorloadoptions\s+DISABLEHARDWAREMBEC\s*$'
    },
    [pscustomobject]@{
        Name = 'Fallback: xsavedisable ausente'
        Passed = $diagnostic.Output -notmatch '(?im)^xsavedisable\s+'
    },
    [pscustomobject]@{
        Name = 'Boot Manager: normal e o default'
        Passed = $bootManager.Output -match ('(?im)^default\s+' + [regex]::Escape([string]$state.NormalIdentifier) + '\s*$')
    },
    [pscustomobject]@{
        Name = 'Boot Manager: menu visivel'
        Passed = $bootManager.Output -match '(?im)^displaybootmenu\s+Yes\s*$'
    }
)

$checks | Format-Table -AutoSize Name, Passed
Write-Host "Hypervisor presente neste boot: $((Get-CimInstance Win32_ComputerSystem).HypervisorPresent)"
Write-Host "Estado: $StatePath"
Write-Host "Backup inicial: $($state.BackupPath)"

$failed = @($checks | Where-Object { -not $_.Passed })
if ($failed.Count -gt 0) {
    Write-Host ''
    Write-Host 'Saida bruta para inspecao:'
    Write-Host '--- NORMAL ---'
    Write-Host $normal.Output
    Write-Host '--- DIAGNOSTICO ---'
    Write-Host $diagnostic.Output
    Write-Host '--- BOOT MANAGER ---'
    Write-Host $bootManager.Output
    throw "$($failed.Count) verificacao(oes) falharam. Nao reinicie ate revisar a saida acima."
}

Write-Host 'Auditoria aprovada. A entrada normal continuara sendo o default.'
}

if ($MyInvocation.InvocationName -ne '.') {
    Invoke-BcdDualModeAudit @PSBoundParameters
}
