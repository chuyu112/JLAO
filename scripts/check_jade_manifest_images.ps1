param(
  [Parameter(Mandatory = $true)]
  [string]$Manifest,
  [string]$BaseDir = "",
  [switch]$Pretty
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $root "scripts\check_jade_manifest_images.py"
$argsList = @($script, "--manifest", $Manifest)

if ($BaseDir) {
  $argsList += @("--base-dir", $BaseDir)
}
if ($Pretty) {
  $argsList += "--pretty"
}

python @argsList
