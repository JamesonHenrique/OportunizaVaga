# Pester v5: only synthetic jobs/processes and isolated fixtures; no browser or real data.
BeforeAll {
    $script:Source = Join-Path (Split-Path -Parent $PSScriptRoot) 'bot/followup.ps1'
    $script:HostExe = (Get-Process -Id $PID).Path
    $script:Ast = [System.Management.Automation.Language.Parser]::ParseFile($script:Source, [ref]$null, [ref]$null)
    $definition = $script:Ast.Find({ param($n)
        $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Invoke-FollowupModel'
    }, $true)
    Set-Item Function:script:Invoke-FollowupModel -Value ([scriptblock]::Create($definition.Body.Extent.Text.TrimStart('{').TrimEnd('}')))

    function New-FakeExecutable {
        param($Directory, [int]$Code = 0, [string]$Message = 'synthetic output')
        $native = Join-Path $Directory 'native.ps1'
        "[Console]::Out.WriteLine('$Message'); [Console]::Error.WriteLine('synthetic stderr'); exit $Code" |
            Set-Content $native -Encoding UTF8
        $shim = Join-Path $Directory 'fake-opencode.ps1'
        "& '$($script:HostExe.Replace("'", "''"))' -NoProfile -NonInteractive -File '$($native.Replace("'", "''"))'" |
            Set-Content $shim -Encoding UTF8
        return $shim
    }

    function Invoke-IsolatedFollowup {
        param($Directory, $Mode, [int]$Code = 0, [string]$Message = 'synthetic output')
        $bot = New-Item -ItemType Directory (Join-Path $Directory 'bot') -Force
        $homeDir = New-Item -ItemType Directory (Join-Path $Directory 'home') -Force
        $tempDir = New-Item -ItemType Directory (Join-Path $Directory 'temp') -Force
        $fake = New-FakeExecutable -Directory $Directory -Code $Code -Message $Message
        if ($Mode -eq 'quota-recovery') {
            @'
$counter = Join-Path $PSScriptRoot 'attempts.txt'
$count = if (Test-Path $counter) { [int](Get-Content $counter) } else { 0 }
Set-Content $counter ($count + 1)
if ($count -eq 0) { 'QUOTA_EXAUSTA'; exit 7 }
'synthetic recovery'; exit 0
'@ | Set-Content (Join-Path $Directory 'native.ps1') -Encoding UTF8
        }
        $text = Get-Content $script:Source -Raw
        $cdp = $script:Ast.Find({ param($n)
            $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Test-Cdp'
        }, $true)
        $cdpValue = if ($Mode -eq 'cdp-skip') { '$false' } else { '$true' }
        $text.Replace($cdp.Extent.Text, "function Test-Cdp { return $cdpValue }") |
            Set-Content (Join-Path $bot 'followup.ps1') -Encoding UTF8
        'synthetic prompt' | Set-Content (Join-Path $bot 'prompt_followup.md')
        '{"aplicadas":[]}' | Set-Content (Join-Path $Directory 'applications.json')
        @'
function Enter-ChromeLock {
    param($Name, $Prio, $WaitSeconds)
    [pscustomobject]@{ Status = $(if ($Mode -eq 'lock-skip') { 1 } else { 0 }) }
}
function Exit-ChromeLock { param($Lock) }
'@ | Set-Content (Join-Path $bot 'chrome-lock.ps1')
        $wrapper = Join-Path $Directory 'run.ps1'
        # The wrapper overrides only dependencies in a disposable script copy.
        @'
param($Fixture, $Fake, $HomeDir, $TempDir, $Mode)
$env:USERPROFILE = $HomeDir
$env:TEMP = $TempDir
$env:TMP = $TempDir
$env:APLICADAS_FILE = Join-Path $Fixture 'applications.json'
$env:OV_FOLLOWUP_OK_MARK = Join-Path $Fixture 'success.ok'
$env:OV_OPENCODE_CONFIG_CONTENT = '{}'
function Get-Command { param($Name, $ErrorAction); [pscustomobject]@{ Source = $Fake } }
function Start-Job {
    param($ScriptBlock, $ArgumentList, $ErrorAction)
    switch ($Mode) {
        'missing' { $ScriptBlock = { } }
        'malformed' { $ScriptBlock = { 'not a process result' } }
        'null-code' { $ScriptBlock = { [pscustomobject]@{ Protocol = 'FollowupProcessResult/v1'; ExitCode = $null; Output = @('bad') } } }
        'string-code' { $ScriptBlock = { [pscustomobject]@{ Protocol = 'FollowupProcessResult/v1'; ExitCode = '0'; Output = @('bad') } } }
        'protocol-array' { $ScriptBlock = { [pscustomobject]@{ Protocol = @('FollowupProcessResult/v1', 'invalid'); ExitCode = 0; Output = @('bad') } } }
        'bad-output' { $ScriptBlock = { [pscustomobject]@{ Protocol = 'FollowupProcessResult/v1'; ExitCode = 0; Output = @(42) } } }
        'duplicate' { $ScriptBlock = { 1..2 | ForEach-Object { [pscustomobject]@{ Protocol = 'FollowupProcessResult/v1'; ExitCode = 0; Output = @('bad') } } } }
        'failed' { $ScriptBlock = { throw 'synthetic job failure' } }
        'timeout' { $ScriptBlock = { Start-Sleep -Seconds 60 } }
    }
    Microsoft.PowerShell.Core\Start-Job -ScriptBlock $ScriptBlock -ArgumentList $ArgumentList
}
if ($Mode -eq 'timeout') {
    function Wait-Job { param($Job, $Timeout, $ErrorAction); return $null }
}
if ($Mode -eq 'receive-error') {
    function Receive-Job { param($Job, $ErrorAction); throw 'synthetic receive failure' }
}
if ($Mode -eq 'recent-skip') { Set-Content $env:OV_FOLLOWUP_OK_MARK 'existing success' }
& (Join-Path $Fixture 'bot/followup.ps1')
exit $LASTEXITCODE
'@ | Set-Content $wrapper -Encoding UTF8
        $output = & $script:HostExe -NoProfile -NonInteractive -File $wrapper $Directory $fake $homeDir.FullName $tempDir.FullName $Mode 2>&1
        $code = $LASTEXITCODE
        [pscustomobject]@{ ExitCode = $code; Marker = (Test-Path (Join-Path $Directory 'success.ok')); Output = $output }
    }
}

