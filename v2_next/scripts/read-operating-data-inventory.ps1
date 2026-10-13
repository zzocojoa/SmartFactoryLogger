param([string]$BundlePath='', [string]$ExpectedScopeSha256='', [string]$VerifiedHelperSha256='')
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

function Convert-SFLInventoryPath([string]$Path) {
    $native=$Path.Replace('/','\')
    if($native -notmatch '^(?:[A-Za-z]:\\|\\\\[^\\]+\\[^\\]+(?:\\|$))'){throw 'Inventory root must be absolute'}
    $full=[IO.Path]::GetFullPath($native)
    if($full.Length -gt 240){throw 'Unsupported inventory path'}
    $volume=[IO.Path]::GetPathRoot($full)
    if($full.TrimEnd('\') -ieq $volume.TrimEnd('\')){return $volume}
    return $full.TrimEnd('\')
}

function Assert-SFLPlainPath([string]$Path) {
    $full=Convert-SFLInventoryPath $Path
    $root=[IO.Path]::GetPathRoot($full)
    $current=$full
    while($current.Length -ge $root.TrimEnd('\').Length){
        $attributes=[IO.File]::GetAttributes($current)
        if(($attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){throw 'Reparse path is not followed'}
        if($current.TrimEnd('\') -ieq $root.TrimEnd('\')){break}
        $current=[IO.Path]::GetDirectoryName($current)
    }
    return $full
}

function Get-SFLInventoryKind([string]$Name) {
    if($Name -ieq 'spot_image_fact.csv'){return 'image_fact'}
    if($Name -ieq 'spot_observation_fact.csv'){return 'observation_fact'}
    if($Name -like '*.metadata.json'){return 'csv_metadata'}
    if($Name -like '*.csv'){return 'csv'}
    if($Name -match '\.(jpg|jpeg|png|gif|bmp|webp)$'){return 'image'}
    if($Name -match 'manifest.*\.json$'){return 'manifest'}
    if($Name -match '(operator|attestation|approval|owner|responsib)'){return 'owner_or_profile_record_candidate'}
    if($Name -match '(receipt|shutdown).*\.json$'){return 'receipt_or_shutdown_record'}
    if($Name -match '\.(ini|bak)$'){return 'settings_or_backup'}
    if($Name -match '\.(zip|7z|tar|gz)$'){return 'archive_not_expanded'}
    if($Name -match '\.(exe|dll|pyd|asar)$'){return 'runtime_or_installer'}
    if($Name -like '*.lnk'){return 'shortcut_not_followed'}
    return 'other_unclassified_for_data_qa'
}

function Read-SFLDataInventory {
    param([object[]]$Roots, [scriptblock]$OnEntry, [string]$ExcludedRoot='', [int]$MaxSeconds=900)
    $clock=[Diagnostics.Stopwatch]::StartNew()
    $seen=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $covered=[Collections.Generic.List[string]]::new()
    $ledger=[Collections.Generic.List[object]]::new()
    $counts=@{}
    $outputError=$null
    $rowsEmitted=0
    $totals=[ordered]@{file_count=0;directory_count=0;reparse_count=0;error_count=0;apparent_file_bytes=[long]0;excluded_current_bundle=0;budget_exhausted=$false}
    foreach($root in $Roots){
        $row=[ordered]@{id=[string]$root.id;path=[string]$root.path;recursive=[bool]$root.recursive;state='METADATA_ONLY';errors=@()}
        $ledger.Add($row)
        if($null -ne $outputError){$row.state='NOT_SCANNED_AFTER_OUTPUT_ERROR';continue}
        try{$rootPath=Convert-SFLInventoryPath ([string]$root.path);$row.path=$rootPath}
        catch{$row.state='UNSUPPORTED_ROOT';$row.errors+=@($_.Exception.Message);$totals.error_count++;continue}
        $overlap=$false
        foreach($previous in $covered){if($rootPath -ieq $previous -or $rootPath.StartsWith($previous.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)){$overlap=$true;break}}
        if($overlap){$row.state='COVERED_BY_PREVIOUS_RECURSIVE_ROOT';continue}
        if(-not [IO.Directory]::Exists($rootPath)){$row.state='ABSENT_OR_UNREADABLE';$totals.error_count++;continue}
        $pending=[Collections.Generic.Stack[string]]::new();$pending.Push($rootPath)
        while($pending.Count -gt 0 -and $null -eq $outputError){
            if($clock.Elapsed.TotalSeconds -gt $MaxSeconds){$totals.budget_exhausted=$true;$row.state='PARTIAL_TIME_BUDGET';break}
            $directory=$pending.Pop()
            if($ExcludedRoot -and ($directory -ieq $ExcludedRoot -or $directory.StartsWith($ExcludedRoot.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase))){$totals.excluded_current_bundle++;continue}
            try{
                [void](Assert-SFLPlainPath $directory)
                foreach($path in [IO.Directory]::EnumerateFileSystemEntries($directory)){
                    if($clock.Elapsed.TotalSeconds -gt $MaxSeconds){$totals.budget_exhausted=$true;$row.state='PARTIAL_TIME_BUDGET';break}
                    if($ExcludedRoot -and ($path -ieq $ExcludedRoot -or $path.StartsWith($ExcludedRoot.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase))){$totals.excluded_current_bundle++;continue}
                    if(-not $seen.Add($path)){continue}
                    $entry=[ordered]@{root_id=$root.id;path=$path;kind='unknown';bytes=$null;last_write_utc=$null;state='METADATA_ONLY';sha256=$null}
                    try{
                        if($path.Length -gt 240){throw 'Path exceeds tested PS5.1 path budget'}
                        $attrs=[IO.File]::GetAttributes($path)
                        if(($attrs -band [IO.FileAttributes]::ReparsePoint) -ne 0){$entry.kind='reparse_not_followed';$entry.state='REPARSE_SKIPPED';$totals.reparse_count++}
                        elseif(($attrs -band [IO.FileAttributes]::Directory) -ne 0){
                            $entry.kind='directory';$totals.directory_count++
                            if($root.recursive){$pending.Push($path)}
                        }else{
                            $info=[IO.FileInfo]::new($path)
                            $entry.bytes=$info.Length;$entry.last_write_utc=$info.LastWriteTimeUtc.ToString('o')
                            $entry.kind=Get-SFLInventoryKind $info.Name
                            $totals.file_count++;$totals.apparent_file_bytes+=$info.Length
                            if(-not $counts.ContainsKey($entry.kind)){$counts[$entry.kind]=0};$counts[$entry.kind]++
                        }
                    }catch{$entry.state='METADATA_ERROR';$entry.error=$_.Exception.Message;$totals.error_count++}
                    try{$null=& $OnEntry ([pscustomobject]$entry);$rowsEmitted++}
                    catch{$outputError=$_.Exception.Message;$row.state='PARTIAL_OUTPUT_ERROR';$totals.error_count++;break}
                }
            }catch{$row.state='PARTIAL_ENUMERATION_ERROR';$row.errors+=@([pscustomobject]@{path=$directory;error=$_.Exception.Message});$totals.error_count++}
        }
        if($row.recursive -and $row.state -ceq 'METADATA_ONLY'){$covered.Add($rootPath)}
    }
    return [pscustomobject]@{
        file_count=$totals.file_count;directory_count=$totals.directory_count;reparse_count=$totals.reparse_count
        error_count=$totals.error_count;apparent_file_bytes=$totals.apparent_file_bytes;kind_counts=$counts;rows_emitted=$rowsEmitted
        root_ledger=@($ledger.ToArray());budget_exhausted=$totals.budget_exhausted;excluded_current_bundle=$totals.excluded_current_bundle;output_error=$outputError
        elapsed_seconds=$clock.Elapsed.TotalSeconds;full_data_gate='NOT_EVALUATED';atomic_snapshot=$false
        all_source_hashes_measured=$false;archives_expanded=$false;scope_complete=$false
    }
}

function New-SFLInventorySecurity([string]$OperatorSid){
    $acl=[Security.AccessControl.DirectorySecurity]::new();$acl.SetAccessRuleProtection($true,$false)
    $acl.SetOwner([Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))
    foreach($sid in @('S-1-5-32-544','S-1-5-18')){
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($sid),'FullControl','ContainerInherit,ObjectInherit','None','Allow'))
    }
    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($OperatorSid),'ReadAndExecute','ContainerInherit,ObjectInherit','None','Allow'))
    return $acl
}

function Test-SFLInventoryAccessRules([Security.AccessControl.DirectorySecurity]$Actual,[Security.AccessControl.DirectorySecurity]$Expected){
    if(-not $Actual.AreAccessRulesProtected){return $false}
    $actualRows=@($Actual.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])|ForEach-Object {
        '{0}|{1}|{2}|{3}|{4}|{5}' -f $_.IdentityReference.Value,[int]$_.FileSystemRights,[int]$_.InheritanceFlags,[int]$_.PropagationFlags,[int]$_.AccessControlType,$_.IsInherited
    }|Sort-Object)
    $expectedRows=@($Expected.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])|ForEach-Object {
        '{0}|{1}|{2}|{3}|{4}|{5}' -f $_.IdentityReference.Value,[int]$_.FileSystemRights,[int]$_.InheritanceFlags,[int]$_.PropagationFlags,[int]$_.AccessControlType,$_.IsInherited
    }|Sort-Object)
    return (($actualRows -join "`n") -ceq ($expectedRows -join "`n"))
}

