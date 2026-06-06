param(
  [Parameter(Mandatory = $true)]
  [string]$Train,
  [Parameter(Mandatory = $true)]
  [string]$Eval,
  [switch]$Pretty
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $root "scripts\check_jade_split_integrity.py"
$argsList = @($script, "--train", $Train, "--eval", $Eval)

if ($Pretty) {
  $argsList += "--pretty"
}

python @argsList