Describe 'followup.ps1 child process contract' {
    It 'preserves native exit <Code> even when the job completes normally' -ForEach @(@{ Code = 7 }, @{ Code = 0 }) {
        $fake = New-FakeExecutable -Directory $TestDrive -Code $Code
        $result = Invoke-FollowupModel -Bin $fake -Model 'fake' -Title 'test' -Prompt 'fixture' -Config '{}'
        $result.ExitCode | Should -Be $Code
        $result.Output | Should -Contain 'synthetic output'
        ($result.Output -join "`n") | Should -Match 'synthetic stderr'
    }

    It 'times out a real job and removes it' {
        $fake = Join-Path $TestDrive 'slow.ps1'
        'Start-Sleep -Seconds 60' | Set-Content $fake
        $before = @(Get-Job).Count
        $result = Invoke-FollowupModel -Bin $fake -TimeoutSeconds 1
        $result.ExitCode | Should -Be 124
        @(Get-Job).Count | Should -Be $before
    }

    It 'stops the directly invoked native executable on timeout' {
        $fixture = New-Item -ItemType Directory (Join-Path $TestDrive 'native-timeout')
        $fake = New-FakeExecutable -Directory $fixture.FullName
        @'
Set-Content (Join-Path $PSScriptRoot 'native.pid.tmp') $PID
Move-Item (Join-Path $PSScriptRoot 'native.pid.tmp') (Join-Path $PSScriptRoot 'native.pid')
Start-Sleep -Seconds 60
'@ | Set-Content (Join-Path $fixture 'native.ps1') -Encoding UTF8
        $script:NativePidFile = Join-Path $fixture 'native.pid'
        $script:NativeProcess = $null
        $script:RealWaitJob = Get-Command Wait-Job -CommandType Cmdlet
        # Wait for proof that the native executable started before timing out.
        # This avoids a false pass that only cancels job startup on slower CI hosts.
        Mock Wait-Job {
            param($Job, $Timeout)
            $watch = [System.Diagnostics.Stopwatch]::StartNew()
            while (-not (Test-Path $script:NativePidFile) -and $watch.Elapsed.TotalSeconds -lt 20) {
                Start-Sleep -Milliseconds 50
            }
            if (-not (Test-Path $script:NativePidFile)) { throw 'native fixture did not start' }
            $nativePid = [int](Get-Content $script:NativePidFile)
            $script:NativeProcess = [System.Diagnostics.Process]::GetProcessById($nativePid)
            & $script:RealWaitJob -Job $Job -Timeout $Timeout
        }
        $before = @(Get-Job).Count
        try {
            $result = Invoke-FollowupModel -Bin $fake -TimeoutSeconds 1
            $result.ExitCode | Should -Be 124 -Because ($result.Output -join "`n")
            $script:NativeProcess | Should -Not -BeNullOrEmpty
            $script:NativeProcess.WaitForExit(5000) | Should -BeTrue
            @(Get-Job).Count | Should -Be $before
        } finally {
            # Clean up only the synthetic process, even if the assertion fails.
            if ($null -ne $script:NativeProcess) {
                if (-not $script:NativeProcess.HasExited) { $script:NativeProcess.Kill() }
                $script:NativeProcess.Dispose()
            }
        }
        # This checks the direct native process; detached descendants are outside
        # this contract. PowerShell 5.1 has no portable process-tree kill API.
    }
}

