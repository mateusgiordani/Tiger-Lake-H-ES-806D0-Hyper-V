param(
    [Parameter(Mandatory)] [string]$ManifestPath,
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$resolvedManifest = Resolve-Path -LiteralPath $ManifestPath
$manifest = Get-Content -LiteralPath $resolvedManifest -Raw | ConvertFrom-Json

$expectedPath = 'HKLM:\SYSTEM\CurrentControlSet\Control\Hypervisor'
$expectedNativePath = 'HKLM\SYSTEM\CurrentControlSet\Control\Hypervisor'
$expectedName = 'IgnoreMemPart'
if (($manifest.Version -ne 1) -or
    ($manifest.RegistryPath -ne $expectedPath) -or
    ($manifest.NativeRegistryPath -ne $expectedNativePath) -or
    ($manifest.ValueName -ne $expectedName)) {
    throw 'Manifesto incompativel ou alvo inesperado. Nenhuma alteracao foi feita.'
}

$description = if ($manifest.Previous.Existed) {
    "restaurar $expectedName=$($manifest.Previous.Value), tipo $($manifest.Previous.Kind)"
} else {
    "remover $expectedName, pois ele nao existia"
}
Write-Host "Acao: $description"

if (-not $Apply) {
    Write-Host 'DRY RUN: nenhuma alteracao foi feita no Registro.'
    exit 0
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Execute este script em um PowerShell elevado (Administrador).'
}

if (-not (Test-Path -LiteralPath $expectedPath)) {
    throw "A chave esperada nao existe: $expectedPath"
}

$analysisDir = Split-Path -Parent $PSScriptRoot
$backupDir = Join-Path $analysisDir 'registry-backups'
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$preRestoreBackup = Join-Path $backupDir "hypervisor-control-before-restore-$stamp.reg"
& reg.exe export $expectedNativePath $preRestoreBackup /y | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao exportar o estado atual para $preRestoreBackup. Nenhuma alteracao foi feita."
}

if ($manifest.Previous.Existed) {
    if ($manifest.Previous.Kind -ne 'DWord') {
        throw "Tipo de restauracao nao suportado: $($manifest.Previous.Kind). Use o backup .reg do manifesto."
    }
    New-ItemProperty -LiteralPath $expectedPath -Name $expectedName -PropertyType DWord -Value ([uint32]$manifest.Previous.Value) -Force | Out-Null
} else {
    Remove-ItemProperty -LiteralPath $expectedPath -Name $expectedName -ErrorAction SilentlyContinue
}

Write-Host "Backup do estado anterior a restauracao: $preRestoreBackup"
Write-Host "Estado original restaurado conforme $resolvedManifest"
Write-Host 'Nenhum BCD foi alterado e nenhum reboot foi agendado.'
