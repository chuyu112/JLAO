param(
  [Parameter(Mandatory = $true, Position = 0)]
  [ValidateSet(
    "status",
    "static",
    "check",
    "plan",
    "create-manifest",
    "class-reference",
    "analyze",
    "dry-run-import",
    "import",
    "export-feedback",
    "train",
    "train-feedback",
    "train-batch-feedback",
    "evaluate",
    "predict-manifest",
    "predictions-to-manifest",
    "merge-predictions",
    "select-review-samples",
    "review-queue-to-manifest",
    "batch-feedback",
    "compare",
    "summary",
    "export-mistakes",
    "review-manifest",
    "merge-manifests",
    "model-card",
    "package",
    "check-package"
  )]
  [string]$Action,

  [string]$Python = ".\backend\.venv-local\Scripts\python.exe",
  [string]$Manifest = "",
  [string]$SecondaryManifest = "data\jade_review_manifest.csv",
  [string]$Image = "",
  [string]$ImageDir = "",
  [string]$Text = "",
  [string]$TextFile = "",
  [string]$Output = "",
  [switch]$IncludeRows,
  [switch]$ExportMistakes,
  [switch]$PackageArtifacts,
  [switch]$RunStaticCheck,
  [switch]$SkipTrain,
  [switch]$WholeImageBox,
  [int]$Offset = 0,
  [int]$Limit = 120,
  [double]$ConfidenceThreshold = 0.45,
  [string]$BatchId = "",
  [switch]$Pretty
)

$ErrorActionPreference = "Stop"

function Invoke-Python {
  param([string[]]$CommandArgs)
  if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python not found: $Python"
  }
  & $Python @CommandArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Command failed with exit code $LASTEXITCODE"
  }
}

function Require-Manifest {
  if (-not $Manifest) {
    throw "-Manifest is required for action '$Action'"
  }
}

