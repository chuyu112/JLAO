param(
  [Parameter(Mandatory = $true)]
  [string]$ImageDir,
  [Parameter(Mandatory = $true)]
  [string]$Output,
  [switch]$Recursive,
  [string]$RelativeTo = "",
  [string]$BatchId = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $root "scripts\create_jade_labeling_manifest.py"
$argsList = @($script, "--image-dir", $ImageDir, "--output", $Output)

if ($Recursive) {
  $argsList += "--recursive"
}
if ($RelativeTo) {
  $argsList += @("--relative-to", $RelativeTo)
}
if ($BatchId) {
  $argsList += @("--batch-id", $BatchId)
}

python @argsList
