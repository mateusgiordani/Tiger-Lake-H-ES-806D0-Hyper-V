param(
    [switch]$Apply,
    [switch]$Restart,
    [string]$StatePath
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'BcdCommon.ps1')

function Invoke-HyperVDiagnosticOnce {
param(
    [switch]$Apply,
    [switch]$Restart,
    [string]$StatePath
)

if ($Restart -and (-not $Apply)) {
    throw '-Restart so pode ser usado junto com -Apply.'
}
if (-not $StatePath) {
    $StatePath = Get-BcdStatePath
}

if (-not $Apply) {
    Write-Host 'DRY RUN: nenhum boot foi agendado.'
    Write-Host "O script lera o GUID do fallback Hyper-V em $StatePath e usara /bootsequence somente para o proximo boot."
    Write-Host 'Para agendar sem reiniciar:'
    Write-Host '  .\tools\windows\bcd\schedule-hyperv-diagnostic-once.ps1 -Apply'
    Write-Host 'Para agendar e reiniciar imediatamente:'
    Write-Host '  .\tools\windows\bcd\schedule-hyperv-diagnostic-once.ps1 -Apply -Restart'
    return
}

Assert-IsAdministrator
$state = Read-BcdState -StatePath $StatePath
$diagnosticIdentifier = [string]$state.DiagnosticIdentifier
[void](Invoke-BcdEdit -BcdArguments @('/enum', $diagnosticIdentifier, '/v'))
[void](Invoke-BcdEdit -BcdArguments @('/bootsequence', $diagnosticIdentifier))

Write-Host "Proximo boot agendado uma unica vez: $diagnosticIdentifier"
Write-Host 'Depois dele, o Boot Manager retornara a entrada normal/default.'

if ($Restart) {
    Write-Host 'Reiniciando agora...'
    & shutdown.exe /r /t 0
} else {
    Write-Host 'Nenhum reinicio foi iniciado.'
}
}

if ($MyInvocation.InvocationName -ne '.') {
    Invoke-HyperVDiagnosticOnce @PSBoundParameters
}
