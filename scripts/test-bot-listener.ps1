$ErrorActionPreference = "Stop"

$LibPath = Join-Path $PSScriptRoot "bot-listener-lib.ps1"
. $LibPath

function Assert-Equal($Actual, $Expected, $Message) {
    if ($Actual -ne $Expected) {
        throw "$Message. Expected '$Expected', got '$Actual'."
    }
}

function Assert-True($Condition, $Message) {
    if (-not $Condition) {
        throw $Message
    }
}

$sampleLine = '{"type":"im.message.receive_v1","chat_id":"oc_test","sender_id":"ou_user","content":"hello","event_id":"evt_123","message_id":"om_123","message_type":"text"}'
$event = ConvertFrom-BotEventLine -Line $sampleLine

Assert-Equal $event.chat_id "oc_test" "Parses chat_id from receive event"
Assert-Equal $event.content "hello" "Parses content from receive event"
Assert-Equal (New-BotReplyText -Event $event) "Received: hello" "Builds acknowledgement reply"

$argsList = New-BotReplyArgs -Event $event -Text "Received: hello"
Assert-Equal ($argsList -join " ") "im +messages-send --as bot --chat-id oc_test --text Received: hello --idempotency-key evt_123" "Builds send args"

$larkCli = Resolve-LarkCliExecutable
Assert-True ($larkCli -match "lark-cli\.(cmd|ps1)$") "Resolve-LarkCliExecutable should prefer Windows lark-cli shims"

Write-Output "bot-listener tests passed"
