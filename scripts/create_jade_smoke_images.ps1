param(
    [string]$Python = "python",
    [string]$OutputDir = "data\generated_jade_smoke_images",
    [string]$Manifest = "data\generated_jade_smoke_manifest.csv",
    [switch]$Pretty
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Script = Join-Path $Root "scripts\create_jade_smoke_images.py"
$ResolvedOutputDir = if ([System.IO.Path]::IsPathRooted($OutputDir)) { $OutputDir } else { Join-Path $Root $OutputDir }
$ResolvedManifest = if ([System.IO.Path]::IsPathRooted($Manifest)) { $Manifest } else { Join-Path $Root $Manifest }

$argsList = @($Script, "--output-dir", $ResolvedOutputDir, "--manifest", $ResolvedManifest)
if ($Pretty) {
    $argsList += "--pretty"
}

& $Python @argsList
exit $LASTEXITCODE
