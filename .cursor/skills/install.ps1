# Links curated agency-agents skills from the user-wide install into this repo.
$ErrorActionPreference = "Stop"

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$manifestPath = Join-Path $here "agency-manifest.json"
if (-not (Test-Path $manifestPath)) {
    throw "Missing manifest: $manifestPath"
}

$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
$userSkills = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath(
    $manifest.source.Replace("%USERPROFILE%", $env:USERPROFILE)
)

if (-not (Test-Path $userSkills)) {
    throw @"
User-wide agency skills not found at:
  $userSkills

Install agency-agents user-wide first (see %USERPROFILE%\.cursor\AGENCY-AGENTS.md).
"@
}

$linked = 0
$skipped = 0
foreach ($slug in $manifest.skills) {
    $src = Join-Path $userSkills $slug
    $dest = Join-Path $here $slug
    if (-not (Test-Path $src)) {
        Write-Warning "Skip missing skill: $slug"
        $skipped++
        continue
    }
    if (Test-Path $dest) {
        $item = Get-Item $dest -Force
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            $skipped++
            continue
        }
        Remove-Item $dest -Recurse -Force
    }
    cmd /c mklink /J "$dest" "$src" | Out-Null
    Write-Host "Linked $slug"
    $linked++
}

Write-Host "Done. Linked $linked skill(s), skipped $skipped."
