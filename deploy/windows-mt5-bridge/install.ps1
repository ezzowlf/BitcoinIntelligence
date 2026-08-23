$ErrorActionPreference = "Stop"
$StartScript = (Resolve-Path (Join-Path $PSScriptRoot "start.ps1")).Path
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$StartScript`""
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet -RestartCount 20 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName "WAVERUN-AllInOne" -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Force
