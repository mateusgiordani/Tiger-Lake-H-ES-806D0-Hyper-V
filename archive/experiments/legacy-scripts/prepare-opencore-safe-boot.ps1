param(
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'

if (-not $Apply) {
    Write-Host 'DRY RUN: nenhuma alteracao foi feita.'
    Write-Host 'Com -Apply o script exporta o BCD e torna {current} explicitamente seguro:'
    Write-Host '  hypervisorlaunchtype = off'
    Write-Host '  vsmlaunchtype        = off'
    Write-Host 'Ele nao cria entrada Hyper-V, nao agenda boot e nao reinicia.'
    exit 0
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Execute em um PowerShell como Administrador.'
}

$bitLocker = Get-BitLockerVolume -MountPoint $env:SystemDrive -ErrorAction Stop
if ($bitLocker.ProtectionStatus -eq 'On') {
    throw 'BitLocker esta protegido. Nao altere o BCD antes de salvar a chave e suspender a protecao.'
}

$analysisDir = Split-Path -Parent $PSScriptRoot
$backupDir = Join-Path $analysisDir 'bcd-backups'
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupPath = Join-Path $backupDir "bcd-before-opencore-$stamp.bcd"
$beforePath = Join-Path $backupDir "current-before-opencore-$stamp.txt"
$afterPath = Join-Path $backupDir "current-after-opencore-$stamp.txt"
$manifestPath = Join-Path $backupDir "opencore-safe-boot-$stamp.json"

$before = (& bcdedit.exe /enum '{current}' 2>&1) -join "`r`n"
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao ler {current}:`n$before"
}
$before | Set-Content -LiteralPath $beforePath -Encoding UTF8

& bcdedit.exe /export $backupPath
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao exportar o BCD para $backupPath"
}

& bcdedit.exe /set '{current}' hypervisorlaunchtype off
if ($LASTEXITCODE -ne 0) {
    throw 'Falha ao definir hypervisorlaunchtype off.'
}
& bcdedit.exe /set '{current}' vsmlaunchtype off
if ($LASTEXITCODE -ne 0) {
    throw 'Falha ao definir vsmlaunchtype off.'
}
& bcdedit.exe /default '{current}'
if ($LASTEXITCODE -ne 0) {
    throw 'Falha ao manter {current} como entrada padrao.'
}

$after = (& bcdedit.exe /enum '{current}' 2>&1) -join "`r`n"
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao verificar {current}:`n$after"
}
$after | Set-Content -LiteralPath $afterPath -Encoding UTF8

if ($after -notmatch '(?im)^hypervisorlaunchtype\s+Off\s*$') {
    throw 'A verificacao nao encontrou hypervisorlaunchtype Off.'
}
if ($after -notmatch '(?im)^vsmlaunchtype\s+Off\s*$') {
    throw 'A verificacao nao encontrou vsmlaunchtype Off.'
}

$manifest = [ordered]@{
    CreatedAt = (Get-Date).ToString('o')
    BcdBackup = $backupPath
    BeforeText = $beforePath
    AfterText = $afterPath
    DefaultEntry = '{current}'
    HypervisorLaunchType = 'off'
    VsmLaunchType = 'off'
    RebootScheduled = $false
    HyperVEntryCreated = $false
}
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

Write-Host "Backup integral do BCD: $backupPath"
Write-Host "Manifesto: $manifestPath"
Write-Host '{current} permanece padrao, Hyper-V OFF e VSM OFF.'
Write-Host 'Nenhum reboot foi agendado e nenhuma entrada Hyper-V foi criada.'
Write-Host ''
Write-Host $after
