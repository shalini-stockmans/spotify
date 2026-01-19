# PowerShell script to set up Windows Task Scheduler for Spotify sync
# Run this script as Administrator: Right-click PowerShell > Run as Administrator

$taskName = "SpotifySync"
$scriptPath = Join-Path $PSScriptRoot "sync_spotify.bat"

# Remove existing task if it exists
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

# Create the action (what to run)
$action = New-ScheduledTaskAction -Execute $scriptPath -WorkingDirectory $PSScriptRoot

# Create the trigger (when to run - every hour)
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Days 365)

# Create the principal (who runs it - current user)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive

# Settings
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Register the task
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description "Sync Spotify listening history every hour"

Write-Host "Task '$taskName' has been created successfully!" -ForegroundColor Green
Write-Host "The sync will run every hour." -ForegroundColor Green
Write-Host ""
Write-Host "To manage the task:" -ForegroundColor Yellow
Write-Host "  - View: Task Scheduler > Task Scheduler Library > $taskName" -ForegroundColor Yellow
Write-Host "  - Run manually: Right-click task > Run" -ForegroundColor Yellow
Write-Host "  - Delete: Run this script again or delete from Task Scheduler" -ForegroundColor Yellow
