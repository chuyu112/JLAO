Write-Host "Stopping JLAO Lark Agent..."
Stop-Process -Name powershell -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*agent.ps1*" }
Stop-Process -Name lark-cli -ErrorAction SilentlyContinue
Write-Host "Done."
