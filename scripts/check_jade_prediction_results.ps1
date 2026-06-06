param(
    [Parameter(Mandatory = $true)]
    [string]$Predictions,
    [string]$Python = "python",
    [double]$MinCoverage = 0.80,
    [double]$MinAccuracy = 0.0,
    [switch]$Pretty
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Script = Join-Path $Root "scripts\check_jade_prediction_results.py"
$ResolvedPredictions = if ([System.IO.Path]::IsPathRooted($Predictions)) { $Predictions } else { Join-Path $Root $Predictions }

$argsList = @(
    $Script,
    "--predictions",
    $ResolvedPredictions,
    "--min-coverage",
    $MinCoverage,
    "--min-accuracy",
    $MinAccuracy
)
if ($Pretty) {
    $argsList += "--pretty"
}

& $Python @argsList
exit $LASTEXITCODE
