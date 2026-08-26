param(
    [string]$PythonPath = 'python'
)

$ErrorActionPreference = 'Stop'

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Execute este coletor em um PowerShell elevado.'
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$bootDirectory = Join-Path $repoRoot 'evidence\boot\hv06-mbec-working'
$cpuidDirectory = Join-Path $repoRoot 'evidence\cpuid'
New-Item -ItemType Directory -Path $bootDirectory -Force | Out-Null
New-Item -ItemType Directory -Path $cpuidDirectory -Force | Out-Null

$bcdOutput = (& bcdedit.exe /enum '{current}' /v 2>&1) -join "`r`n"
if ($LASTEXITCODE -ne 0) {
    throw "Nao foi possivel ler a entrada BCD atual:`n$bcdOutput"
}
$requiredPatterns = [ordered]@{
    description = '(?im)^description\s+Windows - HV 06 SEM MBEC HW\s*$'
    hypervisorloadoptions = '(?im)^hypervisorloadoptions\s+DISABLEHARDWAREMBEC\s*$'
    hypervisorlaunchtype = '(?im)^hypervisorlaunchtype\s+Auto\s*$'
    vsmlaunchtype = '(?im)^vsmlaunchtype\s+Off\s*$'
}
foreach ($requirement in $requiredPatterns.GetEnumerator()) {
    if ($bcdOutput -notmatch $requirement.Value) {
        throw "BCD atual nao confirma $($requirement.Key) para HV06. Coleta abortada."
    }
}
if ($bcdOutput -match '(?im)^xsavedisable\s+') {
    throw 'A entrada HV06 ainda contem xsavedisable. Coleta abortada.'
}
$bcdOutput | Set-Content -LiteralPath (Join-Path $bootDirectory 'current-bcd.txt') -Encoding UTF8

$hypervisorPresent = (Get-CimInstance Win32_ComputerSystem).HypervisorPresent
if (-not $hypervisorPresent) {
    throw 'HypervisorPresent=False; este nao e o boot HV06 funcional esperado.'
}

$probeScript = Join-Path $PSScriptRoot 'probe_avx_execution.py'
$probeJsonText = (& $PythonPath $probeScript --json 2>&1) -join "`n"
if ($LASTEXITCODE -ne 0) {
    throw "Probe AVX/AVX2 falhou:`n$probeJsonText"
}
$probe = $probeJsonText | ConvertFrom-Json
if (($probe.results.avx.status -ne 'PASS') -or ($probe.results.avx2.status -ne 'PASS')) {
    throw 'Probe nao confirmou AVX=PASS e AVX2=PASS.'
}
$probeJsonText | Set-Content -LiteralPath (Join-Path $bootDirectory 'avx-execution-probe.json') -Encoding UTF8

$wslOutput = (& wsl.exe -d Ubuntu -- uname -srvm 2>&1) -join "`n"
if ($LASTEXITCODE -ne 0) {
    throw "WSL2 probe falhou:`n$wslOutput"
}
$wslOutput | Set-Content -LiteralPath (Join-Path $bootDirectory 'wsl-uname.txt') -Encoding UTF8

$normalizedPath = Join-Path $cpuidDirectory 'cpuid-windows-hv06-mbec-working.json'
$richPath = Join-Path $cpuidDirectory 'cpuid-windows-hv06-mbec-working-legacy-collector.json'
$combinedCollector = Join-Path $PSScriptRoot 'collect_platform.py'
$cpuidCollector = Join-Path $PSScriptRoot 'dump_cpuid_windows.py'
& $PythonPath $combinedCollector $normalizedPath
if ($LASTEXITCODE -ne 0) {
    throw 'A coleta CPUID normalizada falhou.'
}
& $PythonPath $cpuidCollector --output $richPath
if ($LASTEXITCODE -ne 0) {
    throw 'A coleta CPUID rica falhou.'
}

$timestamp = Get-Date -Format o
$runtimeValidation = @"
Timestamp: $timestamp
Boot entry: Windows - HV 06 SEM MBEC HW
HypervisorPresent: $hypervisorPresent

AVX execution probe:
AVX: $($probe.results.avx.status)
AVX2: $($probe.results.avx2.status)

Windows processor features:
PF_AVX_INSTRUCTIONS_AVAILABLE: $($probe.results.avx.windows_feature_available)
PF_AVX2_INSTRUCTIONS_AVAILABLE: $($probe.results.avx2.windows_feature_available)

WSL2 probe:
$wslOutput
"@
$runtimeValidation | Set-Content -LiteralPath (Join-Path $bootDirectory 'runtime-validation.txt') -Encoding UTF8

$operatingSystem = Get-CimInstance Win32_OperatingSystem
$metadata = [ordered]@{
    captured_at = $timestamp
    boot_entry = 'Windows - HV 06 SEM MBEC HW'
    expected_isolator = 'DISABLEHARDWAREMBEC'
    hypervisor_present = $hypervisorPresent
    last_boot_up_time = $operatingSystem.LastBootUpTime.ToString('o')
    avx_execution = $probe.results.avx.status
    avx2_execution = $probe.results.avx2.status
    wsl2_probe_exit_code = 0
    normalized_cpuid = $normalizedPath.Substring($repoRoot.Length + 1).Replace('\', '/')
    rich_cpuid = $richPath.Substring($repoRoot.Length + 1).Replace('\', '/')
}
$metadata | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (
    Join-Path $bootDirectory 'capture-metadata.json'
) -Encoding UTF8

$evidenceFiles = @(
    Get-ChildItem -LiteralPath $bootDirectory -File |
        Where-Object { $_.Name -ne 'sha256-manifest.json' }
    Get-Item -LiteralPath $normalizedPath
    Get-Item -LiteralPath $richPath
)
$hashes = foreach ($file in $evidenceFiles) {
    $hash = Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256
    [ordered]@{
        path = $file.FullName.Substring($repoRoot.Length + 1).Replace('\', '/')
        bytes = $file.Length
        sha256 = $hash.Hash
    }
}
$hashes | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (
    Join-Path $bootDirectory 'sha256-manifest.json'
) -Encoding UTF8

Write-Host "HV06 evidence captured in $bootDirectory"
Write-Host "Normalized CPUID: $normalizedPath"
Write-Host "Rich CPUID: $richPath"
