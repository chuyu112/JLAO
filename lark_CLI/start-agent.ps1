$LogFile = Join-Path (Split-Path -Parent $PSScriptRoot) "logs\lark-agent.log"
Write-Host "Starting JLAO Lark Agent..."
Write-Host "Log: $LogFile"
Start-Process powershell -ArgumentList "-File $PSScriptRoot/agent.ps1" -WindowStyle Hidden
Start-Sleep -Seconds 2
Get-Content $LogFile -Tail 10 -Wait
