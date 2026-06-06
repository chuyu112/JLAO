param(
  [Parameter(Mandatory = $true)]
  [string]$Manifest,
  [Parameter(Mandatory = $true)]
  [string]$TrainOutput,
  [Parameter(Mandatory = $true)]
  [string]$EvalOutput,
  [double]$EvalRatio = 0.2,
  [string]$Salt = "jade-v1",
  [switch]$RequireComplete,
  [switch]$PrettySummary
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $root "scripts\split_jade_manifest.py"
$argsList = @(
  $script,
  "--manifest", $Manifest,
  "--train-output", $TrainOutput,
  "--eval-output", $EvalOutput,
  "--eval-ratio", $EvalRatio,
  "--salt", $Salt
)

if ($RequireComplete) {
  $argsList += "--require-complete"
}
if ($PrettySummary) {
  $argsList += "--pretty-summary"
}

python @argsList
