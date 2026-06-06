param(
  [Parameter(Mandatory = $true)]
  [string]$Manifest,
  [int]$MinLabeled = 1,
  [int]$MinDistinctPerAttribute = 1,
  [switch]$Pretty
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $root "scripts\check_jade_label_distribution.py"
$argsList = @(
  $script,
  "--manifest", $Manifest,
  "--min-labeled", $MinLabeled,
  "--min-distinct-per-attribute", $MinDistinctPerAttribute
)

if ($Pretty) {
  $argsList += "--pretty"
}

python @argsList
