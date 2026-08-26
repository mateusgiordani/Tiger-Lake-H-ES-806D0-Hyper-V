param(
    [switch]$Apply,
    [string]$StatePath
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'BcdCommon.ps1')

function Remove-BcdDualMode {
param(
    [switch]$Apply,
    [string]$StatePath
)

if (-not $StatePath) {
    $StatePath = Get-BcdStatePath
}

if (-not $Apply) {
    Write-Host 'DRY RUN: nenhuma entrada foi removida.'
    Write-Host "Com -Apply, o script usara $StatePath, fara backup e removera somente a entrada diagnostica gerenciada."
    Write-Host 'A entrada normal sera preservada como default, com Hyper-V desligado e XSAVE normal.'
    return
}

Assert-IsAdministrator
Assert-BitLockerReady
$state = Read-BcdState -StatePath $StatePath
$currentIdentifier = Get-CurrentBcdIdentifier
$normalIdentifier = [string]$state.NormalIdentifier
$diagnosticIdentifier = [string]$state.DiagnosticIdentifier

if ($currentIdentifier -eq $diagnosticIdentifier) {
    throw 'Voce esta iniciado pela entrada diagnostica. Reinicie pela entrada normal antes de remove-la.'
}
if ($currentIdentifier -ne $normalIdentifier) {
    throw "A entrada atual ($currentIdentifier) nao e a entrada normal gerenciada ($normalIdentifier). Operacao recusada."
}

$backupPath = New-BcdBackup -Label 'before-dual-mode-removal'
[void](Invoke-BcdEdit -BcdArguments @('/set', $normalIdentifier, 'hypervisorlaunchtype', 'off'))
[void](Remove-BcdValueIfPresent -Identifier $normalIdentifier -Element 'hypervisorloadoptions')
[void](Remove-BcdValueIfPresent -Identifier $normalIdentifier -Element 'xsavedisable')
[void](Remove-BcdValueIfPresent -Identifier $normalIdentifier -Element 'vsmlaunchtype')
[void](Invoke-BcdEdit -BcdArguments @('/default', $normalIdentifier))
[void](Remove-BcdValueIfPresent -Identifier '{bootmgr}' -Element 'bootsequence')
[void](Invoke-BcdEdit -BcdArguments @('/delete', $diagnosticIdentifier))

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$archivedStatePath = "$StatePath.removed-$stamp"
Move-Item -LiteralPath $StatePath -Destination $archivedStatePath

Write-Host 'Entrada diagnostica removida; nenhum reinicio foi iniciado.'
Write-Host "Backup: $backupPath"
Write-Host "Estado arquivado: $archivedStatePath"
Write-Host "Entrada normal/default preservada: $normalIdentifier"
}

if ($MyInvocation.InvocationName -ne '.') {
    Remove-BcdDualMode @PSBoundParameters
}
