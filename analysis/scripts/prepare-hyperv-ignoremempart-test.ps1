param(
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$registryPath = 'HKLM:\SYSTEM\CurrentControlSet\Control\Hypervisor'
$nativeRegistryPath = 'HKLM\SYSTEM\CurrentControlSet\Control\Hypervisor'
$valueName = 'IgnoreMemPart'

if (-not (Test-Path -LiteralPath $registryPath)) {
    throw "A chave esperada nao existe: $registryPath"
}

$key = Get-Item -LiteralPath $registryPath
$previousValue = $key.GetValue($valueName, $null, 'DoNotExpandEnvironmentNames')
$valueExisted = $null -ne $previousValue
$previousKind = if ($valueExisted) { [string]$key.GetValueKind($valueName) } else { $null }

Write-Host "Estado atual: $registryPath\$valueName = $(if ($valueExisted) { $previousValue } else { '<ausente>' })"
Write-Host 'Teste proposto: definir IgnoreMemPart=0. O script nao reinicia e nao liga o Hyper-V.'

if (-not $Apply) {
    Write-Host 'DRY RUN: nenhuma alteracao foi feita no Registro.'
    Write-Host 'Use -Apply somente depois da matriz BCD principal e com {current} seguro como padrao.'
    exit 0
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Execute este script em um PowerShell elevado (Administrador).'
}

if ($valueExisted -and ($previousKind -ne 'DWord')) {
    throw "Tipo inesperado para ${valueName}: $previousKind. Nenhuma alteracao foi feita."
}

$analysisDir = Split-Path -Parent $PSScriptRoot
$backupDir = Join-Path $analysisDir 'registry-backups'
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$regBackup = Join-Path $backupDir "hypervisor-control-before-ignoremempart-$stamp.reg"
$manifestPath = Join-Path $backupDir "ignoremempart-test-$stamp.json"

& reg.exe export $nativeRegistryPath $regBackup /y | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao exportar a chave do Registro para $regBackup. Nenhuma alteracao foi feita."
}

$manifest = [ordered]@{
    Version = 1
    CreatedAt = (Get-Date).ToString('o')
    RegistryPath = $registryPath
    NativeRegistryPath = $nativeRegistryPath
    ValueName = $valueName
    Previous = [ordered]@{
        Existed = $valueExisted
        Kind = $previousKind
        Value = $previousValue
    }
    RegBackup = $regBackup
    TestValue = 0
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

New-ItemProperty -LiteralPath $registryPath -Name $valueName -PropertyType DWord -Value 0 -Force | Out-Null
$observed = (Get-ItemPropertyValue -LiteralPath $registryPath -Name $valueName)
if ($observed -ne 0) {
    throw "A verificacao apos escrita retornou $observed em vez de 0. Use o backup $regBackup."
}

Write-Host "Backup integral da chave: $regBackup"
Write-Host "Manifesto para restauracao: $manifestPath"
Write-Host 'IgnoreMemPart=0 aplicado. Nenhum BCD foi alterado e nenhum reboot foi agendado.'
Write-Host 'Depois do teste, restaure com restore-hyperv-ignoremempart-test.ps1 usando o manifesto acima.'
