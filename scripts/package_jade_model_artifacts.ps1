param(
  [string]$Output = "models\jade-yolo-artifacts.zip",
  [switch]$RequireModel
)

$ErrorActionPreference = "Stop"

$artifacts = @(
  "models\jade-yolo.pt",
  "models\jade-yolo-card.md",
  "data\jade_yolo\dataset.yaml",
  "data\jade_yolo_class_reference.csv",
  "data\jade_eval_baseline.json",
  "data\jade_eval_after_train.json",
  "data\jade_eval_comparison.json",
  "data\jade_eval_summary.md",
  "data\jade_eval_mistakes.csv",
  "docs\jade_multimodal_training.md"
)

if ($RequireModel -and -not (Test-Path -LiteralPath "models\jade-yolo.pt")) {
  throw "Required model not found: models\jade-yolo.pt"
}

$existing = @()
foreach ($artifact in $artifacts) {
  if (Test-Path -LiteralPath $artifact) {
    $existing += $artifact
  }
}

if ($existing.Count -eq 0) {
  throw "No jade model artifacts found to package."
}

$outputPath = Resolve-Path -LiteralPath "." | ForEach-Object { Join-Path $_.Path $Output }
$outputDir = Split-Path -Parent $outputPath
if (-not (Test-Path -LiteralPath $outputDir)) {
  New-Item -ItemType Directory -Path $outputDir | Out-Null
}

if (Test-Path -LiteralPath $outputPath) {
  Remove-Item -LiteralPath $outputPath -Force
}

$stagingRoot = Join-Path $outputDir ".jade-package-staging"
if (Test-Path -LiteralPath $stagingRoot) {
  Remove-Item -LiteralPath $stagingRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $stagingRoot | Out-Null

foreach ($artifact in $existing) {
  $target = Join-Path $stagingRoot $artifact
  $targetDir = Split-Path -Parent $target
  if (-not (Test-Path -LiteralPath $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
  }
  Copy-Item -LiteralPath $artifact -Destination $target -Force
}

Compress-Archive -Path (Join-Path $stagingRoot "*") -DestinationPath $outputPath -Force
Remove-Item -LiteralPath $stagingRoot -Recurse -Force

Write-Host "Packaged $($existing.Count) artifacts:" -ForegroundColor Green
foreach ($artifact in $existing) {
  Write-Host " - $artifact"
}
Write-Host "Output: $outputPath" -ForegroundColor Cyan
