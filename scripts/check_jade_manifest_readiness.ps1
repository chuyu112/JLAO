param(
    [Parameter(Mandatory = $true)]
    [string]$Manifest,
    [string]$Python = "python",
    [switch]$AllowMissingImages,
    [switch]$Pretty
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Script = Join-Path $Root "scripts\check_jade_manifest_readiness.py"
$ResolvedManifest = if ([System.IO.Path]::IsPathRooted($Manifest)) { $Manifest } else { Join-Path $Root $Manifest }

$argsList = @($Script, "--manifest", $ResolvedManifest)
if ($AllowMissingImages) {
    $argsList += "--allow-missing-images"
}
if ($Pretty) {
    $argsList += "--pretty"
}

& $Python @argsList
exit $LASTEXITCODE
