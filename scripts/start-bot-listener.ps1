$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $Root "logs"
$LibPath = Join-Path $PSScriptRoot "bot-listener-lib.ps1"
. $LibPath

if (!(Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

$LogFile = Join-Path $LogDir "bot-listener.log"

function Write-Log($Message) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] $Message"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line
}

function New-LarkConsumeProcessStartInfo($LarkCli) {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $LarkCli
    $psi.Arguments = "event consume --as bot im.message.receive_v1"
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    return $psi
}

function Send-BotReply($LarkCli, $Event) {
    $replyText = New-BotReplyText -Event $Event
    $replyArgs = New-BotReplyArgs -Event $Event -Text $replyText

    Write-Log "Replying to chat $($Event.chat_id), message $($Event.message_id)"
    $output = & $LarkCli @replyArgs 2>&1
    foreach ($line in $output) {
        Write-Log "send: $line"
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Log "ERROR: reply failed with exit code $LASTEXITCODE"
    }
}

Write-Log "=== Bot Event Listener Started ==="
Write-Log "Log file: $LogFile"
Write-Log "Press Ctrl+C to stop. Auto-restart enabled."

$LarkCli = Resolve-LarkCliExecutable
Write-Log "Using lark-cli: $LarkCli"

while ($true) {
    Write-Log "Connecting to Feishu event stream..."

    try {
        $psi = New-LarkConsumeProcessStartInfo -LarkCli $LarkCli

        $process = [System.Diagnostics.Process]::Start($psi)
        Write-Log "Listener PID: $($process.Id)"

        while (-not $process.StandardOutput.EndOfStream) {
            $line = $process.StandardOutput.ReadLine()
            if ([string]::IsNullOrWhiteSpace($line)) {
                continue
            }

            Write-Log "event: $line"
            try {
                $event = ConvertFrom-BotEventLine -Line $line
                if ($event) {
                    Send-BotReply -LarkCli $LarkCli -Event $event
                }
            } catch {
                Write-Log "ERROR: failed to handle event: $($_.Exception.Message)"
            }
        }

        $stderr = $process.StandardError.ReadToEnd()
        if ($stderr) {
            foreach ($line in ($stderr -split "`r?`n")) {
                if ($line) {
                    Write-Log "event stderr: $line"
                }
            }
        }
    } catch {
        Write-Log "ERROR: $($_.Exception.Message)"
    }

    Write-Log "Listener exited. Restarting in 5 seconds..."
    Start-Sleep -Seconds 5
}
