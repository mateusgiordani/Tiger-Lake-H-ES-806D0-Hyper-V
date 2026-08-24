param(
    [Parameter(Mandatory)]
    [string]$ManifestPath,
    [switch]$Apply,
    [switch]$Cancel
)

$ErrorActionPreference = 'Stop'
$expectedConfigHash = 'A541BA6A79F73F9A5A932BFE105B712B446553C579A2DAAC8F4FADC5765D6B64'
$expectedMadtHash = 'DEC804620606536ED5BEFD269E0EB4646732057CD355A9BE2006FDB67C119067'

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Execute em um PowerShell como Administrador.'
}

$resolvedManifest = (Resolve-Path -LiteralPath $ManifestPath).Path
$manifest = Get-Content -LiteralPath $resolvedManifest -Raw -Encoding UTF8 | ConvertFrom-Json
$testId = [string]$manifest.TestEntry.Identifier
if ($testId -notmatch '^\{[0-9A-Fa-f-]{36}\}$') {
    throw "Identificador de teste invalido no manifesto: $testId"
}

function Read-BcdEntry {
    param([Parameter(Mandatory)][string]$Identifier)
    $output = (& bcdedit.exe /enum $Identifier 2>&1) -join "`r`n"
    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao ler BCD ${Identifier}:`n$output"
    }
    return $output
}

$safe = Read-BcdEntry -Identifier '{current}'
$test = Read-BcdEntry -Identifier $testId
if ($safe -notmatch '(?im)^hypervisorlaunchtype\s+Off\s*$') {
    throw '{current} nao esta com hypervisorlaunchtype Off.'
}
if ($safe -notmatch '(?im)^vsmlaunchtype\s+Off\s*$') {
    throw '{current} nao esta com vsmlaunchtype Off.'
}
if ($test -notmatch '(?im)^hypervisorlaunchtype\s+Auto\s*$') {
    throw "$testId nao esta com hypervisorlaunchtype Auto."
}
if ($test -notmatch '(?im)^vsmlaunchtype\s+Off\s*$') {
    throw "$testId nao esta com vsmlaunchtype Off."
}

if ($Cancel) {
    if (-not $Apply) {
        Write-Host "DRY RUN: removeria $testId da sequencia unica do proximo boot."
        exit 0
    }
    & bcdedit.exe /bootsequence $testId /remove
    if ($LASTEXITCODE -ne 0) {
        throw 'Falha ao cancelar a sequencia unica.'
    }
    Write-Host 'Sequencia unica cancelada. {current} permanece o padrao seguro.'
    exit 0
}

$bitLocker = Get-BitLockerVolume -MountPoint $env:SystemDrive -ErrorAction Stop
if ($bitLocker.ProtectionStatus -eq 'On') {
    throw 'BitLocker esta protegido; a tentativa foi recusada.'
}

$usb = Get-Volume -DriveLetter G -ErrorAction Stop
if ($usb.FileSystemLabel -ne 'BIOS_BACKUP' -or $usb.FileSystem -ne 'FAT32') {
    throw 'G: nao e a particao FAT32 BIOS_BACKUP esperada.'
}
$usbConfig = 'G:\EFI\OC\config.plist'
if (-not (Test-Path -LiteralPath $usbConfig)) {
    throw 'config.plist do OpenCore nao foi encontrado em G:.'
}
$configHash = (Get-FileHash -LiteralPath $usbConfig -Algorithm SHA256).Hash
if ($configHash -ne $expectedConfigHash) {
    throw "O patch MADT ativo no USB nao e o validado. Hash: $configHash"
}

$analysisDir = Split-Path -Parent $PSScriptRoot
$madtEvidence = Join-Path $analysisDir 'acpi-after-opencore-patch.dat'
if (-not (Test-Path -LiteralPath $madtEvidence)) {
    throw 'A evidencia da MADT corrigida nao foi encontrada.'
}
$madtHash = (Get-FileHash -LiteralPath $madtEvidence -Algorithm SHA256).Hash
if ($madtHash -ne $expectedMadtHash) {
    throw "A evidencia MADT nao possui o hash esperado. Hash: $madtHash"
}

if (-not $Apply) {
    Write-Host 'DRY RUN: nenhuma alteracao foi feita.'
    Write-Host "Proxima tentativa unica: $testId - Windows - HYPERV MADT PATCH"
    Write-Host 'Depois dessa tentativa, o Boot Manager volta para {current}, Hyper-V OFF.'
    Write-Host 'O script nao reinicia a maquina.'
    exit 0
}

$backupDir = Join-Path $analysisDir 'bcd-backups'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupPath = Join-Path $backupDir "bcd-before-onetime-hyperv-$stamp.bcd"
$scheduleManifestPath = Join-Path $backupDir "hyperv-madt-onetime-$stamp.json"
& bcdedit.exe /export $backupPath
if ($LASTEXITCODE -ne 0) {
    throw 'Falha ao exportar o BCD antes da sequencia unica.'
}

& bcdedit.exe /bootsequence $testId
if ($LASTEXITCODE -ne 0) {
    throw 'Falha ao definir a sequencia unica do proximo boot.'
}
$bootManager = Read-BcdEntry -Identifier '{bootmgr}'
if ($bootManager -notmatch [regex]::Escape($testId.Trim('{}'))) {
    & bcdedit.exe /bootsequence $testId /remove | Out-Null
    throw 'O Boot Manager nao confirmou o identificador na sequencia unica.'
}

$scheduleManifest = [ordered]@{
    CreatedAt = (Get-Date).ToString('o')
    SourceManifest = $resolvedManifest
    BcdBackup = $backupPath
    OneTimeEntry = $testId
    SafeDefault = '{current}'
    SafeDefaultHypervisor = 'off'
    UsbConfigSha256 = $configHash
    PatchedMadtSha256 = $madtHash
    RebootScheduledByScript = $false
}
$scheduleManifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $scheduleManifestPath -Encoding UTF8

Write-Host "Backup BCD: $backupPath"
Write-Host "Manifesto da tentativa: $scheduleManifestPath"
Write-Host "PROXIMO BOOT APENAS: $testId - Windows - HYPERV MADT PATCH"
Write-Host 'Depois, o Boot Manager volta automaticamente para {current}, Hyper-V OFF.'
Write-Host 'Nenhum reboot foi executado por este script.'
