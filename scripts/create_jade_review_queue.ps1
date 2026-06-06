param(
  [Parameter(Mandatory = $true)]
  [string]$Response,
  [Parameter(Mandatory = $true)]
  [string]$Output,
  [double]$MinConfidence = 0.65,
  [switch]$IncludeAll
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $root "scripts\create_jade_review_queue.py"
$argsList = @(
  $script,
  "--response", $Response,
  "--output", $Output,
  "--min-confidence", $MinConfidence
)

if ($IncludeAll) {
  $argsList += "--include-all"
}

python @argsList
