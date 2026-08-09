param([Parameter(Mandatory=$true)][string]$OutputZip)
$ErrorActionPreference="Stop"
$root=(Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if((git -C $root status --porcelain)){throw "Package only from a clean committed worktree"}
$commit=(git -C $root rev-parse HEAD).Trim();$branch=(git -C $root branch --show-current).Trim()
$temp=Join-Path ([System.IO.Path]::GetTempPath()) ("bitcoin-intelligence-"+[guid]::NewGuid().ToString("N"));New-Item -ItemType Directory -Path $temp|Out-Null
try{
  $tar=Join-Path $temp "source.tar";git -C $root archive --format=tar -o $tar HEAD;tar -xf $tar -C $temp;Remove-Item -LiteralPath $tar
  New-Item -ItemType Directory -Force -Path (Join-Path $temp "database")|Out-Null
  foreach($db in @("bitcoin.db","external_metrics.db")){Copy-Item -LiteralPath (Join-Path $root "database\$db") -Destination (Join-Path $temp "database\$db")}
  $master=Get-Content -LiteralPath (Join-Path $root "frozen\master_3_0_frozen.json") -Raw|ConvertFrom-Json;$reference=Get-Content -LiteralPath (Join-Path $root "frozen\best_entry_reference_set_v1.json") -Raw|ConvertFrom-Json
  $version=[ordered]@{local_commit=$commit;branch=$branch;master_version="MASTER-3.0";config_hash="db4b6ed6e40fd9f6ce7efe4b0748c61dee83ddcf0603962eb836eeafa8e3ee5f";master_hash=$master.master_code_hash;reference_set=$reference.reference_set;reference_hash=$reference.factor_matrix_sha256;deployment_timestamp=$null;package_created_at=(Get-Date).ToUniversalTime().ToString("o");github="NOT_CONFIGURED";execution="DISABLED"}|ConvertTo-Json
  [System.IO.File]::WriteAllText((Join-Path $temp "DEPLOYED_VERSION.json"),$version,(New-Object System.Text.UTF8Encoding($false)))
  $target=[System.IO.Path]::GetFullPath($OutputZip);$parent=Split-Path $target -Parent;if(-not (Test-Path $parent)){New-Item -ItemType Directory -Force -Path $parent|Out-Null};if(Test-Path $target){throw "Output already exists: $target"};Compress-Archive -Path (Join-Path $temp "*") -DestinationPath $target -CompressionLevel Optimal
  $hash=(Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash;Write-Output "PACKAGE=$target";Write-Output "SHA256=$hash";Write-Output "COMMIT=$commit"
}finally{if(Test-Path $temp){Remove-Item -LiteralPath $temp -Recurse -Force}}
