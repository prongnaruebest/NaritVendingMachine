param(
    [string]$HostName = "pi@iriv.local",
    [string]$RemoteDir = "/home/admin/NaritVending",
    [switch]$NoPull,
    [switch]$WebOnly
)

$ErrorActionPreference = "Stop"
$ControllerService = "narit-vending-controller-iriv.service"
$WebService = "narit-vending-web-iriv.service"
$StageDir = "/tmp/narit-vending-iriv-deploy"

ssh $HostName "mkdir -p '$RemoteDir'"
if ($LASTEXITCODE -ne 0) { throw "Cannot connect to $HostName over SSH" }

# Only IRIV-specific configuration is synchronised.  The legacy Pi files and
# scripts/deploy_to_pi.ps1 are intentionally untouched.
if (-not $NoPull) {
    foreach ($configFile in @("machine_config.iriv.json", "hardware_config.iriv.json")) {
        $fileExists = ssh $HostName "if [ -f '$RemoteDir/$configFile' ]; then echo yes; fi"
        if ($fileExists.Trim() -eq "yes") {
            scp "${HostName}:${RemoteDir}/${configFile}" "./${configFile}"
            if ($LASTEXITCODE -ne 0) { throw "Failed to preserve remote $configFile" }
            Write-Host "Pulled latest $configFile from IRIV Pi."
        }
    }
}

if ($WebOnly) {
    ssh $HostName "sudo rm -rf '$StageDir' && mkdir -p '$StageDir/narit_vending'"
    scp -r narit_vending/static narit_vending/templates "${HostName}:${StageDir}/narit_vending/"
    if ($LASTEXITCODE -ne 0) { throw "Web asset upload failed" }
    ssh $HostName "sudo cp -a '$StageDir/narit_vending/.' '$RemoteDir/narit_vending/' && sudo rm -rf '$StageDir' && sudo systemctl restart '$WebService' && sudo systemctl is-active --quiet '$WebService'"
    if ($LASTEXITCODE -ne 0) { throw "IRIV web service did not become active" }
    Write-Host "IRIV web-only deployment completed."
    return
}

ssh $HostName "sudo systemctl stop '$WebService' '$ControllerService' 2>/dev/null || true; sudo chown -R admin:admin '$RemoteDir' 2>/dev/null || true"
ssh $HostName "sudo rm -rf '$StageDir' && mkdir -p '$StageDir'"
scp -r README.md main.py requirements.txt machine_config.iriv.json hardware_config.iriv.json narit_vending deploy scripts "${HostName}:${StageDir}/"
if ($LASTEXITCODE -ne 0) { throw "IRIV upload failed" }

$remoteInstall = @"
set -eu
sudo cp -a '$StageDir/.' '$RemoteDir/'
sudo rm -rf '$StageDir'
cd '$RemoteDir'
test -x .venv/bin/python3 || { echo 'Missing .venv; install the existing project runtime first.' >&2; exit 1; }
.venv/bin/python3 scripts/validate_config.py --machine machine_config.iriv.json --hardware hardware_config.iriv.json
sudo install -m 0644 deploy/narit-vending-controller-iriv.service /etc/systemd/system/$ControllerService
sudo install -m 0644 deploy/narit-vending-web-iriv.service /etc/systemd/system/$WebService
sudo systemctl daemon-reload
sudo systemctl disable --now narit-vending-web.service narit-vending-controller.service 2>/dev/null || true
sudo systemctl enable --now '$ControllerService' '$WebService'
sudo systemctl is-active --quiet '$ControllerService'
sudo systemctl is-active --quiet '$WebService'
for _ in 1 2 3 4 5 6 7 8 9 10; do
    curl --fail --silent --max-time 2 http://127.0.0.1/health/live >/dev/null && break
    sleep 1
done
curl --fail --silent --show-error --max-time 5 http://127.0.0.1/health/live >/dev/null
curl --fail --silent --show-error --max-time 5 http://127.0.0.1/health/ready >/dev/null
"@
ssh $HostName $remoteInstall
if ($LASTEXITCODE -ne 0) { throw "IRIV service installation or readiness check failed" }

Write-Host "IRIV deployment completed to ${HostName}:$RemoteDir"