Describe 'followup.ps1 caller status and success marker (isolated copy)' {
    It '<Mode> exits <Expected> with marker=<Marker>' -ForEach @(
        @{ Mode = 'native'; Code = 7; Expected = 7; Marker = $false }
        @{ Mode = 'native'; Code = 0; Expected = 0; Marker = $true }
        @{ Mode = 'missing'; Code = 0; Expected = 1; Marker = $false }
        @{ Mode = 'malformed'; Code = 0; Expected = 1; Marker = $false }
        @{ Mode = 'null-code'; Code = 0; Expected = 1; Marker = $false }
        @{ Mode = 'string-code'; Code = 0; Expected = 1; Marker = $false }
        @{ Mode = 'protocol-array'; Code = 0; Expected = 1; Marker = $false }
        @{ Mode = 'bad-output'; Code = 0; Expected = 1; Marker = $false }
        @{ Mode = 'duplicate'; Code = 0; Expected = 1; Marker = $false }
        @{ Mode = 'failed'; Code = 0; Expected = 1; Marker = $false }
        @{ Mode = 'receive-error'; Code = 0; Expected = 1; Marker = $false }
        @{ Mode = 'timeout'; Code = 0; Expected = 124; Marker = $false }
        @{ Mode = 'cdp-skip'; Code = 0; Expected = 0; Marker = $false }
        @{ Mode = 'lock-skip'; Code = 0; Expected = 0; Marker = $false }
        @{ Mode = 'recent-skip'; Code = 0; Expected = 0; Marker = $true }
    ) {
        $fixture = New-Item -ItemType Directory (Join-Path $TestDrive ([guid]::NewGuid().ToString()))
        $result = Invoke-IsolatedFollowup -Directory $fixture.FullName -Mode $Mode -Code $Code
        $result.ExitCode | Should -Be $Expected -Because ($result.Output -join "`n")
        $result.Marker | Should -Be $Marker
    }

    It 'exhausted quota never creates a marker, including native exit zero' {
        $fixture = New-Item -ItemType Directory (Join-Path $TestDrive 'quota')
        $result = Invoke-IsolatedFollowup -Directory $fixture.FullName -Mode 'native' -Code 0 -Message 'QUOTA_EXAUSTA'
        $result.ExitCode | Should -Be 1
        $result.Marker | Should -BeFalse
    }

    It 'tries the next model after quota and marks a subsequent success' {
        $fixture = New-Item -ItemType Directory (Join-Path $TestDrive 'recovery')
        $result = Invoke-IsolatedFollowup -Directory $fixture.FullName -Mode 'quota-recovery'
        $result.ExitCode | Should -Be 0
        $result.Marker | Should -BeTrue
        [int](Get-Content (Join-Path $fixture 'attempts.txt')) | Should -Be 2
    }
}
