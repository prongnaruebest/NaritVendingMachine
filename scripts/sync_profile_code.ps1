param()

$ErrorActionPreference = "Stop"
$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Profiles = @(
    (Join-Path $RepositoryRoot "NaritVendingMOCKUP"),
    (Join-Path $RepositoryRoot "NaritVendingV1")
)

foreach ($profile in $Profiles) {
    $resolvedParent = (Resolve-Path (Split-Path $profile -Parent)).Path
    if ($resolvedParent -ne $RepositoryRoot) {
        throw "Profile target is outside the repository: $profile"
    }
    New-Item -ItemType Directory -Force -Path $profile | Out-Null

    foreach ($directory in @("narit_vending", "deploy", "scripts", "tests")) {
        $source = Join-Path $RepositoryRoot $directory
        $target = Join-Path $profile $directory
        New-Item -ItemType Directory -Force -Path $target | Out-Null
        & robocopy $source $target /E /XD __pycache__ /XF *.pyc test_deployment_profiles.py sync_profile_code.ps1 watch_and_deploy.ps1 | Out-Null
        if ($LASTEXITCODE -gt 7) {
            throw "Failed to synchronize $directory to $profile (robocopy exit $LASTEXITCODE)"
        }
    }

    foreach ($file in @("main.py", "requirements.txt")) {
        Copy-Item -LiteralPath (Join-Path $RepositoryRoot $file) -Destination (Join-Path $profile $file) -Force
    }
}

Copy-Item -LiteralPath (Join-Path $RepositoryRoot "machine_config.json") -Destination (Join-Path $Profiles[0] "machine_config.json") -Force
Copy-Item -LiteralPath (Join-Path $RepositoryRoot "hardware_config.json") -Destination (Join-Path $Profiles[0] "hardware_config.json") -Force
Copy-Item -LiteralPath (Join-Path $RepositoryRoot "machine_config.iriv.json") -Destination (Join-Path $Profiles[1] "machine_config.iriv.json") -Force
Copy-Item -LiteralPath (Join-Path $RepositoryRoot "hardware_config.iriv.json") -Destination (Join-Path $Profiles[1] "hardware_config.iriv.json") -Force
# Compatibility fixtures keep inherited generic-GPIO tests self-contained.
# V1 runtime/deployment always selects the authoritative *.iriv.json files.
Copy-Item -LiteralPath (Join-Path $RepositoryRoot "machine_config.json") -Destination (Join-Path $Profiles[1] "machine_config.json") -Force
Copy-Item -LiteralPath (Join-Path $RepositoryRoot "hardware_config.json") -Destination (Join-Path $Profiles[1] "hardware_config.json") -Force

Write-Host "Application code synchronized into NaritVendingMOCKUP and NaritVendingV1."
