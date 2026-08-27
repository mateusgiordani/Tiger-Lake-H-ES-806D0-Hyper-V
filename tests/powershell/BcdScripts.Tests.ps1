BeforeAll {
    $script:BcdDirectory = Join-Path $PSScriptRoot '..\..\tools\windows\bcd'
    . (Join-Path $script:BcdDirectory 'setup-bcd-dual-mode.ps1')
    . (Join-Path $script:BcdDirectory 'audit-bcd-dual-mode.ps1')
    . (Join-Path $script:BcdDirectory 'schedule-hyperv-diagnostic-once.ps1')
    . (Join-Path $script:BcdDirectory 'remove-bcd-dual-mode.ps1')

    $script:NormalId = '{11111111-1111-1111-1111-111111111111}'
    $script:DiagnosticId = '{22222222-2222-2222-2222-222222222222}'
}

Describe 'BCD dual-mode scripts' {
    BeforeEach {
        $script:StatePath = Join-Path $TestDrive ("bcd-dual-mode-$([guid]::NewGuid().ToString('N')).json")
        Mock Assert-IsAdministrator {}
        Mock Assert-BitLockerReady {}
        Mock Get-BcdStatePath { $script:StatePath }
        Mock Get-CurrentBcdIdentifier { $script:NormalId }
        Mock New-BcdBackup { 'C:\BcdBackups\BiosInterposer\test.bcd' }
        Mock Get-CimInstance { [pscustomobject]@{ HypervisorPresent = $false } }
        Mock Invoke-BcdEdit {
            param([string[]]$BcdArguments, [switch]$AllowFailure)
            if ($BcdArguments[0] -eq '/copy') {
                return [pscustomobject]@{
                    ExitCode = 0
                    Output = "The entry was successfully copied to $script:DiagnosticId."
                }
            }
            if ($BcdArguments[0] -eq '/enum') {
                return [pscustomobject]@{
                    ExitCode = 0
                    Output = "identifier              $($BcdArguments[1])"
                }
            }
            return [pscustomobject]@{ ExitCode = 0; Output = '' }
        }
    }

    It 'creates a safe normal entry and a separate diagnostic entry' {
        Invoke-BcdDualModeSetup -Apply

        $state = Get-Content -LiteralPath $script:StatePath -Raw | ConvertFrom-Json
        $state.NormalIdentifier | Should -Be $script:NormalId
        $state.DiagnosticIdentifier | Should -Be $script:DiagnosticId
        Should -Invoke Invoke-BcdEdit -ParameterFilter {
            $BcdArguments -join ' ' -eq "/set $script:NormalId hypervisorlaunchtype off"
        }
        Should -Invoke Invoke-BcdEdit -ParameterFilter {
            $BcdArguments -join ' ' -eq "/deletevalue $script:NormalId vsmlaunchtype"
        }
        Should -Invoke Invoke-BcdEdit -ParameterFilter {
            $BcdArguments -join ' ' -eq "/set $script:DiagnosticId hypervisorloadoptions DISABLEHARDWAREMBEC"
        }
        Should -Invoke Invoke-BcdEdit -ParameterFilter {
            $BcdArguments -join ' ' -eq "/default $script:NormalId"
        }
    }

    It 'refuses a base entry containing an experimental override before backup' {
        Mock Invoke-BcdEdit {
            [pscustomobject]@{
                ExitCode = 0
                Output = "identifier $script:NormalId`nhypervisornumproc 1"
            }
        } -ParameterFilter { $BcdArguments[0] -eq '/enum' }

        { Invoke-BcdDualModeSetup -Apply } | Should -Throw '*hypervisornumproc=1*'
        Should -Invoke New-BcdBackup -Times 0
        Should -Invoke Invoke-BcdEdit -Times 0 -ParameterFilter { $BcdArguments[0] -eq '/copy' }
    }

    It 'accepts the current MBEC fallback as a migration source' {
        Mock Invoke-BcdEdit {
            [pscustomobject]@{
                ExitCode = 0
                Output = "identifier $script:NormalId`nhypervisorloadoptions DISABLEHARDWAREMBEC"
            }
        } -ParameterFilter { $BcdArguments[0] -eq '/enum' }

        { Assert-NoUnsafeInheritedBcdOverrides -Identifier $script:NormalId -AllowMbecFallback } |
            Should -Not -Throw
    }

    It 'rejects extra overrides even when the MBEC fallback is present' {
        Mock Invoke-BcdEdit {
            [pscustomobject]@{
                ExitCode = 0
                Output = "identifier $script:NormalId`nhypervisorloadoptions DISABLEHARDWAREMBEC`nhypervisornumproc 1"
            }
        } -ParameterFilter { $BcdArguments[0] -eq '/enum' }

        { Assert-NoUnsafeInheritedBcdOverrides -Identifier $script:NormalId -AllowMbecFallback } |
            Should -Throw '*hypervisornumproc=1*'
    }

    It 'detects disabled recovery and legacy boot status policy' {
        $found = @(Find-UnsafeInheritedBcdOverrides -EntryOutput (
            "recoveryenabled No`nbootstatuspolicy IgnoreAllFailures"
        ))

        $found.Element | Should -Contain 'recoveryenabled'
        $found.Element | Should -Contain 'bootstatuspolicy'
    }

    It 'deletes the copied entry when diagnostic configuration fails' {
        Mock Invoke-BcdEdit {
            throw 'simulated set failure'
        } -ParameterFilter {
            $BcdArguments -join ' ' -eq "/set $script:DiagnosticId hypervisorloadoptions DISABLEHARDWAREMBEC"
        }

        { Invoke-BcdDualModeSetup -Apply } | Should -Throw '*simulated set failure*'
        Should -Invoke Invoke-BcdEdit -ParameterFilter {
            $BcdArguments -join ' ' -eq "/delete $script:DiagnosticId"
        }
    }

    It 'audits the expected normal, diagnostic and boot manager state' {
        Mock Read-BcdState {
            [pscustomobject]@{
                NormalIdentifier = $script:NormalId
                DiagnosticIdentifier = $script:DiagnosticId
                BackupPath = 'C:\backup.bcd'
            }
        }
        Mock Invoke-BcdEdit {
            if ($BcdArguments[1] -eq $script:NormalId) {
                return [pscustomobject]@{ ExitCode = 0; Output = "hypervisorlaunchtype Off" }
            }
            if ($BcdArguments[1] -eq $script:DiagnosticId) {
                return [pscustomobject]@{
                    ExitCode = 0
                    Output = "hypervisorlaunchtype Auto`nvsmlaunchtype Off`nhypervisorloadoptions DISABLEHARDWAREMBEC"
                }
            }
            return [pscustomobject]@{
                ExitCode = 0
                Output = "default $script:NormalId`ndisplaybootmenu Yes"
            }
        }

        { Invoke-BcdDualModeAudit } | Should -Not -Throw
    }

    It 'schedules only the managed diagnostic entry for the next boot' {
        Mock Read-BcdState {
            [pscustomobject]@{ DiagnosticIdentifier = $script:DiagnosticId }
        }

        Invoke-HyperVDiagnosticOnce -Apply

        Should -Invoke Invoke-BcdEdit -ParameterFilter {
            $BcdArguments -join ' ' -eq "/bootsequence $script:DiagnosticId"
        }
    }

    It 'removes only the managed diagnostic entry from a normal boot' {
        @{ NormalIdentifier = $script:NormalId } | ConvertTo-Json |
            Set-Content -LiteralPath $script:StatePath
        Mock Read-BcdState {
            [pscustomobject]@{
                NormalIdentifier = $script:NormalId
                DiagnosticIdentifier = $script:DiagnosticId
            }
        }

        Remove-BcdDualMode -Apply

        Should -Invoke Invoke-BcdEdit -ParameterFilter {
            $BcdArguments -join ' ' -eq "/deletevalue $script:NormalId vsmlaunchtype"
        }
        Should -Invoke Invoke-BcdEdit -ParameterFilter {
            $BcdArguments -join ' ' -eq "/delete $script:DiagnosticId"
        }
        Test-Path -LiteralPath $script:StatePath | Should -BeFalse
    }
}
