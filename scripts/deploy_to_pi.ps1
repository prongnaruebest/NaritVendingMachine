param(
    [string]$HostName = "narit-pi",
    [string]$RemoteDir = "/home/admin/NaritVendingMOCKUP",
    [switch]$NoPull,
    [switch]$WebOnly
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

# HMI-only releases must not interrupt the controller process: it owns the
# cabinet's single MQTT connection and publishes a retained offline presence
# during a controlled stop.  Copy only browser assets and restart the web
# process so MQTT stays continuously connected.
if ($WebOnly) {
    scp -r narit_vending/static narit_vending/templates "${HostName}:${RemoteDir}/narit_vending/"
    if ($LASTEXITCODE -ne 0) {
        throw "Web asset upload failed with exit code $LASTEXITCODE"
    }
    ssh $HostName "sudo systemctl restart narit-vending-web.service; sudo systemctl is-active --quiet narit-vending-web.service"
    if ($LASTEXITCODE -ne 0) {
        throw "Web service did not become active after deployment"
    }
    Write-Host "Web-only deployment completed to ${HostName}:$RemoteDir (controller/MQTT left running)"
    return
}

ssh $HostName "sudo systemctl stop narit-vending-web.service narit-vending-controller.service 2>/dev/null || true; sudo chown -R admin:admin $RemoteDir 2>/dev/null || true; find $RemoteDir -type d -exec chmod u+rwx {} +; find $RemoteDir -type f -exec chmod u+rw {} +"
scp -r README.md main.py machine_config.json hardware_config.json requirements.txt narit_vending deploy scripts "${HostName}:${RemoteDir}/"
if ($LASTEXITCODE -ne 0) {
    throw "SCP upload failed with exit code $LASTEXITCODE"
}
ssh $HostName "cd $RemoteDir && chmod +x scripts/setup_pi.sh && ./scripts/setup_pi.sh"

Write-Host "Deployment completed to ${HostName}:$RemoteDir"
