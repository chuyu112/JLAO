. "$PSScriptRoot\logger.ps1"

function Invoke-AIReply {
    param(
        [Parameter(Mandatory=$true)][string]$UserMessage,
        [Parameter(Mandatory=$false)][string]$SystemPrompt = ""
    )

    # Check if bl CLI is available and API key is configured
    $blCli = Get-Command "bl" -ErrorAction SilentlyContinue
    $hasApiKey = [bool]$env:DASHSCOPE_API_KEY

    if (-not $blCli -or -not $hasApiKey) {
        Write-AgentLog "AI unavailable (bl missing or no API key). Using echo fallback."
        return "【自动回复】收到: $UserMessage"
    }

    $prompt = $UserMessage
    if ($SystemPrompt) {
        $prompt = "System: $SystemPrompt User: $UserMessage"
    }
    Write-AgentLog "Calling AI with prompt length: $($prompt.Length)"
    try {
        $job = Start-Job -ScriptBlock {
            param($p)
            $output = & bl text chat --message $p
            return $output
        } -ArgumentList $prompt
        $completed = $job | Wait-Job -Timeout 60
        if (-not $completed) {
            Stop-Job $job -ErrorAction SilentlyContinue
            Remove-Job $job -ErrorAction SilentlyContinue
            Write-ErrorLog "AI timeout"
            return "[AI timeout] Please try again."
        }
        $result = Receive-Job $job
        Remove-Job $job
        $lines = $result | Where-Object { $_.Trim() -ne "" }
        if ($lines.Count -eq 0) { return "[AI empty response]" }
        $aiText = $lines[-1].Trim()
        if ($aiText.Length -gt 2000) { $aiText = $aiText.Substring(0, 1997) + "..." }
        return $aiText
    } catch {
        Write-ErrorLog "AI call failed: $($_.Exception.Message)"
        return "[AI error] Failed to generate response."
    }
}

function Get-AISystemPrompt {
    return "You are JLAO Agent, a helpful AI assistant integrated with Feishu (Lark). Keep responses concise and actionable."
}
