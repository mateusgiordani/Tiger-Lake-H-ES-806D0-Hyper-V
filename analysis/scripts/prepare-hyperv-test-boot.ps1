param(
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'

if (-not $Apply) {
    Write-Host 'DRY RUN: no BCD changes were made.'
    Write-Host 'With -Apply this script will:'
    Write-Host '  1. Export a BCD backup under analysis\bcd-backups.'
    Write-Host '  2. Keep {current} as the default Hyper-V-OFF recovery entry.'
    Write-Host '  3. Create one separate manual Hyper-V-ON MADT baseline entry.'
    Write-Host '  4. Set a 15-second boot-menu timeout.'
    Write-Host 'It does not schedule a test entry and does not reboot.'
    exit 0
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this script from an elevated PowerShell prompt.'
}

$bitLockerCommand = Get-Command Get-BitLockerVolume -ErrorAction SilentlyContinue
if ($bitLockerCommand) {
    $systemVolume = Get-BitLockerVolume -MountPoint $env:SystemDrive
    if ($systemVolume.ProtectionStatus -eq 'On') {
        throw 'BitLocker protection is active. Save the recovery key and suspend protection manually before changing BCD.'
    }
}

$analysisDir = Split-Path -Parent $PSScriptRoot
$backupDir = Join-Path $analysisDir 'bcd-backups'
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupPath = Join-Path $backupDir "bcd-before-hyperv-test-$stamp.bcd"

& bcdedit.exe /export $backupPath
if ($LASTEXITCODE -ne 0) {
    throw "BCD export failed with exit code $LASTEXITCODE."
}

& bcdedit.exe /set '{current}' hypervisorlaunchtype off
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to set the current recovery entry to hypervisorlaunchtype off.'
}
& bcdedit.exe /set '{current}' vsmlaunchtype off
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to set the current recovery entry to vsmlaunchtype off.'
}

$copyOutput = (& bcdedit.exe /copy '{current}' /d 'Windows - HYPERV MADT PATCH') -join "`n"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create the Hyper-V test entry: $copyOutput"
}
$match = [regex]::Match($copyOutput, '\{[0-9A-Fa-f-]{36}\}')
if (-not $match.Success) {
    throw "Could not parse the new BCD identifier: $copyOutput"
}
$testId = $match.Value

& bcdedit.exe /set $testId hypervisorlaunchtype auto
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to enable the hypervisor on the test entry.'
}
& bcdedit.exe /set $testId vsmlaunchtype off
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to keep VSM off on the Hyper-V baseline entry.'
}
& bcdedit.exe /default '{current}'
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to preserve the current entry as default.'
}
& bcdedit.exe /set '{bootmgr}' displaybootmenu yes
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to enable the explicit boot menu.'
}
& bcdedit.exe /displayorder '{current}' $testId
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to set the boot-menu order.'
}
& bcdedit.exe /timeout 15
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to set the 15-second boot-menu timeout.'
}

$manifestPath = Join-Path $backupDir "hyperv-madt-baseline-$stamp.json"
$manifest = [ordered]@{
    CreatedAt = (Get-Date).ToString('o')
    BcdBackup = $backupPath
    SafeDefault = '{current}'
    SafeHypervisorLaunchType = 'off'
    SafeVsmLaunchType = 'off'
    TestEntry = [ordered]@{
        Identifier = $testId
        Description = 'Windows - HYPERV MADT PATCH'
        HypervisorLaunchType = 'auto'
        VsmLaunchType = 'off'
    }
    TimeoutSeconds = 15
    BootSequenceScheduled = $false
    RebootScheduled = $false
    PatchedMadtEvidence = if (Test-Path -LiteralPath (Join-Path $analysisDir 'acpi-after-opencore-patch.dat')) {
        [ordered]@{
            Path = (Join-Path $analysisDir 'acpi-after-opencore-patch.dat')
            Sha256 = (Get-FileHash -LiteralPath (Join-Path $analysisDir 'acpi-after-opencore-patch.dat') -Algorithm SHA256).Hash
        }
    } else {
        $null
    }
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

Write-Host "BCD backup: $backupPath"
Write-Host "Manifest: $manifestPath"
Write-Host 'Default/recovery entry: {current}, Hyper-V OFF'
Write-Host "Manual test entry: $testId, Windows - HYPERV MADT PATCH, Hyper-V ON, VSM OFF"
Write-Host 'No boot was scheduled. Select the test entry manually only while booting through OpenCore.'
