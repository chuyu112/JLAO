$EventParserRoot = Split-Path -Parent $PSScriptRoot
. "$EventParserRoot\lib\logger.ps1"

function Resolve-LarkCliExecutable {
    foreach ($name in @("lark-cli.cmd", "lark-cli.ps1", "lark-cli")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($cmd -and $cmd.Source) {
            return $cmd.Source
        }
    }
    throw "lark-cli was not found on PATH. Please install it first: npm install -g @larksuiteoapi/lark-cli"
}

function ConvertFrom-LarkEventLine {
    param([Parameter(Mandatory = $true)][string]$Line)

    if ([string]::IsNullOrWhiteSpace($Line)) { return $null }

    # lark-cli event consume outputs NDJSON lines
    try {
        $event = $Line | ConvertFrom-Json -ErrorAction Stop
    } catch {
        Write-ErrorLog "Failed to parse JSON: $Line"
        return $null
    }

    # Filter only message receive events
    if ($event.type -ne "im.message.receive_v1") { return $null }
    if (-not $event.chat_id) { return $null }

    # Extract text content from various message types
    # Feishu content is usually a JSON string like '{"text":"hello"}'
    $textContent = ""
    if ($event.content) {
        $rawContent = $event.content
        # If content is a JSON string, parse it
        if ($rawContent -is [string]) {
            try {
                $parsed = $rawContent | ConvertFrom-Json -ErrorAction Stop
                if ($parsed.text) {
                    $textContent = $parsed.text.Trim()
                } else {
                    $textContent = $rawContent.Trim()
                }
            } catch {
                $textContent = $rawContent.Trim()
            }
        } elseif ($rawContent.text) {
            $textContent = $rawContent.text.Trim()
        }
    }

    # Build normalized event object
    return [PSCustomObject]@{
        type         = $event.type
        chat_id      = $event.chat_id
        sender_id    = $event.sender_id
        sender_name  = $event.sender_name
        content      = $textContent
        event_id     = $event.event_id
        message_id   = $event.message_id
        message_type = $event.message_type
        timestamp    = if ($event.timestamp) { $event.timestamp } else { [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() }
        raw          = $Line
    }
}

function Send-LarkBotReply {
    param(
        [Parameter(Mandatory = $true)][object]$Event,
        [Parameter(Mandatory = $true)][string]$ReplyText
    )

    $LarkCli = Resolve-LarkCliExecutable
    $idempotencyKey = if ($Event.event_id) { $Event.event_id } elseif ($Event.message_id) { $Event.message_id } else { [Guid]::NewGuid().ToString("N") }

    $args = @(
        "im", "+messages-send",
        "--as", "bot",
        "--chat-id", $Event.chat_id,
        "--text", $ReplyText,
        "--idempotency-key", $idempotencyKey
    )

    Write-AgentLog "Sending reply to chat $($Event.chat_id): $ReplyText"

    try {
        # Fix encoding for Chinese characters when calling lark-cli from event runspace
        $prevEncoding = $OutputEncoding
        $OutputEncoding = [System.Text.Encoding]::UTF8
        $output = & $LarkCli @args 2>&1
        $OutputEncoding = $prevEncoding
        $exitCode = $LASTEXITCODE
        if ($exitCode -ne 0) {
            Write-ErrorLog "Reply failed with exit code $exitCode. Output: $output"
            return $false
        }
        Write-AgentLog "Reply sent successfully"
        return $true
    } catch {
        Write-ErrorLog "Exception sending reply: $($_.Exception.Message)"
        return $false
    }
}
