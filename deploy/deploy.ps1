$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Server = "root@47.120.41.143"
$Package = Join-Path $Root "jlao-release.tar.gz"
$Temp = Join-Path $Root ".release"
$OpenSshDir = Join-Path $env:WINDIR "System32\OpenSSH"
$Scp = Join-Path $OpenSshDir "scp.exe"
$Ssh = Join-Path $OpenSshDir "ssh.exe"

if (-not (Test-Path $Scp)) {
  throw "scp.exe not found at $Scp"
}
if (-not (Test-Path $Ssh)) {
  throw "ssh.exe not found at $Ssh"
}

Write-Host "[JLAO] Building frontend..." -ForegroundColor Cyan
Push-Location (Join-Path $Root "frontend")
$env:VITE_API_BASE = "https://jlao.szkakayiduo.com"
npm.cmd run build
Pop-Location

Write-Host "[JLAO] Preparing release package..." -ForegroundColor Cyan
if (Test-Path $Temp) {
  Remove-Item -LiteralPath $Temp -Recurse -Force
}
New-Item -ItemType Directory -Path $Temp | Out-Null
New-Item -ItemType Directory -Path (Join-Path $Temp "frontend-dist") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $Temp "backend") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $Temp "data") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $Temp "models") | Out-Null

Copy-Item -Path (Join-Path $Root "backend\app") -Destination (Join-Path $Temp "backend\app") -Recurse
Copy-Item -Path (Join-Path $Root "backend\requirements.txt") -Destination (Join-Path $Temp "backend\requirements.txt")
Copy-Item -Path (Join-Path $Root "data\samples") -Destination (Join-Path $Temp "data\samples") -Recurse
Copy-Item -Path (Join-Path $Root "frontend\dist\*") -Destination (Join-Path $Temp "frontend-dist") -Recurse
Copy-Item -Path (Join-Path $Root "deploy") -Destination (Join-Path $Temp "deploy") -Recurse
Copy-Item -Path (Join-Path $Root "models\jade-yolo.pt") -Destination (Join-Path $Temp "models\jade-yolo.pt")

if (Test-Path $Package) {
  Remove-Item -LiteralPath $Package -Force
}

Push-Location $Temp
try {
  $WinTar = "C:\Windows\System32\tar.exe"
  if (Test-Path $WinTar) {
    & $WinTar -czf $Package .
  } else {
    & tar.exe -czf $Package .
  }
  if ($LASTEXITCODE -ne 0) {
    throw "tar failed with exit code $LASTEXITCODE"
  }
} finally {
  Pop-Location
}

if (-not (Test-Path $Package)) {
  throw "Release package was not created at $Package"
}

Write-Host "[JLAO] Uploading package to server..." -ForegroundColor Cyan
& $Scp -o StrictHostKeyChecking=accept-new $Package "${Server}:/tmp/jlao-release.tar.gz"
if ($LASTEXITCODE -ne 0) {
  throw "scp failed with exit code $LASTEXITCODE"
}

Write-Host "[JLAO] Installing on server..." -ForegroundColor Cyan
& $Ssh -o StrictHostKeyChecking=accept-new $Server "rm -rf /tmp/jlao-release && mkdir -p /tmp/jlao-release && tar -xzf /tmp/jlao-release.tar.gz -C /tmp/jlao-release && bash /tmp/jlao-release/deploy/server-install.sh"

Write-Host "[JLAO] Deployment finished: https://jlao.szkakayiduo.com" -ForegroundColor Green
