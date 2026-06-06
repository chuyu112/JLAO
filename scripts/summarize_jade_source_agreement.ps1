param(
  [Parameter(Mandatory = $true)]
  [string]$Response,
  [int]$MaxExamples = 20,
  [switch]$Pretty
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $root "scripts\summarize_jade_source_agreement.py"
$argsList = @($script, "--response", $Response, "--max-examples", $MaxExamples)

if ($Pretty) {
  $argsList += "--pretty"
}

python @argsList
