# JLAO Lark Agent - Main Event Loop
# Fixes the stdin-closing bug by keeping stdin open and using async reads

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
. "$PSScriptRoot\lib\logger.ps1"
. "$PSScriptRoot\lib\event-parser.ps1"
. "$PSScriptRoot\lib\ai-handler.ps1"

$LogDir = Join-Path $Root "logs"
if (!(Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
$LogFile = Join-Path $LogDir "lark-agent.log"

$script:CurrentProcess = $null
$script:ShouldRun = $true
$script:EventQueue = [System.Collections.ArrayList]::Synchronized([System.Collections.ArrayList]::new())
$script:StderrQueue = [System.Collections.ArrayList]::Synchronized([System.Collections.ArrayList]::new())

function Write-Log($Message, $Level = "INFO") {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] [$Level] $Message"
    Write-Host $line
    try { Add-Content -Path $LogFile -Value $line -ErrorAction SilentlyContinue } catch {}
}

function Write-Err($Message) { Write-Log $Message "ERROR" }

# Graceful shutdown on Ctrl+C (only in interactive console)
try { [Console]::TreatControlCAsInput = $true } catch {}

function Process-EventLine($Line) {
    Write-Log "stdout: $Line"
    try {
        $event = ConvertFrom-LarkEventLine -Line $Line
        if ($event) {
            Write-Log "Message from $($event.sender_id): $($event.content)"
            $systemPrompt = Get-AISystemPrompt
            $reply = Invoke-AIReply -UserMessage $event.content -SystemPrompt $systemPrompt
            $sent = Send-LarkBotReply -Event $event -ReplyText $reply
            if (-not $sent) { Write-Err "Failed to send reply" }
        }
    } catch {
        Write-Err "Event handler error: $($_.Exception.Message)"
    }
}

function Process-StderrLine($Line) {
    Write-Log "stderr: $Line"
}

function Start-AgentListener {
    $LarkCli = Resolve-LarkCliExecutable
    Write-Log "Using lark-cli: $LarkCli"

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $LarkCli
    $psi.Arguments = "event consume --as bot im.message.receive_v1"
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    # lark-cli on Windows uses system default encoding (GBK on Chinese Windows)
    $psi.StandardOutputEncoding = [System.Text.Encoding]::Default
    $psi.StandardErrorEncoding = [System.Text.Encoding]::Default

    $process = [System.Diagnostics.Process]::Start($psi)
    $script:CurrentProcess = $process
    Write-Log "Listener PID: $($process.Id)"

    # Clear queues
    $script:EventQueue.Clear()
    $script:StderrQueue.Clear()

    # Async output handler via Register-ObjectEvent (only queues data, no string processing)
    $outputJob = Register-ObjectEvent -InputObject $process -EventName OutputDataReceived -Action {
        if ([string]::IsNullOrWhiteSpace($EventArgs.Data)) { return }
        [void]$script:EventQueue.Add($EventArgs.Data.Trim())
    }

    # Async error handler
    $errorJob = Register-ObjectEvent -InputObject $process -EventName ErrorDataReceived -Action {
        if ([string]::IsNullOrWhiteSpace($EventArgs.Data)) { return }
        [void]$script:StderrQueue.Add($EventArgs.Data.Trim())
    }

    $process.BeginOutputReadLine()
    $process.BeginErrorReadLine()

    # Keep stdin open by writing a newline every 30 seconds
    $stdinTimer = New-Object System.Timers.Timer
    $stdinTimer.Interval = 30000
    $stdinTimer.AutoReset = $true
    $stdinTimer.Add_Elapsed({
        param($s, $e)
        try {
            if ($script:CurrentProcess -and -not $script:CurrentProcess.HasExited) {
                $script:CurrentProcess.StandardInput.WriteLine("")
            }
        } catch {}
    })
    $stdinTimer.Start()

    # Main loop - process queued events in main runspace (correct encoding)
    while ($script:ShouldRun -and -not $process.HasExited) {
        # Process stdout events
        while ($script:EventQueue.Count -gt 0) {
            $line = $script:EventQueue[0]
            $script:EventQueue.RemoveAt(0)
            Process-EventLine -Line $line
        }

        # Process stderr lines
        while ($script:StderrQueue.Count -gt 0) {
            $line = $script:StderrQueue[0]
            $script:StderrQueue.RemoveAt(0)
            Process-StderrLine -Line $line
        }

        # Check for Ctrl+C (only in interactive console)
        try {
            if ([Console]::KeyAvailable) {
                $key = [Console]::ReadKey($true)
                if ($key.Key -eq "C" -and $key.Modifiers -eq "Control") {
                    Write-Log "Ctrl+C received, shutting down gracefully..."
                    $script:ShouldRun = $false
                    break
                }
            }
        } catch {}

        Start-Sleep -Milliseconds 100
    }

    $stdinTimer.Stop()
    $stdinTimer.Dispose()

    if (-not $process.HasExited) {
        try {
            $process.StandardInput.Close()
            if (-not $process.WaitForExit(5000)) {
                $process.Kill()
            }
        } catch {
            Write-Err "Error stopping process: $($_.Exception.Message)"
        }
    }

    $process.CancelOutputRead()
    $process.CancelErrorRead()

    # Unregister event subscribers
    if ($outputJob) { Unregister-Event -SourceIdentifier $outputJob.Name -ErrorAction SilentlyContinue }
    if ($errorJob) { Unregister-Event -SourceIdentifier $errorJob.Name -ErrorAction SilentlyContinue }

    $process.Dispose()
    $script:CurrentProcess = $null

    $exitCode = if ($process.HasExited) { $process.ExitCode } else { "killed" }
    Write-Log "Listener exited with code: $exitCode"
}

# Main entry
Write-Log "=== JLAO Lark Agent Started ==="
Write-Log "Log file: $LogFile"
Write-Log "Press Ctrl+C to stop. Auto-restart enabled."

while ($true) {
    try {
        Start-AgentListener
    } catch {
        Write-Err "Agent crashed: $($_.Exception.Message)"
    }

    if (-not $script:ShouldRun) {
        Write-Log "Agent stopped by user."
        break
    }

    Write-Log "Restarting in 5 seconds..."
    Start-Sleep -Seconds 5
}

Write-Log "=== JLAO Lark Agent Stopped ==="
