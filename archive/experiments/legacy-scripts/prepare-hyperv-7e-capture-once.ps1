param(
    [Parameter(Mandatory)]
    [string]$AtomicManifestPath,
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$expectedConfigHash = 'A541BA6A79F73F9A5A932BFE105B712B446553C579A2DAAC8F4FADC5765D6B64'
$expectedMadtHash = 'DEC804620606536ED5BEFD269E0EB4646732057CD355A9BE2006FDB67C119067'

function Invoke-Bcd {
    param([Parameter(Mandatory)][string[]]$Arguments)
    $text = (& bcdedit.exe @Arguments 2>&1) -join "`r`n"
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "bcdedit $($Arguments -join ' ') falhou ($exitCode):`n$text"
    }
    return $text
}

function Assert-BcdValue {
    param([string]$Text, [string]$Name, [string]$Value, [string]$Context)
    $pattern = '(?im)^' + [regex]::Escape($Name) + '\s+' + [regex]::Escape($Value) + '\s*$'
    if ($Text -notmatch $pattern) {
        throw "$Context nao confirmou $Name=$Value."
    }
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Execute em um PowerShell como Administrador.'
}

$bitLocker = Get-BitLockerVolume -MountPoint $env:SystemDrive -ErrorAction Stop
if ($bitLocker.ProtectionStatus -eq 'On') {
    throw 'BitLocker esta protegido; a captura foi recusada.'
}

$resolvedAtomicManifest = (Resolve-Path -LiteralPath $AtomicManifestPath).Path
$atomicManifest = Get-Content -LiteralPath $resolvedAtomicManifest -Raw -Encoding UTF8 | ConvertFrom-Json
$testId = [string]$atomicManifest.OneTimeEntry
if ($testId -notmatch '^\{[0-9A-Fa-f-]{36}\}$') {
    throw "GUID de teste invalido: $testId"
}

$safe = Invoke-Bcd -Arguments @('/enum', '{current}')
$test = Invoke-Bcd -Arguments @('/enum', $testId)
$bootManager = Invoke-Bcd -Arguments @('/enum', '{bootmgr}')
Assert-BcdValue -Text $safe -Name 'hypervisorlaunchtype' -Value 'Off' -Context '{current}'
Assert-BcdValue -Text $safe -Name 'vsmlaunchtype' -Value 'Off' -Context '{current}'
Assert-BcdValue -Text $test -Name 'hypervisorlaunchtype' -Value 'Auto' -Context $testId
Assert-BcdValue -Text $test -Name 'vsmlaunchtype' -Value 'Off' -Context $testId
if ($bootManager -match '(?im)^bootsequence\s+') {
    throw 'Ja existe uma bootsequence unica; recusei substituir.'
}

$analysisDir = Split-Path -Parent $PSScriptRoot
$usbConfig = 'G:\EFI\OC\config.plist'
if (-not (Test-Path -LiteralPath $usbConfig)) {
    throw 'OpenCore config.plist ausente em G:.'
}
$configHash = (Get-FileHash -LiteralPath $usbConfig -Algorithm SHA256).Hash
if ($configHash -ne $expectedConfigHash) {
    throw "Patch MADT incorreto no USB. Hash: $configHash"
}
$madtEvidence = Join-Path $analysisDir 'acpi-after-opencore-patch.dat'
$madtHash = (Get-FileHash -LiteralPath $madtEvidence -Algorithm SHA256).Hash
if ($madtHash -ne $expectedMadtHash) {
    throw "Evidencia MADT incorreta. Hash: $madtHash"
}

if (-not $Apply) {
    Write-Host 'DRY RUN: nenhuma alteracao foi feita.'
    Write-Host "Entrada validada: $testId, Hyper-V Auto, VSM Off."
    Write-Host 'Com -Apply: backup de BCD/CrashControl, parametros do bugcheck visiveis, sem auto-restart, bootlog/SOS e bootsequence unica.'
    Write-Host 'O script nao reinicia.'
    exit 0
}

$backupDir = Join-Path $analysisDir 'bcd-backups'
$registryDir = Join-Path $analysisDir 'registry-backups'
New-Item -ItemType Directory -Path $backupDir,$registryDir -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$bcdBefore = Join-Path $backupDir "bcd-before-7e-capture-$stamp.bcd"
$bcdAfter = Join-Path $backupDir "bcd-after-7e-capture-$stamp.bcd"
$registryBackup = Join-Path $registryDir "crashcontrol-before-7e-capture-$stamp.reg"
$manifestPath = Join-Path $backupDir "hyperv-7e-capture-onetime-$stamp.json"
$crashKeyPath = 'HKLM:\SYSTEM\CurrentControlSet\Control\CrashControl'
$crashKey = Get-Item -LiteralPath $crashKeyPath
$valueNames = @($crashKey.GetValueNames())
$prior = [ordered]@{
    DisplayParametersExisted = $valueNames -contains 'DisplayParameters'
    DisplayParameters = $crashKey.GetValue('DisplayParameters', $null)
    DisplayDisabledExisted = $valueNames -contains 'DisplayDisabled'
    DisplayDisabled = $crashKey.GetValue('DisplayDisabled', $null)
}

