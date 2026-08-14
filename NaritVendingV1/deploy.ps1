param(
    [switch]$NoPull,
    [switch]$WebOnly
)

$deployArgs = @{}
if ($NoPull) { $deployArgs.NoPull = $true }
if ($WebOnly) { $deployArgs.WebOnly = $true }
& "$PSScriptRoot\..\scripts\deploy_to_iriv.ps1" @deployArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
