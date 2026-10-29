# Starts the Antigravity proxy + bridge at Windows logon via pm2 (always-on PC setup).
# FreeLLMAPI itself: install the desktop .exe and enable "Start at login" in its tray menu.
#
#   powershell -ExecutionPolicy Bypass -File deploy\windows\install-autostart.ps1
#   powershell -ExecutionPolicy Bypass -File deploy\windows\install-autostart.ps1 -Remove

param([switch]$Remove)

$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$taskName = 'FreeLLMStack-pm2'

if ($Remove) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed scheduled task $taskName"
    return
}

foreach ($cmd in 'node', 'npm') {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { throw "$cmd not found: install Node.js 20+ first" }
}
if (-not (Get-Command pm2 -ErrorAction SilentlyContinue)) { npm install -g pm2 }
if (-not (Get-Command antigravity-claude-proxy -ErrorAction SilentlyContinue)) { npm install -g antigravity-claude-proxy@2.9.1 }

$ecosystem = Join-Path $root 'deploy\pm2\ecosystem.config.cjs'
pm2 start $ecosystem
pm2 save

$pm2 = (Get-Command pm2).Source
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -WindowStyle Hidden -Command `"& '$pm2' resurrect`""
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description 'Resurrect pm2 apps (antigravity proxy + bridge) at logon' -Force | Out-Null

Write-Host "OK: proxy + bridge run under pm2 and restart at logon (task '$taskName')."
Write-Host "Check: pm2 ls   |   logs: pm2 logs"
