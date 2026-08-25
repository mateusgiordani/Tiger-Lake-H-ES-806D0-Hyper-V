$ErrorActionPreference = 'Stop'

$targetDiskNumber = 4
$targetSerial = '03001429060822130415'
$expectedMinSize = 126000000000
$expectedMaxSize = 126200000000
$workspace = Split-Path -Parent $PSScriptRoot
$source = Join-Path $workspace 'polestar-hm570-backup-only'
$logPath = Join-Path $PSScriptRoot 'prepare-ps5-bios-backup.log'
$diskpartScript = Join-Path $PSScriptRoot 'prepare-ps5-diskpart.txt'

Start-Transcript -LiteralPath $logPath -Force

try {
    $disk = Get-Disk -Number $targetDiskNumber
    if ($disk.BusType -ne 'USB' -or
        $disk.SerialNumber.Trim() -ne $targetSerial -or
        $disk.Size -lt $expectedMinSize -or
        $disk.Size -gt $expectedMaxSize -or
        $disk.IsBoot -or
        $disk.IsSystem) {
        throw 'Verificacao de seguranca falhou: o disco USB alvo nao corresponde ao SanDisk PS5 autorizado.'
    }

    if (-not (Test-Path -LiteralPath (Join-Path $source 'Fpt.efi')) -or
        -not (Test-Path -LiteralPath (Join-Path $source 'EFI\BOOT\BOOTX64.EFI'))) {
        throw 'Arquivos-fonte do pacote de backup nao foram encontrados.'
    }

    if (-not (Test-Path -LiteralPath $diskpartScript)) {
        throw 'Roteiro do DiskPart nao foi encontrado.'
    }

    & diskpart.exe /s $diskpartScript
    if ($LASTEXITCODE -ne 0) {
        throw "DiskPart terminou com codigo $LASTEXITCODE."
    }

    Get-Volume -DriveLetter G,H | Out-Null
    $bootRoot = 'G:\'
    Copy-Item -LiteralPath (Join-Path $source 'EFI') -Destination $bootRoot -Recurse
    Copy-Item -LiteralPath (Join-Path $source 'Fpt.efi') -Destination $bootRoot
    Copy-Item -LiteralPath (Join-Path $source 'LEIA-ME-BACKUP.txt') -Destination $bootRoot

    Write-Output 'BOOT_DRIVE=G:'
    Write-Output 'DATA_DRIVE=H:'
}
catch {
    Write-Error ($_ | Out-String)
    exit 1
}
finally {
    Stop-Transcript
}
