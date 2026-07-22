param(
    [string]$HostName = "narit-pi",
    [string]$RemoteDir = "/home/admin/NaritVending",
    [switch]$NoPull
)

$ErrorActionPreference = "Stop"

ssh $HostName "mkdir -p $RemoteDir"

# Pull the latest machine and hardware configuration from the Pi so web-saved
# motor, slot, GPIO, and sensor settings survive future deployments.
if (-not $NoPull) {
    foreach ($configFile in @("machine_config.json", "hardware_config.json")) {
        try {
            $fileExists = ssh $HostName "if [ -f ${RemoteDir}/${configFile} ]; then echo 'yes'; fi"
            if ($fileExists.Trim() -eq "yes") {
                scp "${HostName}:${RemoteDir}/${configFile}" "./${configFile}"
                Write-Host "Pulled latest ${configFile} from Pi to preserve controller configuration."
            }
        } catch {
            Write-Warning "Could not pull ${configFile} from Pi. Proceeding with local configuration."
        }
    }
}

ssh $HostName "sudo systemctl stop narit-vending-web.service 2>/dev/null || true; sudo chown -R admin:admin $RemoteDir 2>/dev/null || true; find $RemoteDir -type d -exec chmod u+rwx {} +; find $RemoteDir -type f -exec chmod u+rw {} +"
scp -r README.md main.py machine_config.json hardware_config.json requirements.txt narit_vending deploy scripts "Test motor.py" "${HostName}:${RemoteDir}/"
if ($LASTEXITCODE -ne 0) {
    throw "SCP upload failed with exit code $LASTEXITCODE"
}
ssh $HostName "cd $RemoteDir && chmod +x scripts/setup_pi.sh && ./scripts/setup_pi.sh"

Write-Host "Deployment completed to ${HostName}:$RemoteDir"
