param(
  [Parameter(Mandatory = $true)]
  [string]$Manifest,
  [Parameter(Mandatory = $true)]
  [string]$Output,
  [string]$Prompt = "",
  [switch]$AllowIncomplete,
  [switch]$PrettySummary
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $root "scripts\create_jade_vlm_training_jsonl.py"
$argsList = @($script, "--manifest", $Manifest, "--output", $Output)

if ($Prompt) {
  $argsList += @("--prompt", $Prompt)
}
if ($AllowIncomplete) {
  $argsList += "--allow-incomplete"
}
if ($PrettySummary) {
  $argsList += "--pretty-summary"
}

python @argsList
