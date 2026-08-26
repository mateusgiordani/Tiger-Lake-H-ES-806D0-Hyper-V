Set-StrictMode -Version Latest

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Assert-IsAdministrator {
    if (-not (Test-IsAdministrator)) {
        throw 'Execute este script em um PowerShell elevado (Executar como administrador).'
    }
}

function Invoke-BcdEdit {
    param(
        [Parameter(Mandatory)] [string[]]$BcdArguments,
        [switch]$AllowFailure
    )

    $executable = Join-Path $env:SystemRoot 'System32\bcdedit.exe'
    $output = (& $executable @BcdArguments 2>&1) -join "`n"
    $exitCode = $LASTEXITCODE
    if (($exitCode -ne 0) -and (-not $AllowFailure)) {
        throw "bcdedit $($BcdArguments -join ' ') falhou ($exitCode):`n$output"
    }

    return [pscustomobject]@{
        ExitCode = $exitCode
        Output = $output
    }
}

function Assert-BitLockerReady {
    $command = Get-Command Get-BitLockerVolume -ErrorAction SilentlyContinue
    if (-not $command) {
        Write-Warning 'Get-BitLockerVolume nao esta disponivel; confirme manualmente que voce possui a chave de recuperacao.'
        return
    }

    $volume = Get-BitLockerVolume -MountPoint $env:SystemDrive
    if (($volume.ProtectionStatus -eq 'On') -or ($volume.ProtectionStatus -eq 1)) {
        throw 'O BitLocker esta protegido. Salve a chave de recuperacao e suspenda a protecao antes de alterar o BCD.'
    }
}

function Assert-BcdIdentifier {
    param([Parameter(Mandatory)] [string]$Identifier)

    if ($Identifier -notmatch '^\{[0-9A-Fa-f-]{36}\}$') {
        throw "Identificador BCD invalido: $Identifier"
    }
}

function Get-CurrentBcdIdentifier {
    $entry = Invoke-BcdEdit -BcdArguments @('/enum', '{current}', '/v')
    $match = [regex]::Match($entry.Output, '\{[0-9A-Fa-f-]{36}\}')
    if (-not $match.Success) {
        throw "Nao foi possivel obter o GUID real de {current}:`n$($entry.Output)"
    }
    return $match.Value
}

function Get-BcdStatePath {
    return (Join-Path $env:ProgramData 'BiosInterposer\bcd-dual-mode.json')
}

function Read-BcdState {
    param([string]$StatePath = (Get-BcdStatePath))

    if (-not (Test-Path -LiteralPath $StatePath -PathType Leaf)) {
        throw "Estado nao encontrado: $StatePath. Execute setup-bcd-dual-mode.ps1 primeiro."
    }

    $state = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
    Assert-BcdIdentifier -Identifier ([string]$state.NormalIdentifier)
    Assert-BcdIdentifier -Identifier ([string]$state.DiagnosticIdentifier)
    return $state
}

function New-BcdBackup {
    param([Parameter(Mandatory)] [string]$Label)

    $backupDirectory = Join-Path $env:SystemDrive 'BcdBackups\BiosInterposer'
    New-Item -ItemType Directory -Path $backupDirectory -Force | Out-Null
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $backupPath = Join-Path $backupDirectory "$Label-$stamp.bcd"
    [void](Invoke-BcdEdit -BcdArguments @('/export', $backupPath))
    return $backupPath
}

function Remove-BcdValueIfPresent {
    param(
        [Parameter(Mandatory)] [string]$Identifier,
        [Parameter(Mandatory)] [string]$Element
    )

    return Invoke-BcdEdit -BcdArguments @('/deletevalue', $Identifier, $Element) -AllowFailure
}

function Find-UnsafeInheritedBcdOverrides {
    param([Parameter(Mandatory)] [string]$EntryOutput)

    $unsafeElements = @(
        'bootlog',
        'bootdebug',
        'bootstatuspolicy',
        'configaccesspolicy',
        'debug',
        'disabledynamictick',
        'firstmegabytepolicy',
        'groupaware',
        'groupsize',
        'hypervisordisableslat',
        'hypervisoriommupolicy',
        'hypervisorloadoptions',
        'hypervisornumproc',
        'hypervisorschedulertype',
        'hypervisorusevapic',
        'maxmem',
        'nocrashautoreboot',
        'nointegritychecks',
        'nolowmem',
        'numproc',
        'onecpu',
        'removememory',
        'safeboot',
        'sos',
        'testsigning',
        'truncatememory',
        'tscsyncpolicy',
        'usefirmwarepcisettings',
        'uselegacyapicmode',
        'usephysicaldestination',
        'useplatformclock',
        'useplatformtick',
        'x2apicpolicy',
        'xsaveremovefeature'
    )
    $found = @()
    foreach ($element in $unsafeElements) {
        $match = [regex]::Match(
            $EntryOutput,
            '(?im)^\s*' + [regex]::Escape($element) + '\s+(.+?)\s*$'
        )
        if ($match.Success) {
            $found += [pscustomobject]@{
                Element = $element
                Value = $match.Groups[1].Value
            }
        }
    }
    $disabledRecovery = [regex]::Match(
        $EntryOutput,
        '(?im)^\s*recoveryenabled\s+(No|Off|False|0)\s*$'
    )
    if ($disabledRecovery.Success) {
        $found += [pscustomobject]@{
            Element = 'recoveryenabled'
            Value = $disabledRecovery.Groups[1].Value
        }
    }
    return $found
}

function Assert-NoUnsafeInheritedBcdOverrides {
    param([Parameter(Mandatory)] [string]$Identifier)

    $entry = Invoke-BcdEdit -BcdArguments @('/enum', $Identifier, '/v')
    $overrides = @(Find-UnsafeInheritedBcdOverrides -EntryOutput $entry.Output)
    if ($overrides.Count -gt 0) {
        $rendered = ($overrides | ForEach-Object { "$($_.Element)=$($_.Value)" }) -join ', '
        throw "A entrada-base contem overrides experimentais: $rendered. Remova-os ou escolha uma entrada limpa antes do setup."
    }
}
