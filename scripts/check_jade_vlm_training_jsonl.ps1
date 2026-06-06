param(
  [Parameter(Mandatory = $true)]
  [string]$Input,
  [switch]$AllowIncomplete,
  [switch]$Pretty
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $root "scripts\check_jade_vlm_training_jsonl.py"
$argsList = @($script, "--input", $Input)

if ($AllowIncomplete) {
  $argsList += "--allow-incomplete"
}
if ($Pretty) {
  $argsList += "--pretty"
}

python @argsList
