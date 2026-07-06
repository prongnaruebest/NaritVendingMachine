param(
    [string]$HostName = "narit-pi",
    [string]$RemoteDir = "/home/admin/NaritVending"
)

$path = Resolve-Path "."
Write-Host "Watching for file changes in $path..."
Write-Host "Auto-deploying to ${HostName}:${RemoteDir} on save."
Write-Host "Press Ctrl+C to stop."

$watcher = New-Object System.IO.FileSystemWatcher
$watcher.Path = $path
$watcher.IncludeSubdirectories = $true
$watcher.Filter = "*.*"
$watcher.EnableRaisingEvents = $true

# Track last change timestamp to prevent duplicate triggers
$lastRun = [DateTime]::MinValue

$action = {
    $filePath = $Event.SourceEventArgs.FullPath
    $changeType = $Event.SourceEventArgs.ChangeType
    
    # Ignore git, vs, pycache, .venv and log/temporary files
    if ($filePath -notmatch "\\\.git" -and 
        $filePath -notmatch "\\\.vs" -and 
        $filePath -notmatch "__pycache__" -and 
        $filePath -notmatch "\\\.venv" -and 
        $filePath -notmatch "\\\.codex" -and
        $filePath -notmatch "\\\.system_generated" -and
        $filePath -notmatch "walkthrough\.md") {
        
        # Debounce event (FileSystemWatcher sometimes triggers multiple times for a single save)
        $now = [DateTime]::Now
        if ($now.Subtract($lastRun).TotalMilliseconds -gt 1000) {
            global:__lastRun = $now
            Write-Host ""
            Write-Host "File changed: $filePath ($changeType)" -ForegroundColor Cyan
            Write-Host "Running deploy_to_pi.ps1..." -ForegroundColor Yellow
            try {
                & "$PSScriptRoot/deploy_to_pi.ps1" -HostName $HostName -RemoteDir $RemoteDir -NoPull
            } catch {
                Write-Error "Deployment failed: $_"
            }
        }
    }
}

$changedEvent = Register-ObjectEvent $watcher "Changed" -Action $action

try {
    while ($true) {
        Start-Sleep -Seconds 1
    }
}
finally {
    Unregister-Event -SourceIdentifier $changedEvent.Name
    $watcher.Dispose()
    Write-Host "Watcher stopped."
}
