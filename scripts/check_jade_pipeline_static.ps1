param(
  [string]$Python = ".\backend\.venv-local\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $Python)) {
  throw "Python not found: $Python"
}

$pythonScripts = @(
  "scripts/analyze_jade_sample.py",
  "scripts/build_jade_yolo_dataset_from_feedback.py",
  "scripts/check_jade_artifact_package.py",
  "scripts/check_jade_manifest.py",
  "scripts/compare_jade_eval_reports.py",
  "scripts/create_jade_model_card.py",
  "scripts/create_jade_manifest_from_images.py",
  "scripts/create_jade_manifest_from_predictions.py",
  "scripts/create_jade_manifest_from_review_queue.py",
  "scripts/create_jade_review_manifest_from_mistakes.py",
  "scripts/evaluate_jade_manifest.py",
  "scripts/export_jade_eval_mistakes.py",
  "scripts/export_jade_feedback_manifest.py",
  "scripts/generate_jade_yolo_class_reference.py",
  "scripts/import_jade_feedback_samples.py",
  "scripts/jade_pipeline_status.py",
  "scripts/merge_jade_prediction_csvs.py",
  "scripts/merge_jade_manifests.py",
  "scripts/plan_jade_sample_collection.py",
  "scripts/predict_jade_manifest.py",
  "scripts/select_jade_review_samples.py",
  "scripts/summarize_jade_batch_feedback.py",
  "scripts/summarize_jade_eval_reports.py",
  "scripts/train_jade_yolo.py"
)

$backendServiceScripts = @(
  "backend/app/services/jade_batch_feedback_summary_service.py",
  "backend/app/services/jade_batch_trace_service.py",
  "backend/app/services/jade_review_flags_service.py"
)

$pythonScripts = $pythonScripts + $backendServiceScripts

$powerShellScripts = @(
  "scripts/jade.ps1",
  "scripts/package_jade_model_artifacts.ps1",
  "scripts/run_jade_feedback_training_pipeline.ps1",
  "scripts/run_jade_training_pipeline.ps1"
)

Write-Host "==> Python syntax check" -ForegroundColor Cyan
foreach ($script in $pythonScripts) {
  if (-not (Test-Path -LiteralPath $script)) {
    throw "Missing script: $script"
  }
  & $Python -m py_compile $script
  if ($LASTEXITCODE -ne 0) {
    throw "Python syntax check failed: $script"
  }
  Write-Host "ok $script"
}

Write-Host ""
Write-Host "==> PowerShell syntax check" -ForegroundColor Cyan
foreach ($script in $powerShellScripts) {
  if (-not (Test-Path -LiteralPath $script)) {
    throw "Missing script: $script"
  }
  $tokens = $null
  $errors = $null
  [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path -LiteralPath $script), [ref]$tokens, [ref]$errors) | Out-Null
  if ($errors.Count -gt 0) {
    $details = ($errors | ForEach-Object { "$($_.Extent.StartLineNumber): $($_.Message)" }) -join "`n"
    throw "PowerShell syntax check failed: $script`n$details"
  }
  Write-Host "ok $script"
}

Write-Host ""
Write-Host "Jade training pipeline static checks passed." -ForegroundColor Green
