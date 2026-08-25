$ErrorActionPreference = 'Stop'

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Execute em um PowerShell como Administrador.'
}

$analysisDir = Split-Path -Parent $PSScriptRoot
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$outputDir = Join-Path $analysisDir "efi-bcd-stores-$stamp"
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

function Invoke-BcdRead {
    param(
        [string]$StorePath,
        [string]$OutputPath
    )
    if ($StorePath) {
        $text = (& bcdedit.exe /store $StorePath /enum all /v 2>&1) -join "`r`n"
    } else {
        $text = (& bcdedit.exe /enum all /v 2>&1) -join "`r`n"
    }
    $exitCode = $LASTEXITCODE
    $text | Set-Content -LiteralPath $OutputPath -Encoding UTF8
    return [pscustomobject]@{ ExitCode = $exitCode; TextPath = $OutputPath }
}

$defaultBcd = Invoke-BcdRead -StorePath '' -OutputPath (Join-Path $outputDir 'default-store.txt')
$firmwareText = (& bcdedit.exe /enum firmware /v 2>&1) -join "`r`n"
$firmwareExit = $LASTEXITCODE
$firmwarePath = Join-Path $outputDir 'firmware-entries.txt'
$firmwareText | Set-Content -LiteralPath $firmwarePath -Encoding UTF8

$espGuid = '{c12a7328-f81f-11d2-ba4b-00a0c93ec93b}'
$espPartitions = Get-Partition | Where-Object { [string]$_.GptType -eq $espGuid }
$stores = @()
foreach ($partition in $espPartitions) {
    $volumePath = @($partition.AccessPaths | Where-Object { $_ -like '\\?\Volume{*' })[0]
    if (-not $volumePath) {
        $stores += [pscustomobject]@{
            DiskNumber = $partition.DiskNumber
            PartitionNumber = $partition.PartitionNumber
            Error = 'ESP has no volume GUID access path'
        }
        continue
    }
    if (-not $volumePath.EndsWith('\')) {
        $volumePath += '\'
    }
    $prefix = "disk$($partition.DiskNumber)-part$($partition.PartitionNumber)"
    $efiRoot = Join-Path $volumePath 'EFI'
    $bcdPath = Join-Path $efiRoot 'Microsoft\Boot\BCD'
    $bootManagerPath = Join-Path $efiRoot 'Microsoft\Boot\bootmgfw.efi'
    $fallbackPath = Join-Path $efiRoot 'Boot\bootx64.efi'
    $record = [ordered]@{
        DiskNumber = $partition.DiskNumber
        PartitionNumber = $partition.PartitionNumber
        VolumePath = $volumePath
        Size = $partition.Size
        IsSystem = $partition.IsSystem
        BcdExists = Test-Path -LiteralPath $bcdPath
        BootManagerExists = Test-Path -LiteralPath $bootManagerPath
        FallbackExists = Test-Path -LiteralPath $fallbackPath
    }
    try {
        $files = Get-ChildItem -LiteralPath $efiRoot -Recurse -Force -File -ErrorAction Stop | ForEach-Object {
            [ordered]@{
                RelativePath = $_.FullName.Substring($volumePath.Length)
                Length = $_.Length
                LastWriteTime = $_.LastWriteTime.ToString('o')
                Sha256 = if ($_.Extension -ieq '.efi' -or $_.Name -ieq 'BCD') {
                    (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
                } else {
                    $null
                }
            }
        }
        $files | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $outputDir "$prefix-files.json") -Encoding UTF8
        $record.FileCount = @($files).Count
        if ($record.BcdExists) {
            $record.BcdSha256 = (Get-FileHash -LiteralPath $bcdPath -Algorithm SHA256).Hash
            $record.BcdLastWriteTime = (Get-Item -LiteralPath $bcdPath).LastWriteTime.ToString('o')
            $copyPath = Join-Path $outputDir "$prefix-BCD"
            Copy-Item -LiteralPath $bcdPath -Destination $copyPath
            $bcdRead = Invoke-BcdRead -StorePath $bcdPath -OutputPath (Join-Path $outputDir "$prefix-bcdedit.txt")
            $record.BcdEditExitCode = $bcdRead.ExitCode
            $record.BcdEditText = $bcdRead.TextPath
        }
        if ($record.BootManagerExists) {
            $record.BootManagerSha256 = (Get-FileHash -LiteralPath $bootManagerPath -Algorithm SHA256).Hash
        }
        if ($record.FallbackExists) {
            $record.FallbackSha256 = (Get-FileHash -LiteralPath $fallbackPath -Algorithm SHA256).Hash
        }
    } catch {
        $record.Error = $_.Exception.Message
    }
    $stores += [pscustomobject]$record
}

$summary = [ordered]@{
    CreatedAt = (Get-Date).ToString('o')
    ReadOnlySourceOperations = $true
    DefaultStoreExitCode = $defaultBcd.ExitCode
    DefaultStoreText = $defaultBcd.TextPath
    FirmwareEntriesExitCode = $firmwareExit
    FirmwareEntriesText = $firmwarePath
    Stores = $stores
}
$summaryPath = Join-Path $outputDir 'summary.json'
$summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

Write-Host "Coleta concluida: $outputDir"
Write-Host "Resumo: $summaryPath"
foreach ($store in $stores) {
    Write-Host "ESP disco $($store.DiskNumber), particao $($store.PartitionNumber): BCD=$($store.BcdExists), bootmgfw=$($store.BootManagerExists), erro=$($store.Error)"
}
Write-Host 'Nenhuma particao foi montada, nenhum BCD foi alterado e nenhum boot foi agendado.'
