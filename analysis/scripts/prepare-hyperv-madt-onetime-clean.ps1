param(
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
    param(
        [Parameter(Mandatory)][string]$Text,
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$Value,
        [Parameter(Mandatory)][string]$Context
    )
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
    throw 'BitLocker esta protegido; a tentativa foi recusada.'
}

$analysisDir = Split-Path -Parent $PSScriptRoot
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
    throw "Patch MADT incorreto no USB. Hash: $configHash"
}
$madtEvidence = Join-Path $analysisDir 'acpi-after-opencore-patch.dat'
if (-not (Test-Path -LiteralPath $madtEvidence)) {
    throw 'Evidencia da MADT corrigida ausente.'
}
$madtHash = (Get-FileHash -LiteralPath $madtEvidence -Algorithm SHA256).Hash
if ($madtHash -ne $expectedMadtHash) {
    throw "Evidencia MADT incorreta. Hash: $madtHash"
}

$safeBefore = Invoke-Bcd -Arguments @('/enum', '{current}')
Assert-BcdValue -Text $safeBefore -Name 'hypervisorlaunchtype' -Value 'Off' -Context '{current}'
Assert-BcdValue -Text $safeBefore -Name 'vsmlaunchtype' -Value 'Off' -Context '{current}'
$bootManagerBefore = Invoke-Bcd -Arguments @('/enum', '{bootmgr}')
if ($bootManagerBefore -match '(?im)^bootsequence\s+') {
    throw 'Ja existe uma sequencia unica no Boot Manager; recusei substituir.'
}

if (-not $Apply) {
    Write-Host 'DRY RUN: nenhuma alteracao foi feita.'
    Write-Host 'Validado: BitLocker OFF, {current} seguro, USB com patch e MADT corrigida.'
    Write-Host 'Com -Apply: backup -> nova entrada Hyper-V -> bootsequence unica -> exportacao e verificacao pos-alteracao.'
    Write-Host 'O script nao reinicia a maquina.'
    exit 0
}

$backupDir = Join-Path $analysisDir 'bcd-backups'
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupBefore = Join-Path $backupDir "bcd-before-atomic-hyperv-$stamp.bcd"
$exportAfter = Join-Path $backupDir "bcd-after-atomic-hyperv-$stamp.bcd"
$manifestPath = Join-Path $backupDir "hyperv-madt-atomic-onetime-$stamp.json"

[void](Invoke-Bcd -Arguments @('/export', $backupBefore))
$testId = $null
try {
    [void](Invoke-Bcd -Arguments @('/set', '{current}', 'hypervisorlaunchtype', 'off'))
    [void](Invoke-Bcd -Arguments @('/set', '{current}', 'vsmlaunchtype', 'off'))
    [void](Invoke-Bcd -Arguments @('/default', '{current}'))

    $copyText = Invoke-Bcd -Arguments @('/copy', '{current}', '/d', 'Windows - HYPERV MADT ONETIME')
    $match = [regex]::Match($copyText, '\{[0-9A-Fa-f-]{36}\}')
    if (-not $match.Success) {
        throw "Nao foi possivel extrair o GUID: $copyText"
    }
    $testId = $match.Value
    [void](Invoke-Bcd -Arguments @('/set', $testId, 'hypervisorlaunchtype', 'auto'))
    [void](Invoke-Bcd -Arguments @('/set', $testId, 'vsmlaunchtype', 'off'))
    [void](Invoke-Bcd -Arguments @('/bootsequence', $testId))

    $safeAfter = Invoke-Bcd -Arguments @('/enum', '{current}')
    $testAfter = Invoke-Bcd -Arguments @('/enum', $testId)
    $bootManagerAfter = Invoke-Bcd -Arguments @('/enum', '{bootmgr}')
    Assert-BcdValue -Text $safeAfter -Name 'hypervisorlaunchtype' -Value 'Off' -Context '{current}'
    Assert-BcdValue -Text $safeAfter -Name 'vsmlaunchtype' -Value 'Off' -Context '{current}'
    Assert-BcdValue -Text $testAfter -Name 'hypervisorlaunchtype' -Value 'Auto' -Context $testId
    Assert-BcdValue -Text $testAfter -Name 'vsmlaunchtype' -Value 'Off' -Context $testId
    if ($bootManagerAfter -notmatch [regex]::Escape($testId.Trim('{}'))) {
        throw 'Boot Manager nao confirmou o GUID na bootsequence unica.'
    }

    [void](Invoke-Bcd -Arguments @('/export', $exportAfter))
    $exportedTest = Invoke-Bcd -Arguments @('/store', $exportAfter, '/enum', $testId)
    Assert-BcdValue -Text $exportedTest -Name 'hypervisorlaunchtype' -Value 'Auto' -Context 'exportacao pos-alteracao'
    Assert-BcdValue -Text $exportedTest -Name 'vsmlaunchtype' -Value 'Off' -Context 'exportacao pos-alteracao'

    $manifest = [ordered]@{
        CreatedAt = (Get-Date).ToString('o')
        BcdBackupBefore = $backupBefore
        BcdExportAfter = $exportAfter
        SafeDefault = '{current}'
        OneTimeEntry = $testId
        OneTimeDescription = 'Windows - HYPERV MADT ONETIME'
        SafeHypervisorLaunchType = 'off'
        TestHypervisorLaunchType = 'auto'
        VsmLaunchType = 'off'
        UsbConfigSha256 = $configHash
        PatchedMadtSha256 = $madtHash
        PostExportVerified = $true
        RebootScheduledByScript = $false
        RequiredRestartCommand = 'shutdown.exe /r /t 0'
    }
    $manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
} catch {
    if ($testId) {
        & bcdedit.exe /bootsequence $testId /remove 2>$null | Out-Null
        & bcdedit.exe /delete $testId 2>$null | Out-Null
    }
    throw
}

Write-Host "Backup anterior: $backupBefore"
Write-Host "Exportacao posterior verificada: $exportAfter"
Write-Host "Manifesto: $manifestPath"
Write-Host "PROXIMO BOOT APENAS: $testId - Windows - HYPERV MADT ONETIME"
Write-Host '{current} permanece o padrao seguro com Hyper-V/VSM OFF.'
Write-Host 'NAO use o botao Reset. Aguarde instrucao para executar shutdown.exe /r /t 0.'
