param([string]$InstallRoot="C:\BitcoinIntelligence")
$ErrorActionPreference="Stop"
$roots=@("C:\","C:\Users\","C:\MeanPulse AI\","C:\MeanPulse News\","C:\BitcoinIntelligence\","C:\Projects\")
$paths=foreach($path in $roots){[ordered]@{path=$path;exists=Test-Path -LiteralPath $path;item_count=if(Test-Path -LiteralPath $path){@(Get-ChildItem -LiteralPath $path -Force -ErrorAction SilentlyContinue).Count}else{0}}}
$tasks=Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object {$_.TaskName -match "Bitcoin|MeanPulse"} | Select-Object TaskName,State
$processes=Get-CimInstance Win32_Process | Where-Object {$_.Name -match "python|streamlit|MeanPulse|terminal64"} | Select-Object ProcessId,Name,ExecutablePath
$drives=Get-CimInstance Win32_LogicalDisk | Select-Object DeviceID,Size,FreeSpace
$python=Get-Command python -ErrorAction SilentlyContinue
$payload=[ordered]@{computer=$env:COMPUTERNAME;windows=(Get-CimInstance Win32_OperatingSystem).Caption;python=if($python){& $python.Source --version}else{"UNAVAILABLE"};memory_bytes=(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory;drives=$drives;paths=$paths;target_exists=Test-Path -LiteralPath $InstallRoot;target_owned=Test-Path -LiteralPath (Join-Path $InstallRoot ".bitcoin-intelligence-owned");tasks=$tasks;processes=$processes;inventory_only=$true}
$payload|ConvertTo-Json -Depth 6
