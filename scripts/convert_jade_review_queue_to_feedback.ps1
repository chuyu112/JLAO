param(
  [Parameter(Mandatory = $true)]
  [string]$ReviewQueue,
  [Parameter(Mandatory = $true)]
  [string]$Output,
  [switch]$RequireComplete,
  [string]$Source = "review_queue",
  [switch]$PrettySummary
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $root "scripts\convert_jade_review_queue_to_feedback.py"
$argsList = @(
  $script,
  "--review-queue", $ReviewQueue,
  "--output", $Output,
  "--source", $Source
)

if ($RequireComplete) {
  $argsList += "--require-complete"
}
if ($PrettySummary) {
  $argsList += "--pretty-summary"
}

python @argsList