switch ($Action) {
  "status" {
    $cmdArgs = @("scripts/jade_pipeline_status.py")
    if ($Pretty) { $cmdArgs += "--pretty" }
    Invoke-Python $cmdArgs
  }
  "static" {
    & powershell -ExecutionPolicy Bypass -File "scripts\check_jade_pipeline_static.ps1" -Python $Python
    if ($LASTEXITCODE -ne 0) { throw "Static check failed with exit code $LASTEXITCODE" }
  }
  "check" {
    Require-Manifest
    $cmdArgs = @("scripts/check_jade_manifest.py", "--manifest", $Manifest)
    if ($Pretty) { $cmdArgs += "--pretty" }
    Invoke-Python $cmdArgs
  }
  "plan" {
    Require-Manifest
    $cmdArgs = @("scripts/plan_jade_sample_collection.py", "--manifest", $Manifest)
    if ($Pretty) { $cmdArgs += "--pretty" }
    Invoke-Python $cmdArgs
  }
  "create-manifest" {
    if (-not $ImageDir) { throw "-ImageDir is required for create-manifest" }
    if (-not $Output) { throw "-Output is required for create-manifest" }
    Invoke-Python @("scripts/create_jade_manifest_from_images.py", "--image-dir", $ImageDir, "--output", $Output, "--recursive", "--whole-image-box")
  }
  "class-reference" {
    $cmdArgs = @("scripts/generate_jade_yolo_class_reference.py")
    if ($Output) { $cmdArgs += @("--output", $Output) }
    Invoke-Python $cmdArgs
  }
  "analyze" {
    $cmdArgs = @("scripts/analyze_jade_sample.py")
    if ($Image) { $cmdArgs += @("--image", $Image) }
    if ($Text) { $cmdArgs += @("--text", $Text) }
    if ($TextFile) { $cmdArgs += @("--text-file", $TextFile) }
    if ($Output) { $cmdArgs += @("--output", $Output) }
    if ($Pretty) { $cmdArgs += "--pretty" }
    Invoke-Python $cmdArgs
  }
  "dry-run-import" {
    Require-Manifest
    Invoke-Python @(
      "scripts/import_jade_feedback_samples.py",
      "--manifest", $Manifest,
      "--dry-run",
      "--build-dataset",
      "--auto-val"
    )
  }
  "import" {
    Require-Manifest
    Invoke-Python @(
      "scripts/import_jade_feedback_samples.py",
      "--manifest", $Manifest,
      "--build-dataset",
      "--auto-val"
    )
  }
  "export-feedback" {
    $cmdArgs = @("scripts/export_jade_feedback_manifest.py")
    if ($Output) { $cmdArgs += @("--output", $Output) }
    if ($BatchId) { $cmdArgs += @("--batch-id", $BatchId) }
    Invoke-Python $cmdArgs
  }
  "train" {
    Require-Manifest
    $cmdArgs = @("-ExecutionPolicy", "Bypass", "-File", "scripts\run_jade_training_pipeline.ps1", "-Manifest", $Manifest, "-Python", $Python)
    if ($IncludeRows) { $cmdArgs += "-IncludeRows" }
    if ($ExportMistakes) { $cmdArgs += "-ExportMistakes" }
    if ($PackageArtifacts) { $cmdArgs += "-PackageArtifacts" }
    if ($RunStaticCheck) { $cmdArgs += "-RunStaticCheck" }
    if ($SkipTrain) { $cmdArgs += "-SkipTrain" }
    & powershell @cmdArgs
    if ($LASTEXITCODE -ne 0) { throw "Training pipeline failed with exit code $LASTEXITCODE" }
  }
  "train-feedback" {
    $cmdArgs = @("-ExecutionPolicy", "Bypass", "-File", "scripts\run_jade_feedback_training_pipeline.ps1", "-Python", $Python)
    if ($IncludeRows) { $cmdArgs += "-IncludeRows" }
    if ($ExportMistakes) { $cmdArgs += "-ExportMistakes" }
    if ($PackageArtifacts) { $cmdArgs += "-PackageArtifacts" }
    if ($RunStaticCheck) { $cmdArgs += "-RunStaticCheck" }
    if ($SkipTrain) { $cmdArgs += "-SkipTrain" }
    & powershell @cmdArgs
    if ($LASTEXITCODE -ne 0) { throw "Feedback training pipeline failed with exit code $LASTEXITCODE" }
  }
  "train-batch-feedback" {
    if (-not $BatchId) { throw "-BatchId is required for train-batch-feedback" }
    $safeBatchId = $BatchId -replace '[^A-Za-z0-9_.-]', '-'
    $batchManifest = if ($Output) { $Output } else { "data\jade_feedback_manifest_$safeBatchId.csv" }
    Write-Host "BatchId: $BatchId"
    Write-Host "Batch manifest: $batchManifest"
    Invoke-Python @(
      "scripts/export_jade_feedback_manifest.py",
      "--batch-id", $BatchId,
      "--output", $batchManifest
    )
    $cmdArgs = @("-ExecutionPolicy", "Bypass", "-File", "scripts\run_jade_training_pipeline.ps1", "-Manifest", $batchManifest, "-Python", $Python)
    if ($IncludeRows) { $cmdArgs += "-IncludeRows" }
    if ($ExportMistakes) { $cmdArgs += "-ExportMistakes" }
    if ($PackageArtifacts) { $cmdArgs += "-PackageArtifacts" }
    if ($RunStaticCheck) { $cmdArgs += "-RunStaticCheck" }
    if ($SkipTrain) { $cmdArgs += "-SkipTrain" }
    & powershell @cmdArgs
    if ($LASTEXITCODE -ne 0) { throw "Batch feedback training pipeline failed with exit code $LASTEXITCODE" }
  }
  "evaluate" {
    Require-Manifest
    $cmdArgs = @("scripts/evaluate_jade_manifest.py", "--manifest", $Manifest, "--mode", "all")
    if ($IncludeRows) { $cmdArgs += "--include-rows" }
    if ($Pretty) { $cmdArgs += "--pretty" }
    Invoke-Python $cmdArgs
  }
  "predict-manifest" {
    Require-Manifest
    $cmdArgs = @("scripts/predict_jade_manifest.py", "--manifest", $Manifest)
    if ($Output) { $cmdArgs += @("--output", $Output) }
    if ($Offset -gt 0) { $cmdArgs += @("--offset", "$Offset") }
    if ($PSBoundParameters.ContainsKey("Limit")) { $cmdArgs += @("--limit", "$Limit") }
    if ($BatchId) { $cmdArgs += @("--batch-id", $BatchId) }
    if ($Pretty) { $cmdArgs += "--pretty" }
    Invoke-Python $cmdArgs
  }
  "predictions-to-manifest" {
    Require-Manifest
    $cmdArgs = @("scripts/create_jade_manifest_from_predictions.py", "--predictions", $Manifest)
    if ($Output) { $cmdArgs += @("--output", $Output) }
    if ($WholeImageBox) { $cmdArgs += "--whole-image-box" }
    Invoke-Python $cmdArgs
  }
  "merge-predictions" {
    Require-Manifest
    if (-not $SecondaryManifest) { throw "-SecondaryManifest is required for merge-predictions" }
    $extraManifests = $SecondaryManifest -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    $cmdArgs = @("scripts/merge_jade_prediction_csvs.py", "--input", $Manifest) + $extraManifests
    if ($Output) { $cmdArgs += @("--output", $Output) }
    Invoke-Python $cmdArgs
  }
  "select-review-samples" {
    Require-Manifest
    $cmdArgs = @(
      "scripts/select_jade_review_samples.py",
      "--predictions", $Manifest,
      "--confidence-threshold", "$ConfidenceThreshold",
      "--limit", "$Limit"
    )
    if ($Output) { $cmdArgs += @("--output", $Output) }
    Invoke-Python $cmdArgs
  }
  "review-queue-to-manifest" {
    Require-Manifest
    $cmdArgs = @("scripts/create_jade_manifest_from_review_queue.py", "--queue", $Manifest)
    if ($Output) { $cmdArgs += @("--output", $Output) }
    if ($WholeImageBox) { $cmdArgs += "--whole-image-box" }
    Invoke-Python $cmdArgs
  }
  "batch-feedback" {
    if (-not $BatchId) { throw "-BatchId is required for batch-feedback" }
    $cmdArgs = @("scripts/summarize_jade_batch_feedback.py", "--batch-id", $BatchId)
    if ($Output) { $cmdArgs += @("--output", $Output) }
    if ($Pretty) { $cmdArgs += "--pretty" }
    Invoke-Python $cmdArgs
  }
  "compare" {
    $cmdArgs = @("scripts/compare_jade_eval_reports.py")
    if ($Pretty) { $cmdArgs += "--pretty" }
    Invoke-Python $cmdArgs
  }
  "summary" {
    $cmdArgs = @("scripts/summarize_jade_eval_reports.py")
    if ($Output) { $cmdArgs += @("--output", $Output) }
    Invoke-Python $cmdArgs
  }
  "export-mistakes" {
    $cmdArgs = @("scripts/export_jade_eval_mistakes.py")
    if ($Output) { $cmdArgs += @("--output", $Output) }
    Invoke-Python $cmdArgs
  }
  "review-manifest" {
    $cmdArgs = @("scripts/create_jade_review_manifest_from_mistakes.py")
    if ($Output) { $cmdArgs += @("--output", $Output) }
    Invoke-Python $cmdArgs
  }
  "merge-manifests" {
    Require-Manifest
    if (-not $Output) { throw "-Output is required for merge-manifests" }
    Invoke-Python @(
      "scripts/merge_jade_manifests.py",
      "--input", $Manifest, $SecondaryManifest,
      "--output", $Output
    )
  }
  "model-card" {
    $cmdArgs = @("scripts/create_jade_model_card.py")
    if ($Output) { $cmdArgs += @("--output", $Output) }
    Invoke-Python $cmdArgs
  }
  "package" {
    $cmdArgs = @("-ExecutionPolicy", "Bypass", "-File", "scripts\package_jade_model_artifacts.ps1", "-RequireModel")
    if ($Output) { $cmdArgs += @("-Output", $Output) }
    & powershell @cmdArgs
    if ($LASTEXITCODE -ne 0) { throw "Package failed with exit code $LASTEXITCODE" }
  }
  "check-package" {
    $cmdArgs = @("scripts/check_jade_artifact_package.py")
    if ($Output) { $cmdArgs += @("--package", $Output) }
    if ($Pretty) { $cmdArgs += "--pretty" }
    Invoke-Python $cmdArgs
  }
}
