param(
    [Parameter(Mandatory)]
    [string]$AtomicManifestPath,
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$expectedControlHash = 'B537E45232F88F8D9124AB94E68D5F29381EC6D6CC47472BA6C0138F62B511C8'

function Invoke-Bcd {
    param([Parameter(Mandatory)][string[]]$Arguments, [switch]$AllowFailure)
    $text = (& bcdedit.exe @Arguments 2>&1) -join "`r`n"
    $exitCode = $LASTEXITCODE
    if (($exitCode -ne 0) -and (-not $AllowFailure)) {
        throw "bcdedit $($Arguments -join ' ') falhou ($exitCode):`n$text"
    }
    [pscustomobject]@{ ExitCode = $exitCode; Text = $text }
}

function Assert-BcdValue {
    param([string]$Text, [string]$Name, [string]$Value, [string]$Context)
    $pattern = '(?im)^' + [regex]::Escape($Name) + '\s+' + [regex]::Escape($Value) + '\s*$'
    if ($Text -notmatch $pattern) {
        throw "$Context nao confirmou $Name=$Value."
    }
}

function Remove-BcdValue {
    param([string]$Identifier, [string]$Name)
    [void](Invoke-Bcd -Arguments @('/deletevalue', $Identifier, $Name) -AllowFailure)
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Execute em um PowerShell como Administrador.'
}

$bitLocker = Get-BitLockerVolume -MountPoint $env:SystemDrive -ErrorAction Stop
if ($bitLocker.ProtectionStatus -eq 'On') {
    throw 'BitLocker esta protegido; o controle foi recusado.'
}

$resolvedManifest = (Resolve-Path -LiteralPath $AtomicManifestPath).Path
$atomicManifest = Get-Content -LiteralPath $resolvedManifest -Raw -Encoding UTF8 | ConvertFrom-Json
$testId = [string]$atomicManifest.OneTimeEntry
if ($testId -notmatch '^\{[0-9A-Fa-f-]{36}\}$') {
    throw "GUID de teste invalido no manifesto: $testId"
}

$safe = (Invoke-Bcd -Arguments @('/enum', '{current}')).Text
$test = (Invoke-Bcd -Arguments @('/enum', $testId)).Text
$bootManager = (Invoke-Bcd -Arguments @('/enum', '{bootmgr}')).Text
Assert-BcdValue -Text $safe -Name 'hypervisorlaunchtype' -Value 'Off' -Context '{current}'
Assert-BcdValue -Text $safe -Name 'vsmlaunchtype' -Value 'Off' -Context '{current}'
Assert-BcdValue -Text $test -Name 'hypervisorlaunchtype' -Value 'Auto' -Context $testId
Assert-BcdValue -Text $test -Name 'vsmlaunchtype' -Value 'Off' -Context $testId
if ($bootManager -match '(?im)^bootsequence\s+') {
    throw 'Ja existe uma bootsequence unica; recusei substituir.'
}

$usbConfig = 'G:\EFI\OC\config.plist'
if (-not (Test-Path -LiteralPath $usbConfig)) {
    throw 'OpenCore config.plist ausente em G:.'
}
$configHash = (Get-FileHash -LiteralPath $usbConfig -Algorithm SHA256).Hash
if ($configHash -ne $expectedControlHash) {
    throw "O USB nao esta em CONTROL DISABLED. Hash ativo: $configHash"
}

if (-not $Apply) {
    Write-Host 'DRY RUN: nenhuma alteracao foi feita.'
    Write-Host 'Validado: OpenCore CONTROL DISABLED, MADT sem patch, BitLocker OFF e {current} seguro.'
    Write-Host 'Com -Apply: backup -> baseline Hyper-V sem isoladores -> captura visivel -> bootsequence unica.'
    Write-Host 'O script nao reinicia.'
    exit 0
}

$analysisDir = Split-Path -Parent $PSScriptRoot
$backupDir = Join-Path $analysisDir 'bcd-backups'
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$bcdBefore = Join-Path $backupDir "bcd-before-opencore-control-$stamp.bcd"
$bcdAfter = Join-Path $backupDir "bcd-after-opencore-control-$stamp.bcd"
$manifestPath = Join-Path $backupDir "hyperv-opencore-control-onetime-$stamp.json"
[void](Invoke-Bcd -Arguments @('/export', $bcdBefore))

$isolators = @(
    'hypervisoriommupolicy',
    'x2apicpolicy',
    'uselegacyapicmode',
    'hypervisornumproc',
    'hypervisorloadoptions',
    'hypervisorusevapic',
    'hypervisordisableslat',
    'hypervisorschedulertype',
    'xsavedisable',
    'onecpu',
    'numproc',
    'usephysicaldestination'
)

try {
    [void](Invoke-Bcd -Arguments @('/set', '{current}', 'hypervisorlaunchtype', 'off'))
    [void](Invoke-Bcd -Arguments @('/set', '{current}', 'vsmlaunchtype', 'off'))
    [void](Invoke-Bcd -Arguments @('/default', '{current}'))
    foreach ($element in $isolators) {
        Remove-BcdValue -Identifier $testId -Name $element
    }

    [void](Invoke-Bcd -Arguments @('/set', $testId, 'description', 'Windows - HYPERV OPENCORE CONTROL'))
    [void](Invoke-Bcd -Arguments @('/set', $testId, 'hypervisorlaunchtype', 'auto'))
    [void](Invoke-Bcd -Arguments @('/set', $testId, 'vsmlaunchtype', 'off'))
    [void](Invoke-Bcd -Arguments @('/set', $testId, 'nocrashautoreboot', 'yes'))
    [void](Invoke-Bcd -Arguments @('/set', $testId, 'bootlog', 'yes'))
    [void](Invoke-Bcd -Arguments @('/set', $testId, 'sos', 'yes'))
    [void](Invoke-Bcd -Arguments @('/set', $testId, 'quietboot', 'off'))
    [void](Invoke-Bcd -Arguments @('/bootsequence', $testId))

    $safeAfter = (Invoke-Bcd -Arguments @('/enum', '{current}')).Text
    $testAfter = (Invoke-Bcd -Arguments @('/enum', $testId)).Text
    $bootManagerAfter = (Invoke-Bcd -Arguments @('/enum', '{bootmgr}')).Text
    Assert-BcdValue -Text $safeAfter -Name 'hypervisorlaunchtype' -Value 'Off' -Context '{current}'
    Assert-BcdValue -Text $safeAfter -Name 'vsmlaunchtype' -Value 'Off' -Context '{current}'
    Assert-BcdValue -Text $testAfter -Name 'hypervisorlaunchtype' -Value 'Auto' -Context $testId
    Assert-BcdValue -Text $testAfter -Name 'vsmlaunchtype' -Value 'Off' -Context $testId
    Assert-BcdValue -Text $testAfter -Name 'nocrashautoreboot' -Value 'Yes' -Context $testId
    foreach ($element in $isolators) {
        if ($testAfter -match ('(?im)^' + [regex]::Escape($element) + '\s+')) {
            throw "O isolador $element ainda esta presente."
        }
    }
    if ($bootManagerAfter -notmatch [regex]::Escape($testId.Trim('{}'))) {
        throw 'Boot Manager nao confirmou o GUID na bootsequence unica.'
    }

    [void](Invoke-Bcd -Arguments @('/export', $bcdAfter))
    $exported = (Invoke-Bcd -Arguments @('/store', $bcdAfter, '/enum', $testId)).Text
    Assert-BcdValue -Text $exported -Name 'hypervisorlaunchtype' -Value 'Auto' -Context 'exportacao pos-alteracao'
    foreach ($element in $isolators) {
        if ($exported -match ('(?im)^' + [regex]::Escape($element) + '\s+')) {
            throw "A exportacao ainda contem $element."
        }
    }

    $manifest = [ordered]@{
        CreatedAt = (Get-Date).ToString('o')
        SourceAtomicManifest = $resolvedManifest
        BcdBackupBefore = $bcdBefore
        BcdExportAfter = $bcdAfter
        SafeDefault = '{current}'
        OneTimeEntry = $testId
        OneTimeDescription = 'Windows - HYPERV OPENCORE CONTROL'
        Experiment = 'Controle causal: mesmo OpenCore e Hyper-V baseline, MADT original sem patch.'
        ActiveUsbConfigSha256 = $configHash
        ExpectedMadT = 'Original: CPUs 0..15, Local APIC NMI UIDs 1..16.'
        HypervisorLaunchType = 'auto'
        VsmLaunchType = 'off'
        IsolatorsRemoved = $isolators
        Capture = [ordered]@{
            nocrashautoreboot = 'yes'
            bootlog = 'yes'
            sos = 'yes'
            quietboot = 'off'
        }
        PostExportVerified = $true
        RebootScheduledByScript = $false
    }
    $manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
} catch {
    [void](Invoke-Bcd -Arguments @('/bootsequence', $testId, '/remove') -AllowFailure)
    throw
}

Write-Host "Backup BCD: $bcdBefore"
Write-Host "Exportacao verificada: $bcdAfter"
Write-Host "Manifesto: $manifestPath"
Write-Host "PROXIMO BOOT APENAS: $testId - OpenCore CONTROL DISABLED + MADT original + Hyper-V baseline."
Write-Host '{current} permanece o padrao seguro com Hyper-V/VSM OFF.'
Write-Host 'O script NAO reiniciou.'
