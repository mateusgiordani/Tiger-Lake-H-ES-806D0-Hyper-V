param(
    [Parameter(Mandatory)] [string]$ManifestPath,
    [string]$SelectedEntry = 'unknown'
)

$ErrorActionPreference = 'Stop'
$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
$outputDir = Split-Path -Parent $ManifestPath
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$outputPath = Join-Path $outputDir "hyperv-postboot-$stamp.json"

function Convert-BytesToUInt32 {
    param($Value)
    if ($null -eq $Value) { return $null }
    $bytes = [byte[]]$Value
    if ($bytes.Length -lt 4) { return $null }
    return [BitConverter]::ToUInt32($bytes, 0)
}

function Convert-KernelPowerEvent {
    param($Event)
    $xml = [xml]$Event.ToXml()
    $data = [ordered]@{}
    foreach ($node in $xml.Event.EventData.Data) {
        $data[[string]$node.Name] = [string]$node.'#text'
    }
    return [ordered]@{
        TimeCreated = $Event.TimeCreated.ToString('o')
        RecordId = $Event.RecordId
        BugcheckCode = $data.BugcheckCode
        BugcheckParameter1 = $data.BugcheckParameter1
        BugcheckParameter2 = $data.BugcheckParameter2
        BugcheckParameter3 = $data.BugcheckParameter3
        BugcheckParameter4 = $data.BugcheckParameter4
        PowerButtonTimestamp = $data.PowerButtonTimestamp
        WHEABootErrorCount = $data.WHEABootErrorCount
    }
}

$ntbtlogPath = "$env:SystemRoot\ntbtlog.txt"
$ntbtlog = if (Test-Path -LiteralPath $ntbtlogPath) {
    $item = Get-Item -LiteralPath $ntbtlogPath
    [ordered]@{
        Exists = $true
        Length = $item.Length
        LastWriteTime = $item.LastWriteTime.ToString('o')
        Tail = @(Get-Content -LiteralPath $ntbtlogPath -Tail 120)
    }
} else {
    [ordered]@{ Exists = $false; Tail = @() }
}

$processor = Get-ItemProperty 'HKLM:\HARDWARE\DESCRIPTION\System\CentralProcessor\0'
$hypervisorKey = Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Hypervisor' -ErrorAction SilentlyContinue
$powerEvents = @(
    Get-WinEvent -FilterHashtable @{
        LogName = 'System'
        ProviderName = 'Microsoft-Windows-Kernel-Power'
        Id = 41
    } -MaxEvents 10 -ErrorAction SilentlyContinue | ForEach-Object {
        Convert-KernelPowerEvent $_
    }
)
$bugchecks = @(
    Get-WinEvent -FilterHashtable @{ LogName = 'System'; Id = 1001 } -MaxEvents 10 -ErrorAction SilentlyContinue |
        Select-Object TimeCreated, RecordId, ProviderName, Message
)

$report = [ordered]@{
    CollectedAt = (Get-Date).ToString('o')
    SelectedEntry = $SelectedEntry
    SourceManifest = (Resolve-Path -LiteralPath $ManifestPath).Path
    PreTestEvidence = $manifest.PreTestEvidence
    CurrentLastBootUpTime = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToString('o')
    Ntbtlog = $ntbtlog
    KernelPower41 = $powerEvents
    BugcheckEvents = $bugchecks
    HypervisorRegistry = [ordered]@{
        IgnoreMemPart = $hypervisorKey.IgnoreMemPart
        HypervisorUseVapic = $hypervisorKey.HypervisorUseVapic
        Hypervisorloadoptions = $hypervisorKey.Hypervisorloadoptions
    }
    Processor = [ordered]@{
        Identifier = $processor.Identifier
        Name = $processor.ProcessorNameString
        UpdateRevision = Convert-BytesToUInt32 $processor.'Update Revision'
        PreviousUpdateRevision = Convert-BytesToUInt32 $processor.'Previous Update Revision'
    }
}

$report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $outputPath -Encoding UTF8
Write-Host "Evidence report: $outputPath"
Write-Host "Selected entry: $SelectedEntry"
Write-Host "ntbtlog exists: $($ntbtlog.Exists); last write: $($ntbtlog.LastWriteTime)"
if ($powerEvents.Count) {
    Write-Host "Latest Kernel-Power 41 bugcheck code: $($powerEvents[0].BugcheckCode)"
}
