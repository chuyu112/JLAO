param(
    [string]$Python = "python",
    [switch]$Pretty
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Runner = Join-Path $Root "scripts\check_jade_recognition_offline_gates.py"

$argsList = @($Runner, "--python", $Python)
if ($Pretty) {
    $argsList += "--pretty"
}

& $Python @argsList
exit $LASTEXITCODE
