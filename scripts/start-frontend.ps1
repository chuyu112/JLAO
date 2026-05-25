$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Frontend = Join-Path $Root "frontend"

Set-Location $Frontend
npm.cmd run dev -- --host 127.0.0.1

