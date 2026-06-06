param(
  [Parameter(Mandatory = $true)]
  [string]$Input,
  [switch]$RequirePresent,
  [switch]$Pretty
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $root "scripts\check_jade_taxonomy_values.py"
$argsList = @($script, "--input", $Input)

if ($RequirePresent) {
  $argsList += "--require-present"
}
if ($Pretty) {
  $argsList += "--pretty"
}

python @argsList
