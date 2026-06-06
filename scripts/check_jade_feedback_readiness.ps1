param(
    [string]$Python = "python",
    [string]$Feedback = "data\jade_feedback.jsonl",
    [string]$BatchId = "",
    [int]$MinRecords = 1,
    [switch]$Pretty
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Script = Join-Path $Root "scripts\check_jade_feedback_readiness.py"
$ResolvedFeedback = if ([System.IO.Path]::IsPathRooted($Feedback)) { $Feedback } else { Join-Path $Root $Feedback }

$argsList = @($Script, "--feedback", $ResolvedFeedback, "--min-records", $MinRecords)
if ($BatchId) {
    $argsList += @("--batch-id", $BatchId)
}
if ($Pretty) {
    $argsList += "--pretty"
}

& $Python @argsList
exit $LASTEXITCODE
