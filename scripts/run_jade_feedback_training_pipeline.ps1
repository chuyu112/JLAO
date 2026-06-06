param(
  [string]$Feedback = "data\jade_feedback.jsonl",
  [string]$Manifest = "data\jade_feedback_manifest.csv",
  [string]$Python = ".\backend\.venv-local\Scripts\python.exe",
  [string]$Model = "yolo11n.pt",
  [int]$EpochS = 50,
  [int]$ImageSize = 640,
  [string]$Batch = "auto",
  [double]$ValRatio = 0.2,
  [int]$MinTrainLabels = 10,
  [int]$MinValLabels = 2,
  [string]$BaselineOutput = "data\jade_eval_baseline.json",
  [string]$EvaluationOutput = "data\jade_eval_after_train.json",
  [string]$ComparisonOutput = "data\jade_eval_comparison.json",
  [string]$SummaryOutput = "data\jade_eval_summary.md",
  [string]$ModelCardOutput = "models\jade-yolo-card.md",
  [string]$MistakesOutput = "data\jade_eval_mistakes.csv",
  [string]$ArtifactsOutput = "models\jade-yolo-artifacts.zip",
  [switch]$FailOnRegression,
  [double]$MinFusedColor = -1,
  [double]$MinFusedWater = -1,
  [double]$MinFusedStyle = -1,
  [double]$MinFusedTheme = -1,
  [switch]$IncludePending,
  [switch]$ExportMistakes,
  [switch]$PackageArtifacts,
  [switch]$RunStaticCheck,
  [switch]$SkipBaseline,
  [switch]$SkipTrain,
  [switch]$IncludeRows
)

$ErrorActionPreference = "Stop"

function Invoke-Step {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Name,
    [Parameter(Mandatory = $true)]
    [string[]]$Args
  )

  Write-Host ""
  Write-Host "==> $Name" -ForegroundColor Cyan
  & $Python @Args
  if ($LASTEXITCODE -ne 0) {
    throw "$Name failed with exit code $LASTEXITCODE"
  }
}

if (-not (Test-Path -LiteralPath $Python)) {
  throw "Python not found: $Python"
}

if (-not (Test-Path -LiteralPath $Feedback)) {
  throw "Feedback file not found: $Feedback"
}

$exportArgs = @(
  "scripts/export_jade_feedback_manifest.py",
  "--feedback", $Feedback,
  "--output", $Manifest
)
if ($IncludePending) {
  $exportArgs += "--include-pending"
}

Invoke-Step "Export jade feedback manifest" $exportArgs

$pipelineArgs = @(
  "-ExecutionPolicy", "Bypass",
  "-File", "scripts\run_jade_training_pipeline.ps1",
  "-Manifest", $Manifest,
  "-Python", $Python,
  "-Model", $Model,
  "-EpochS", "$EpochS",
  "-ImageSize", "$ImageSize",
  "-Batch", $Batch,
  "-ValRatio", "$ValRatio",
  "-MinTrainLabels", "$MinTrainLabels",
  "-MinValLabels", "$MinValLabels",
  "-BaselineOutput", $BaselineOutput,
  "-EvaluationOutput", $EvaluationOutput,
  "-ComparisonOutput", $ComparisonOutput,
  "-SummaryOutput", $SummaryOutput,
  "-ModelCardOutput", $ModelCardOutput,
  "-MistakesOutput", $MistakesOutput,
  "-ArtifactsOutput", $ArtifactsOutput
)
if ($ExportMistakes) {
  $pipelineArgs += "-ExportMistakes"
}
if ($PackageArtifacts) {
  $pipelineArgs += "-PackageArtifacts"
}
if ($RunStaticCheck) {
  $pipelineArgs += "-RunStaticCheck"
}
if ($FailOnRegression) {
  $pipelineArgs += "-FailOnRegression"
}
if ($MinFusedColor -ge 0) {
  $pipelineArgs += @("-MinFusedColor", "$MinFusedColor")
}
if ($MinFusedWater -ge 0) {
  $pipelineArgs += @("-MinFusedWater", "$MinFusedWater")
}
if ($MinFusedStyle -ge 0) {
  $pipelineArgs += @("-MinFusedStyle", "$MinFusedStyle")
}
if ($MinFusedTheme -ge 0) {
  $pipelineArgs += @("-MinFusedTheme", "$MinFusedTheme")
}
if ($SkipBaseline) {
  $pipelineArgs += "-SkipBaseline"
}
if ($SkipTrain) {
  $pipelineArgs += "-SkipTrain"
}
if ($IncludeRows) {
  $pipelineArgs += "-IncludeRows"
}

Write-Host ""
Write-Host "==> Run jade training pipeline from exported feedback" -ForegroundColor Cyan
& powershell @pipelineArgs
if ($LASTEXITCODE -ne 0) {
  throw "Training pipeline failed with exit code $LASTEXITCODE"
}
