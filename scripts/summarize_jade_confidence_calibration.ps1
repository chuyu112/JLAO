param(
  [Parameter(Mandatory = $true)]
  [string]$Predictions,
  [double]$BucketSize = 0.1,
  [switch]$Pretty
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $root "scripts\summarize_jade_confidence_calibration.py"
$argsList = @($script, "--predictions", $Predictions, "--bucket-size", $BucketSize)

if ($Pretty) {
  $argsList += "--pretty"
}

python @argsList
