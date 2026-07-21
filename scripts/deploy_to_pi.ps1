param(
    [string]$HostName = "narit-pi",
    [string]$RemoteDir = "/home/admin/NaritVending",
    [switch]$NoPull
)

$ErrorActionPreference = "Stop"

ssh $HostName "mkdir -p $RemoteDir"

# Try to pull the latest machine_config.json from the Pi to preserve slot settings
if (-not $NoPull) {
    try {
        $fileExists = ssh $HostName "if [ -f ${RemoteDir}/machine_config.json ]; then echo 'yes'; fi"
        if ($fileExists.Trim() -eq "yes") {
            scp "${HostName}:${RemoteDir}/machine_config.json" ./machine_config.json
            Write-Host "Pulled latest machine_config.json from Pi to preserve slot configurations."
        }
    } catch {
        Write-Warning "Could not pull machine_config.json from Pi. Proceeding with local configuration."
    }
}

ssh $HostName "sudo systemctl stop narit-vending-web.service 2>/dev/null || true; sudo chown -R admin:admin $RemoteDir 2>/dev/null || true; find $RemoteDir -type d -exec chmod u+rwx {} +; find $RemoteDir -type f -exec chmod u+rw {} +"
scp -r README.md main.py machine_config.json hardware_config.json requirements.txt narit_vending deploy scripts "Test motor.py" "${HostName}:${RemoteDir}/"
if ($LASTEXITCODE -ne 0) {
    throw "SCP upload failed with exit code $LASTEXITCODE"
}
ssh $HostName "cd $RemoteDir && chmod +x scripts/setup_pi.sh && ./scripts/setup_pi.sh"

Write-Host "Deployment completed to ${HostName}:$RemoteDir"
