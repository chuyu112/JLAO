param(
    [string]$Python = "python",
    [string]$Examples = "data\jade_recognition_examples.jsonl",
    [switch]$Pretty
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Script = Join-Path $Root "scripts\check_jade_recognition_examples.py"
$ResolvedExamples = if ([System.IO.Path]::IsPathRooted($Examples)) { $Examples } else { Join-Path $Root $Examples }

$argsList = @($Script, "--examples", $ResolvedExamples)
if ($Pretty) {
    $argsList += "--pretty"
}

& $Python @argsList
exit $LASTEXITCODE
