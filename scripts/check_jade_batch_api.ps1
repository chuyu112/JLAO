param(
    [string[]]$Image = @(),
    [string]$Manifest = "",
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$Text = "",
    [string]$Python = "python",
    [switch]$RequireAllAttributes,
    [switch]$Pretty
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Script = Join-Path $Root "scripts\check_jade_batch_api.py"

$argsList = @($Script, "--base-url", $BaseUrl)
foreach ($item in $Image) {
    $resolved = if ([System.IO.Path]::IsPathRooted($item)) { $item } else { Join-Path $Root $item }
    $argsList += @("--image", $resolved)
}
if ($Manifest) {
    $resolvedManifest = if ([System.IO.Path]::IsPathRooted($Manifest)) { $Manifest } else { Join-Path $Root $Manifest }
    $argsList += @("--manifest", $resolvedManifest)
}
if ($Text) {
    $argsList += @("--text", $Text)
}
if ($RequireAllAttributes) {
    $argsList += "--require-all-attributes"
}
if ($Pretty) {
    $argsList += "--pretty"
}

& $Python @argsList
exit $LASTEXITCODE
