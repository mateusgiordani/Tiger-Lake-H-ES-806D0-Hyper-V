param(
    [Parameter(Mandatory)]
    [string]$AtomicManifestPath,
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$expectedConfigHash = 'A541BA6A79F73F9A5A932BFE105B712B446553C579A2DAAC8F4FADC5765D6B64'
$expectedMadtHash = 'DEC804620606536ED5BEFD269E0EB4646732057CD355A9BE2006FDB67C119067'

function Invoke-Bcd {
    param(
        [Parameter(Mandatory)][string[]]$Arguments,
        [switch]$AllowFailure
    )
    $text = (& bcdedit.exe @Arguments 2>&1) -join "`r`n"
    $exitCode = $LASTEXITCODE
    if (($exitCode -ne 0) -and (-not $AllowFailure)) {
        throw "bcdedit $($Arguments -join ' ') falhou ($exitCode):`n$text"
    }
    return [pscustomobject]@{ ExitCode = $exitCode; Text = $text }
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
    throw 'BitLocker esta protegido; o teste foi recusado.'
}

$resolvedAtomicManifest = (Resolve-Path -LiteralPath $AtomicManifestPath).Path
$atomicManifest = Get-Content -LiteralPath $resolvedAtomicManifest -Raw -Encoding UTF8 | ConvertFrom-Json
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

$analysisDir = Split-Path -Parent $PSScriptRoot
$usbConfig = 'G:\EFI\OC\config.plist'
if (-not (Test-Path -LiteralPath $usbConfig)) {
    throw 'OpenCore config.plist ausente em G:.'
}
$configHash = (Get-FileHash -LiteralPath $usbConfig -Algorithm SHA256).Hash
if ($configHash -ne $expectedConfigHash) {
    throw "Patch MADT incorreto no USB. Hash encontrado: $configHash"
}
$madtEvidence = Join-Path $analysisDir 'acpi-after-opencore-patch.dat'
if (-not (Test-Path -LiteralPath $madtEvidence)) {
    throw 'Evidencia local da MADT corrigida ausente.'
}
$madtHash = (Get-FileHash -LiteralPath $madtEvidence -Algorithm SHA256).Hash
if ($madtHash -ne $expectedMadtHash) {
    throw "Evidencia MADT incorreta. Hash encontrado: $madtHash"
}

if (-not $Apply) {
    Write-Host 'DRY RUN: nenhuma alteracao foi feita.'
    Write-Host "Entrada reutilizavel validada: $testId, Hyper-V Auto, VSM Off."
    Write-Host 'Com -Apply: backup -> remocao de hypervisornumproc e demais isoladores -> hypervisorusevapic=No -> bootsequence unica.'
    Write-Host '{current} continuara seguro e o script nao reinicia.'
    exit 0
}

$backupDir = Join-Path $analysisDir 'bcd-backups'
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$bcdBefore = Join-Path $backupDir "bcd-before-hyperv-no-vapic-$stamp.bcd"
$bcdAfter = Join-Path $backupDir "bcd-after-hyperv-no-vapic-$stamp.bcd"
$manifestPath = Join-Path $backupDir "hyperv-no-vapic-onetime-$stamp.json"

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

    [void](Invoke-Bcd -Arguments @('/set', $testId, 'description', 'Windows - HYPERV MADT NO vAPIC'))
    [void](Invoke-Bcd -Arguments @('/set', $testId, 'hypervisorlaunchtype', 'auto'))
    [void](Invoke-Bcd -Arguments @('/set', $testId, 'vsmlaunchtype', 'off'))
    [void](Invoke-Bcd -Arguments @('/set', $testId, 'hypervisorusevapic', 'no'))
    [void](Invoke-Bcd -Arguments @('/set', $testId, 'nocrashautoreboot', 'yes'))
    [void](Invoke-Bcd -Arguments @('/set', $testId, 'bootlog', 'yes'))
    [void](Invoke-Bcd -Arguments @('/set', $testId, 'sos', 'yes'))
    [void](Invoke-Bcd -Arguments @('/set', $testId, 'quietboot', 'off'))
    [void](Invoke-Bcd -Arguments @('/bootsequence', $testId))

    $testAfter = (Invoke-Bcd -Arguments @('/enum', $testId)).Text
    $safeAfter = (Invoke-Bcd -Arguments @('/enum', '{current}')).Text
    $bootManagerAfter = (Invoke-Bcd -Arguments @('/enum', '{bootmgr}')).Text
    Assert-BcdValue -Text $safeAfter -Name 'hypervisorlaunchtype' -Value 'Off' -Context '{current}'
    Assert-BcdValue -Text $safeAfter -Name 'vsmlaunchtype' -Value 'Off' -Context '{current}'
    Assert-BcdValue -Text $testAfter -Name 'hypervisorlaunchtype' -Value 'Auto' -Context $testId
    Assert-BcdValue -Text $testAfter -Name 'vsmlaunchtype' -Value 'Off' -Context $testId
    Assert-BcdValue -Text $testAfter -Name 'hypervisorusevapic' -Value 'No' -Context $testId
    Assert-BcdValue -Text $testAfter -Name 'nocrashautoreboot' -Value 'Yes' -Context $testId
    if ($testAfter -match '(?im)^hypervisornumproc\s+') {
        throw 'hypervisornumproc ainda esta presente; o teste foi recusado.'
    }
    if ($bootManagerAfter -notmatch [regex]::Escape($testId.Trim('{}'))) {
        throw 'Boot Manager nao confirmou o GUID na bootsequence unica.'
    }

    [void](Invoke-Bcd -Arguments @('/export', $bcdAfter))
    $exportedTest = (Invoke-Bcd -Arguments @('/store', $bcdAfter, '/enum', $testId)).Text
    Assert-BcdValue -Text $exportedTest -Name 'hypervisorusevapic' -Value 'No' -Context 'exportacao pos-alteracao'
    Assert-BcdValue -Text $exportedTest -Name 'hypervisorlaunchtype' -Value 'Auto' -Context 'exportacao pos-alteracao'
    if ($exportedTest -match '(?im)^hypervisornumproc\s+') {
        throw 'A exportacao ainda contem hypervisornumproc.'
    }

    $manifest = [ordered]@{
        CreatedAt = (Get-Date).ToString('o')
        SourceAtomicManifest = $resolvedAtomicManifest
        BcdBackupBefore = $bcdBefore
        BcdExportAfter = $bcdAfter
        SafeDefault = '{current}'
        OneTimeEntry = $testId
        OneTimeDescription = 'Windows - HYPERV MADT NO vAPIC'
        PreviousResult = [ordered]@{
            Test = 'MADT corrigida + hypervisornumproc=1'
            BugCheck = '0x7E'
            Exception = '0xC0000005'
            ExceptionAddress = '0xFFFFF8044BE01A96'
            Outcome = 'Mesma instrucao aparente; nenhum dump ou bootlog.'
        }
        Hypothesis = 'Falha no caminho de virtualizacao de APIC usado pelo hipervisor neste firmware/CPU ES.'
        Settings = [ordered]@{
            hypervisorlaunchtype = 'auto'
            vsmlaunchtype = 'off'
            hypervisorusevapic = 'no'
            nocrashautoreboot = 'yes'
            bootlog = 'yes'
            sos = 'yes'
            quietboot = 'off'
        }
        RemovedSettings = @('hypervisornumproc')
        UsbConfigSha256 = $configHash
        PatchedMadtSha256 = $madtHash
        PostExportVerified = $true
        RebootScheduledByScript = $false
        RequiredBootPath = 'Reiniciar normalmente e selecionar Windows no OpenCore; o Windows Boot Manager consumira a bootsequence unica.'
    }
    $manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
} catch {
    [void](Invoke-Bcd -Arguments @('/bootsequence', $testId, '/remove') -AllowFailure)
    throw
}

Write-Host "Backup BCD: $bcdBefore"
Write-Host "Exportacao verificada: $bcdAfter"
Write-Host "Manifesto: $manifestPath"
Write-Host "PROXIMO BOOT APENAS: $testId - Hyper-V + MADT corrigida + vAPIC desligado."
Write-Host '{current} permanece o padrao seguro com Hyper-V/VSM OFF.'
Write-Host 'O script NAO reiniciou. Quando instruido, use shutdown.exe /r /t 0 e selecione Windows no OpenCore.'
