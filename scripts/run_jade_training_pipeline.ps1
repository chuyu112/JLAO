param(
  [Parameter(Mandatory = $true)]
  [string]$Manifest,

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

if (-not (Test-Path -LiteralPath $Manifest)) {
  throw "Manifest not found: $Manifest"
}

if ($RunStaticCheck) {
  Write-Host ""
  Write-Host "==> Run jade pipeline static checks" -ForegroundColor Cyan
  & powershell -ExecutionPolicy Bypass -File "scripts\check_jade_pipeline_static.ps1" -Python $Python
  if ($LASTEXITCODE -ne 0) {
    throw "Static checks failed with exit code $LASTEXITCODE"
  }
}

Invoke-Step "Check manifest quality" @(
  "scripts/check_jade_manifest.py",
  "--manifest", $Manifest,
  "--min-train-labels", "$MinTrainLabels",
  "--min-val-labels", "$MinValLabels",
  "--val-ratio", "$ValRatio",
  "--pretty"
)

if (-not $SkipBaseline) {
  $baselineArgs = @(
    "scripts/evaluate_jade_manifest.py",
    "--manifest", $Manifest,
    "--mode", "all",
    "--output", $BaselineOutput,
    "--pretty"
  )
  if ($IncludeRows) {
    $baselineArgs += "--include-rows"
  }
  Invoke-Step "Evaluate baseline jade multimodal recognition" $baselineArgs
}

Invoke-Step "Import feedback and build dataset" @(
  "scripts/import_jade_feedback_samples.py",
  "--manifest", $Manifest,
  "--build-dataset",
  "--auto-val",
  "--val-ratio", "$ValRatio"
)

$trainLabels = @(Get-ChildItem -LiteralPath "data\jade_yolo\labels\train" -Filter "*.txt" -ErrorAction SilentlyContinue).Count
$valLabels = @(Get-ChildItem -LiteralPath "data\jade_yolo\labels\val" -Filter "*.txt" -ErrorAction SilentlyContinue).Count

Write-Host ""
Write-Host "Dataset labels: train=$trainLabels val=$valLabels" -ForegroundColor Yellow

if ($trainLabels -lt $MinTrainLabels -or $valLabels -lt $MinValLabels) {
  throw "Not enough labels to train. Need train>=$MinTrainLabels and val>=$MinValLabels."
}

if (-not $SkipTrain) {
  Invoke-Step "Train jade YOLO" @(
    "scripts/train_jade_yolo.py",
    "--data", "data/jade_yolo/dataset.yaml",
    "--model", $Model,
    "--epochs", "$EpochS",
    "--imgsz", "$ImageSize",
    "--batch", $Batch,
    "--output", "models/jade-yolo.pt",
    "--min-train-labels", "$MinTrainLabels",
    "--min-val-labels", "$MinValLabels",
    "--write-yaml"
  )
}

$evalArgs = @(
  "scripts/evaluate_jade_manifest.py",
  "--manifest", $Manifest,
  "--mode", "all",
  "--output", $EvaluationOutput,
  "--pretty"
)
if ($IncludeRows) {
  $evalArgs += "--include-rows"
}

Invoke-Step "Evaluate jade multimodal recognition" $evalArgs

if (-not $SkipBaseline) {
  $comparisonArgs = @(
    "scripts/compare_jade_eval_reports.py",
    "--baseline", $BaselineOutput,
    "--after", $EvaluationOutput,
    "--output", $ComparisonOutput,
    "--pretty"
  )
  if ($FailOnRegression) {
    $comparisonArgs += "--fail-on-regression"
  }
  if ($MinFusedColor -ge 0) {
    $comparisonArgs += @("--min-fused-color", "$MinFusedColor")
  }
  if ($MinFusedWater -ge 0) {
    $comparisonArgs += @("--min-fused-water", "$MinFusedWater")
  }
  if ($MinFusedStyle -ge 0) {
    $comparisonArgs += @("--min-fused-style", "$MinFusedStyle")
  }
  if ($MinFusedTheme -ge 0) {
    $comparisonArgs += @("--min-fused-theme", "$MinFusedTheme")
  }
  Invoke-Step "Compare baseline and after-training reports" $comparisonArgs
}

Invoke-Step "Summarize jade evaluation reports" @(
  "scripts/summarize_jade_eval_reports.py",
  "--baseline", $BaselineOutput,
  "--after", $EvaluationOutput,
  "--comparison", $ComparisonOutput,
  "--output", $SummaryOutput
)

Invoke-Step "Create jade model card" @(
  "scripts/create_jade_model_card.py",
  "--model", "models/jade-yolo.pt",
  "--dataset", "data/jade_yolo",
  "--after", $EvaluationOutput,
  "--comparison", $ComparisonOutput,
  "--output", $ModelCardOutput
)

if ($ExportMistakes) {
  if (-not $IncludeRows) {
    throw "ExportMistakes requires IncludeRows so evaluation reports contain per-row results."
  }
  Invoke-Step "Export jade evaluation mistakes" @(
    "scripts/export_jade_eval_mistakes.py",
    "--report", $EvaluationOutput,
    "--output", $MistakesOutput,
    "--mode", "all",
    "--field", "all"
  )
}

if ($PackageArtifacts) {
  Write-Host ""
  Write-Host "==> Package jade model artifacts" -ForegroundColor Cyan
  & powershell -ExecutionPolicy Bypass -File "scripts\package_jade_model_artifacts.ps1" -Output $ArtifactsOutput -RequireModel
  if ($LASTEXITCODE -ne 0) {
    throw "Package jade model artifacts failed with exit code $LASTEXITCODE"
  }
}
