param(
  [Parameter(Mandatory = $true)]
  [string]$Predictions,
  [Parameter(Mandatory = $true)]
  [string]$Output,
  [switch]$IncludeMissingExpected
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $root "scripts\create_jade_error_review_queue.py"
$argsList = @($script, "--predictions", $Predictions, "--output", $Output)

if ($IncludeMissingExpected) {
  $argsList += "--include-missing-expected"
}

python @argsList
