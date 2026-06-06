param(
  [Parameter(Mandatory = $true)]
  [string]$Predictions,
  [int]$MaxExamples = 20,
  [switch]$Pretty
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $root "scripts\summarize_jade_prediction_errors.py"
$argsList = @($script, "--predictions", $Predictions, "--max-examples", $MaxExamples)

if ($Pretty) {
  $argsList += "--pretty"
}

python @argsList
