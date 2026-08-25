param(
    [Parameter(Mandatory)] [string]$ManifestPath,
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$resolvedManifest = Resolve-Path -LiteralPath $ManifestPath
$manifest = Get-Content -LiteralPath $resolvedManifest -Raw | ConvertFrom-Json

if (-not $manifest.TestEntries) {
    throw 'O manifesto não contém TestEntries.'
}

foreach ($entry in $manifest.TestEntries) {
    if ($entry.Identifier -notmatch '^\{[0-9A-Fa-f-]{36}\}$') {
        throw "Identificador inválido no manifesto: $($entry.Identifier)"
    }
}

if (-not $Apply) {
    Write-Host 'DRY RUN: nenhuma entrada foi removida.'
    Write-Host "Manifesto: $resolvedManifest"
    foreach ($entry in $manifest.TestEntries) {
        Write-Host "  removeria $($entry.Identifier)  $($entry.Name)"
    }
    exit 0
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Execute este script em um PowerShell elevado (Administrador).'
}

function Invoke-BcdEdit {
    param([Parameter(Mandatory)] [string[]]$BcdArguments)
    $output = (& bcdedit.exe @BcdArguments 2>&1) -join "`n"
    if ($LASTEXITCODE -ne 0) {
        throw "bcdedit $($BcdArguments -join ' ') falhou ($LASTEXITCODE):`n$output"
    }
}

$analysisDir = Split-Path -Parent $PSScriptRoot
$backupDir = Join-Path $analysisDir 'bcd-backups'
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$cleanupBackup = Join-Path $backupDir "bcd-before-matrix-removal-$stamp.bcd"
Invoke-BcdEdit -BcdArguments @('/export', $cleanupBackup)

foreach ($entry in $manifest.TestEntries) {
    Invoke-BcdEdit -BcdArguments @('/delete', [string]$entry.Identifier)
}

Invoke-BcdEdit -BcdArguments @('/set', '{current}', 'hypervisorlaunchtype', 'off')
Invoke-BcdEdit -BcdArguments @('/set', '{current}', 'vsmlaunchtype', 'off')
Invoke-BcdEdit -BcdArguments @('/default', '{current}')
Invoke-BcdEdit -BcdArguments @('/set', '{bootmgr}', 'displaybootmenu', 'yes')
Invoke-BcdEdit -BcdArguments @('/timeout', '15')

Write-Host "Backup antes da remoção: $cleanupBackup"
Write-Host 'Entradas da matriz removidas. {current} continua como padrão seguro, Hyper-V OFF.'
