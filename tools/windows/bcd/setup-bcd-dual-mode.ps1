param(
    [switch]$Apply,
    [ValidateRange(3, 60)] [int]$TimeoutSeconds = 8
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'BcdCommon.ps1')

$statePath = Get-BcdStatePath

if (-not $Apply) {
    Write-Host 'DRY RUN: nenhuma alteracao foi feita no BCD.'
    Write-Host 'Com -Apply, o script ira:'
    Write-Host '  1. exigir PowerShell elevado e BitLocker suspenso;'
    Write-Host '  2. exportar um backup integral do BCD;'
    Write-Host '  3. copiar a entrada atual para Windows - Hyper-V diagnostic (XSAVE off);'
    Write-Host '  4. tornar a entrada atual Windows - Normal (AVX, Hyper-V off);'
    Write-Host "  5. manter a entrada normal como default e usar timeout de $TimeoutSeconds segundos;"
    Write-Host '  6. cancelar qualquer /bootsequence antigo;'
    Write-Host "  7. gravar os GUIDs em $statePath."
    Write-Host ''
    Write-Host 'Para aplicar: .\tools\windows\bcd\setup-bcd-dual-mode.ps1 -Apply'
    exit 0
}

Assert-IsAdministrator
Assert-BitLockerReady

if (Test-Path -LiteralPath $statePath) {
    throw "Ja existe um estado gerenciado em $statePath. Audite ou remova a configuracao existente antes de executar novamente."
}

$normalIdentifier = Get-CurrentBcdIdentifier
$backupPath = New-BcdBackup -Label 'before-dual-mode-setup'
$diagnosticIdentifier = $null

try {
    $copy = Invoke-BcdEdit -BcdArguments @(
        '/copy', $normalIdentifier,
        '/d', 'Windows - Hyper-V diagnostic (XSAVE off)'
    )
    $match = [regex]::Match($copy.Output, '\{[0-9A-Fa-f-]{36}\}')
    if (-not $match.Success) {
        throw "Nao foi possivel extrair o GUID da entrada copiada:`n$($copy.Output)"
    }
    $diagnosticIdentifier = $match.Value

    [void](Invoke-BcdEdit -BcdArguments @('/set', $diagnosticIdentifier, 'hypervisorlaunchtype', 'auto'))
    [void](Invoke-BcdEdit -BcdArguments @('/set', $diagnosticIdentifier, 'xsavedisable', '1'))
    [void](Invoke-BcdEdit -BcdArguments @('/set', $diagnosticIdentifier, 'vsmlaunchtype', 'off'))
    [void](Invoke-BcdEdit -BcdArguments @('/set', $diagnosticIdentifier, 'description', 'Windows - Hyper-V diagnostic (XSAVE off)'))
    [void](Invoke-BcdEdit -BcdArguments @('/displayorder', $diagnosticIdentifier, '/addlast'))

    [void](Invoke-BcdEdit -BcdArguments @('/set', $normalIdentifier, 'hypervisorlaunchtype', 'off'))
    [void](Remove-BcdValueIfPresent -Identifier $normalIdentifier -Element 'xsavedisable')
    [void](Invoke-BcdEdit -BcdArguments @('/set', $normalIdentifier, 'vsmlaunchtype', 'off'))
    [void](Invoke-BcdEdit -BcdArguments @('/set', $normalIdentifier, 'description', 'Windows - Normal (AVX, Hyper-V off)'))
    [void](Invoke-BcdEdit -BcdArguments @('/default', $normalIdentifier))
    [void](Invoke-BcdEdit -BcdArguments @('/set', '{bootmgr}', 'displaybootmenu', 'yes'))
    [void](Invoke-BcdEdit -BcdArguments @('/timeout', [string]$TimeoutSeconds))
    [void](Remove-BcdValueIfPresent -Identifier '{bootmgr}' -Element 'bootsequence')

    $stateDirectory = Split-Path -Parent $statePath
    New-Item -ItemType Directory -Path $stateDirectory -Force | Out-Null
    $state = [ordered]@{
        SchemaVersion = 1
        CreatedAt = (Get-Date).ToString('o')
        BackupPath = $backupPath
        NormalIdentifier = $normalIdentifier
        DiagnosticIdentifier = $diagnosticIdentifier
        NormalDescription = 'Windows - Normal (AVX, Hyper-V off)'
        DiagnosticDescription = 'Windows - Hyper-V diagnostic (XSAVE off)'
        TimeoutSeconds = $TimeoutSeconds
    }
    $state | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $statePath -Encoding UTF8
} catch {
    if ($diagnosticIdentifier) {
        [void](Invoke-BcdEdit -BcdArguments @('/delete', $diagnosticIdentifier) -AllowFailure)
    }
    Write-Error "A configuracao falhou. O backup permanece em $backupPath. Erro: $($_.Exception.Message)"
    exit 1
}

Write-Host 'Configuracao concluida; nenhum reinicio foi iniciado.'
Write-Host "Backup: $backupPath"
Write-Host "Estado: $statePath"
Write-Host "Entrada normal/default: $normalIdentifier"
Write-Host "Entrada diagnostica:   $diagnosticIdentifier"
Write-Host 'Execute audit-bcd-dual-mode.ps1 antes de reiniciar.'
