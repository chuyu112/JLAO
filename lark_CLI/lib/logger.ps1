$script:LogDir = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) "logs"
if (!(Test-Path $script:LogDir)) {
    New-Item -ItemType Directory -Path $script:LogDir -Force | Out-Null
}
$script:LogFile = Join-Path $script:LogDir "lark-agent.log"

function Write-AgentLog {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Message,
        [string]$Level = "INFO"
    )
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] [$Level] $Message"
    Write-Host $line
    try {
        Add-Content -Path $script:LogFile -Value $line -ErrorAction SilentlyContinue
    } catch {}
}

function Write-ErrorLog {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-AgentLog -Message $Message -Level "ERROR"
}