& reg.exe export 'HKLM\SYSTEM\CurrentControlSet\Control\CrashControl' $registryBackup /y | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw 'Falha ao exportar CrashControl.'
}
[void](Invoke-Bcd -Arguments @('/export', $bcdBefore))

try {
    New-ItemProperty -LiteralPath $crashKeyPath -Name DisplayParameters -PropertyType DWord -Value 1 -Force | Out-Null
    New-ItemProperty -LiteralPath $crashKeyPath -Name DisplayDisabled -PropertyType DWord -Value 0 -Force | Out-Null

    [void](Invoke-Bcd -Arguments @('/set', $testId, 'hypervisorlaunchtype', 'auto'))
    [void](Invoke-Bcd -Arguments @('/set', $testId, 'vsmlaunchtype', 'off'))
    [void](Invoke-Bcd -Arguments @('/set', $testId, 'nocrashautoreboot', 'yes'))
    [void](Invoke-Bcd -Arguments @('/set', $testId, 'bootlog', 'yes'))
    [void](Invoke-Bcd -Arguments @('/set', $testId, 'sos', 'yes'))
    [void](Invoke-Bcd -Arguments @('/set', $testId, 'quietboot', 'off'))
    [void](Invoke-Bcd -Arguments @('/bootsequence', $testId))

    $testAfter = Invoke-Bcd -Arguments @('/enum', $testId)
    $bootManagerAfter = Invoke-Bcd -Arguments @('/enum', '{bootmgr}')
    Assert-BcdValue -Text $testAfter -Name 'hypervisorlaunchtype' -Value 'Auto' -Context $testId
    Assert-BcdValue -Text $testAfter -Name 'vsmlaunchtype' -Value 'Off' -Context $testId
    Assert-BcdValue -Text $testAfter -Name 'nocrashautoreboot' -Value 'Yes' -Context $testId
    Assert-BcdValue -Text $testAfter -Name 'bootlog' -Value 'Yes' -Context $testId
    Assert-BcdValue -Text $testAfter -Name 'sos' -Value 'Yes' -Context $testId
    if ($bootManagerAfter -notmatch [regex]::Escape($testId.Trim('{}'))) {
        throw 'Boot Manager nao confirmou a bootsequence unica.'
    }

    [void](Invoke-Bcd -Arguments @('/export', $bcdAfter))
    $exportedTest = Invoke-Bcd -Arguments @('/store', $bcdAfter, '/enum', $testId)
    Assert-BcdValue -Text $exportedTest -Name 'hypervisorlaunchtype' -Value 'Auto' -Context 'exportacao pos-captura'
    Assert-BcdValue -Text $exportedTest -Name 'nocrashautoreboot' -Value 'Yes' -Context 'exportacao pos-captura'

    $manifest = [ordered]@{
        CreatedAt = (Get-Date).ToString('o')
        SourceAtomicManifest = $resolvedAtomicManifest
        BcdBackupBefore = $bcdBefore
        BcdExportAfter = $bcdAfter
        CrashControlBackup = $registryBackup
        CrashControlPrior = $prior
        OneTimeEntry = $testId
        Settings = [ordered]@{
            hypervisorlaunchtype = 'auto'
            vsmlaunchtype = 'off'
            nocrashautoreboot = 'yes'
            bootlog = 'yes'
            sos = 'yes'
            quietboot = 'off'
            DisplayParameters = 1
            DisplayDisabled = 0
        }
        SafeDefault = '{current}'
        UsbConfigSha256 = $configHash
        PatchedMadtSha256 = $madtHash
        RebootScheduledByScript = $false
    }
    $manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
} catch {
    & bcdedit.exe /bootsequence $testId /remove 2>$null | Out-Null
    & reg.exe import $registryBackup | Out-Null
    throw
}

Write-Host "Backup BCD: $bcdBefore"
Write-Host "Backup CrashControl: $registryBackup"
Write-Host "Manifesto: $manifestPath"
Write-Host "PROXIMO BOOT APENAS: $testId - captura 0x7E com parametros visiveis."
Write-Host '{current} continua seguro; este script nao reiniciou.'
