param(
    [switch]$NoPull,
    [switch]$WebOnly
)

$deployArgs = @{}
if ($NoPull) { $deployArgs.NoPull = $true }
if ($WebOnly) { $deployArgs.WebOnly = $true }
Push-Location $PSScriptRoot
try {
    & "$PSScriptRoot\scripts\deploy_to_pi.ps1" @deployArgs
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}
