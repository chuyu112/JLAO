param(
  [Parameter(Mandatory = $true)]
  [string[]]$Report,
  [switch]$Pretty
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $root "scripts\summarize_jade_gate_reports.py"
$argsList = @($script)

foreach ($item in $Report) {
  $argsList += @("--report", $item)
}
if ($Pretty) {
  $argsList += "--pretty"
}

python @argsList
