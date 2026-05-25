function Resolve-LarkCliExecutable {
    foreach ($name in @("lark-cli.cmd", "lark-cli.ps1")) {
        $command = Get-Command $name -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($command -and $command.Source) {
            return $command.Source
        }
    }

    $fallback = Get-Command "lark-cli" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($fallback -and $fallback.Source) {
        return $fallback.Source
    }

    throw "lark-cli was not found on PATH"
}

function ConvertFrom-BotEventLine {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Line
    )

    if ([string]::IsNullOrWhiteSpace($Line)) {
        return $null
    }

    $event = $Line | ConvertFrom-Json -ErrorAction Stop
    if ($event.type -ne "im.message.receive_v1") {
        return $null
    }

    if (-not $event.chat_id) {
        return $null
    }

    return $event
}

function New-BotReplyText {
    param(
        [Parameter(Mandatory = $true)]
        $Event
    )

    $content = ""
    if ($Event.content) {
        $content = ([string]$Event.content).Trim()
    }

    if ($content.Length -gt 120) {
        $content = $content.Substring(0, 120) + "..."
    }

    if ($content) {
        return "Received: $content"
    }

    return "Received."
}

function New-BotReplyArgs {
    param(
        [Parameter(Mandatory = $true)]
        $Event,

        [Parameter(Mandatory = $true)]
        [string]$Text
    )

    $idempotencyKey = $Event.event_id
    if (-not $idempotencyKey) {
        $idempotencyKey = $Event.message_id
    }
    if (-not $idempotencyKey) {
        $idempotencyKey = [Guid]::NewGuid().ToString("N")
    }

    return @(
        "im",
        "+messages-send",
        "--as",
        "bot",
        "--chat-id",
        $Event.chat_id,
        "--text",
        $Text,
        "--idempotency-key",
        $idempotencyKey
    )
}