function Write-SFLNewJson([string]$Path,[object]$Value){
    $bytes=[Text.UTF8Encoding]::new($false).GetBytes(($Value|ConvertTo-Json -Depth 12))
    $stream=[IO.File]::Open($Path,'CreateNew','Write','Read')
    try{$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
}

function Assert-SFLInventorySource([object]$Health,[object]$Scope){
    if(-not $Health.running -or $Health.mode -cne 'REAL' -or $Health.app_version -cne $Scope.expected_app_version){throw 'Expected live operating backend is not running'}
    $loggerId=$Health.spot_temperature.v2_4_operational.logger_service_instance_id
    if($loggerId -cne $Scope.expected_logger_service_instance_id){throw 'Operating logger instance changed or this is a different PC'}
}

if($MyInvocation.InvocationName -eq '.'){return}
if($PSVersionTable.PSEdition -cne 'Desktop' -or $PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1){throw 'Native Windows PowerShell 5.1 is required'}
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not ([Security.Principal.WindowsPrincipal]::new($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Administrator PowerShell is required only to protect the new result folder'}
if($identity.Name.Split('\')[-1] -ine 'user' -or $env:APPDATA -ine 'C:\Users\user\AppData\Roaming'){throw 'Unexpected operating user/profile'}
if($VerifiedHelperSha256 -notmatch '^[a-f0-9]{64}$' -or $ExpectedScopeSha256 -notmatch '^[a-f0-9]{64}$'){throw 'Use the fixed-hash launcher'}
$bundle=Assert-SFLPlainPath $BundlePath
$desktop=[Environment]::GetFolderPath([Environment+SpecialFolder]::Desktop)
$base=[IO.Path]::GetFullPath((Join-Path $desktop 'SmartFactory')).TrimEnd('\')
if(-not $bundle.StartsWith($base+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Bundle is outside the actual Desktop SmartFactory folder'}
$scopePath=Join-Path $bundle 'scope.json';[void](Assert-SFLPlainPath $scopePath)
$scopePin=[IO.File]::Open($scopePath,'Open','Read','Read')
try{
    if($scopePin.Length -gt 65536){throw 'Scope file exceeds size contract'}
    $sha=[Security.Cryptography.SHA256]::Create()
    try{$scopeHash=([BitConverter]::ToString($sha.ComputeHash($scopePin))).Replace('-','').ToLowerInvariant()}finally{$sha.Dispose()}
    if($scopeHash -cne $ExpectedScopeSha256){throw 'Scope SHA256 mismatch'}
    $scopePin.Position=0;$reader=[IO.StreamReader]::new($scopePin,[Text.Encoding]::UTF8,$true,4096,$true)
    try{$scope=$reader.ReadToEnd()|ConvertFrom-Json}finally{$reader.Dispose()}
    if($scope.operation -cne 'metadata_inventory_only'){throw 'Unsupported operation'}
    $basisPins=[Collections.Generic.List[IO.FileStream]]::new()
    foreach($basis in $scope.basis_files){
        $basisPath=[IO.Path]::GetFullPath((Join-Path $bundle $basis.path))
        if(-not $basisPath.StartsWith($bundle.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Basis path escapes bundle'}
        [void](Assert-SFLPlainPath $basisPath)
        $pin=[IO.File]::Open($basisPath,'Open','Read','Read');$basisPins.Add($pin)
        $hash=[Security.Cryptography.SHA256]::Create()
        try{$actualBasis=([BitConverter]::ToString($hash.ComputeHash($pin))).Replace('-','').ToLowerInvariant()}finally{$hash.Dispose()}
        if($actualBasis -cne $basis.sha256){throw 'Basis SHA256 mismatch'}
    }
    $roots=@($scope.roots)
    if($roots.Count -eq 0 -or $roots.Count -gt 16){throw 'Scope root count differs'}
    $healthResponse=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 5
    $liveHealth=$healthResponse.Content|ConvertFrom-Json
    Assert-SFLInventorySource $liveHealth $scope
    $volume=[IO.DriveInfo]::new([IO.Path]::GetPathRoot($bundle))
    if($volume.AvailableFreeSpace -lt 2147483648){throw 'Less than 2GiB free before inventory; no result folder created'}
    $resultPath=Join-Path $bundle ('r-'+[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')+'-'+[Guid]::NewGuid().ToString('N').Substring(0,8))
    if(($resultPath+'\manifest-verification.json').Length -gt 240 -or [IO.Directory]::Exists($resultPath) -or [IO.File]::Exists($resultPath)){throw 'Result path is not new or exceeds budget'}
    $acl=New-SFLInventorySecurity $identity.User.Value
    [void][IO.Directory]::CreateDirectory($resultPath,$acl)
    [void](Assert-SFLPlainPath $resultPath)
    $actual=Get-Acl -LiteralPath $resultPath
    if(-not $actual.AreAccessRulesProtected -or $actual.GetOwner([Security.Principal.SecurityIdentifier]).Value -cne 'S-1-5-32-544'){throw 'New result ACL/owner differs'}
    if(-not (Test-SFLInventoryAccessRules $actual $acl)){throw 'New result access rules differ'}
    $inventoryPath=Join-Path $resultPath 'files.jsonl'
    $output=[IO.File]::Open($inventoryPath,'CreateNew','Write','Read')
    $writer=[IO.StreamWriter]::new($output,[Text.UTF8Encoding]::new($false),65536,$true)
    try{
        $callback={param($entry) $writer.WriteLine(($entry|ConvertTo-Json -Depth 5 -Compress));if($output.Position -gt 536870912){throw 'Inventory output exceeds 512MiB; incomplete metadata'}}
        $summary=Read-SFLDataInventory -Roots $roots -OnEntry $callback -ExcludedRoot $bundle
        $writer.Flush();$output.Flush($true)
    }finally{$writer.Dispose();$output.Dispose()}
    $summary|Add-Member -NotePropertyName helper_sha256 -NotePropertyValue $VerifiedHelperSha256
    $summary|Add-Member -NotePropertyName scope_sha256 -NotePropertyValue $scopeHash
    $summary|Add-Member -NotePropertyName operator_sid -NotePropertyValue $identity.User.Value
    $summary|Add-Member -NotePropertyName computer_name -NotePropertyValue $env:COMPUTERNAME
    $summary|Add-Member -NotePropertyName result_path -NotePropertyValue $resultPath
    Write-SFLNewJson (Join-Path $resultPath 'summary.json') $summary
    $manifest=@(Get-ChildItem -LiteralPath $resultPath -File|ForEach-Object {[pscustomobject]@{name=$_.Name;bytes=$_.Length;sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}})
    Write-SFLNewJson (Join-Path $resultPath 'manifest.json') $manifest
    $manifestHash=(Get-FileHash -LiteralPath (Join-Path $resultPath 'manifest.json') -Algorithm SHA256).Hash
    Write-Output ('RESULT_PATH='+$resultPath)
    Write-Output ('MANIFEST_SHA256='+$manifestHash)
    Write-Output 'FULL_DATA_GATE=NOT_EVALUATED; metadata-only, live/non-atomic; no source file content changed'
}finally{if(Get-Variable basisPins -ErrorAction SilentlyContinue){foreach($pin in $basisPins){$pin.Dispose()}};$scopePin.Dispose()}
