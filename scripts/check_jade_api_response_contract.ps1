param(
  [Parameter(Mandatory = $true)]
  [string]$Response,
  [switch]$RequireAllAttributes,
  [switch]$Pretty
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $root "scripts\check_jade_api_response_contract.py"
$argsList = @($script, "--response", $Response)

if ($RequireAllAttributes) {
  $argsList += "--require-all-attributes"
}
if ($Pretty) {
  $argsList += "--pretty"
}

python @argsList
