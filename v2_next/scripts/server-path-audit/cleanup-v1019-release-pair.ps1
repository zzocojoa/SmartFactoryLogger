[CmdletBinding()]
param([switch]$Execute)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

function Get-ReleasePairPlan {
    param([object]$Manifest,[string]$DeleteTop,[string]$KeepTop)
    foreach($top in @($DeleteTop,$KeepTop)) {Assert-QRelative $top;if($top.Contains('\')){throw 'Pair root must be one top-level name.'}}
    if($DeleteTop -ieq $KeepTop){throw 'Source and retained copy cannot be the same root.'}
    $left=@{};$right=@{}
    foreach($row in $Manifest.files){
        foreach($pair in @(@($DeleteTop,$left),@($KeepTop,$right))){
            if($row.relative_path.StartsWith($pair[0]+'\',[StringComparison]::Ordinal)){
                $suffix=$row.relative_path.Substring($pair[0].Length+1);Assert-QRelative $suffix
                if($pair[1].ContainsKey($suffix)){throw 'Repeated pair suffix.'}
                $pair[1][$suffix]=$row
            }
        }
    }
    $deletes=[Collections.Generic.List[object]]::new();$leftUnique=@();$rightUnique=@();$bytes=0L
    foreach($suffix in @($left.Keys|Sort-Object)){
        $a=$left[$suffix]
        if(-not $right.ContainsKey($suffix)){$leftUnique+=,$a;continue}
        $b=$right[$suffix]
        if($b.relative_path.Substring($KeepTop.Length+1) -cne $suffix -or $a.length -ne $b.length -or $a.sha256 -cne $b.sha256){
            throw 'Same-name pair differs; do not broaden deletion.'
        }
        $deletes.Add([pscustomobject]@{relative_path=$a.relative_path;retained_relative_path=$b.relative_path;length=$a.length;sha256=$a.sha256})
        $bytes+=$a.length
    }
    foreach($suffix in @($right.Keys|Sort-Object)){if(-not $left.ContainsKey($suffix)){$rightUnique+=,$right[$suffix]}}
    return [pscustomobject]@{delete_top=$DeleteTop;keep_top=$KeepTop;left_files=$left.Count;right_files=$right.Count;
        files=$deletes.ToArray();bytes=$bytes;left_unique=$leftUnique;right_unique=$rightUnique}
}

function Assert-ReviewedReleasePair {
    param([object]$Plan)
    if($Plan.delete_top -cne 'release_private_unsigned_v1_0_19_0c1ad4f_20260810_R1' -or
        $Plan.keep_top -cne 'release_private_unsigned_v1_0_19_0c1ad4f_20260810_R2_clean' -or
        $Plan.left_files -ne 23 -or $Plan.right_files -ne 23 -or $Plan.files.Count -ne 22 -or $Plan.bytes -ne 157989430L -or
        $Plan.left_unique.Count -ne 1 -or $Plan.right_unique.Count -ne 1){throw 'Reviewed pair count/direction differs.'}
    $a=$Plan.left_unique[0];$b=$Plan.right_unique[0]
    if($a.relative_path -cne ($Plan.delete_top+'\server_kit\server_check_before_v1019_0c1ad4f_install_20260810_075959.json') -or
        $a.length -ne 2501 -or $a.sha256 -cne 'FE9379B528432C405320DE08DBD1F37616AB4A85D0DDA70310ABAACBB6371B3F' -or
        $b.relative_path -cne ($Plan.keep_top+'\server_kit\server_check_before_v1019_0c1ad4f_install_20260810_105635.json') -or
        $b.length -ne 2342 -or $b.sha256 -cne '05FC7AA7F9550CE134B859E4399DAF9020DE89599F158F9770E5248E8D0D06B6'){
        throw 'Unique diagnostic JSON binding differs.'
    }
}

function Get-PostCleanupContract {
    param([object]$Manifest,[object[]]$Records)
    if($Records.Count -ne 218 -or $Records[0].event -cne 'PLAN' -or $Records[-1].event -cne 'COMPLETE' -or
        $Records[-1].result -cne 'VERIFIED_DUPLICATE_FOLDERS_REMOVED' -or $Records[-1].deleted_files -ne 88 -or
        $Records[-1].deleted_folders -ne 13 -or $Records[-1].deleted_bytes -ne 7658995L -or
        $Records[-1].retained_original_files -ne 470 -or $Records[0].root -cne $Manifest.quarantine_root -or
        $Records[-1].source_root -cne $Manifest.quarantine_root){throw 'First cleanup receipt is not the reviewed completion.'}
    $original=Get-QContract $Manifest;$expected=@{};$removedTops=@{};$bytes=0L
    foreach($folder in $Records[0].plan){
        Assert-QRelative $folder.top
        if($folder.top.Contains('\') -or $removedTops.ContainsKey($folder.top)){throw 'Invalid first cleanup top.'}
        $removedTops[$folder.top]=$true
        foreach($row in $folder.files){
            if(-not $original.files.ContainsKey($row.relative_path) -or $expected.ContainsKey($row.relative_path) -or
                -not $row.relative_path.StartsWith($folder.top+'\',[StringComparison]::Ordinal) -or
                $original.files[$row.relative_path].length -ne $row.length -or $original.files[$row.relative_path].sha256 -cne $row.sha256){throw 'First cleanup PLAN differs.'}
            $expected[$row.relative_path]=$row;$bytes+=$row.length
        }
    }
    $pending=@{};$deleted=@{};$dirPending=@{};$dirs=@{}
    for($i=1;$i -lt $Records.Count-1;$i++){
        $e=$Records[$i]
        switch -CaseSensitive ($e.event){
            'DELETE_INTENT' {
                $name=$e.file.relative_path
                if(-not $expected.ContainsKey($name) -or $pending.ContainsKey($name) -or $deleted.ContainsKey($name) -or
                    $e.file.sha256 -cne $expected[$name].sha256 -or $e.file.length -ne $expected[$name].length){throw 'Unbound prior delete intent.'}
                $pending[$name]=$true
            }
            'DELETED' {$name=$e.relative_path;if(-not $pending.ContainsKey($name) -or $deleted.ContainsKey($name)){throw 'Unpaired prior deletion.'};$pending.Remove($name);$deleted[$name]=$true}
            'EMPTY_DIRECTORY_INTENT' {
                $name=$e.relative_path
                if(-not $original.dirs.Contains($name) -or -not $removedTops.ContainsKey($name.Split('\')[0]) -or $dirPending.ContainsKey($name) -or $dirs.ContainsKey($name)){throw 'Unbound prior directory intent.'}
                $dirPending[$name]=$true
            }
            'EMPTY_DIRECTORY_DELETED' {$name=$e.relative_path;if(-not $dirPending.ContainsKey($name) -or $dirs.ContainsKey($name)){throw 'Unpaired prior directory deletion.'};$dirPending.Remove($name);$dirs[$name]=$true}
            default {throw 'Unexpected prior journal event.'}
        }
    }
    if($expected.Count -ne 88 -or $deleted.Count -ne 88 -or $removedTops.Count -ne 13 -or $bytes -ne 7658995L -or
        $pending.Count -ne 0 -or $dirPending.Count -ne 0 -or $dirs.Count -ne 20){throw 'Prior journal is incomplete.'}
    $remaining=@($Manifest.files|Where-Object {-not $deleted.ContainsKey($_.relative_path)})
    $m=[pscustomobject]@{top_level_items=@($Manifest.top_level_items|Where-Object {-not $removedTops.ContainsKey($_)});
        files=$remaining;file_count=470;total_bytes=1069506724L;critical_keep=$Manifest.critical_keep}
    return Get-QContract $m
}

function Invoke-ReleasePairDeletion {
    param([string]$Root,[object]$Plan,[hashtable]$ReadStreams,[hashtable]$Identities,[IO.FileStream]$Journal,
        [Collections.Generic.List[object]]$Confirmed)
    $writeIntentHandles=@{}
    try {
        # Every source is opened for deletion before the first mutation; no forced unlock.
        foreach($row in $Plan.files){
            $keepPath=Join-Path $Root $row.retained_relative_path
            Assert-CleanupChild $Root $keepPath
            $keep=$ReadStreams[$row.retained_relative_path]
            if($keep.Length -ne $row.length -or (Get-QHash $keep) -cne $row.sha256 -or
                [SflCleanupNativeV1]::Identity($keep.SafeFileHandle,$keepPath,$false) -cne $Identities[$row.retained_relative_path]){throw 'Retained copy no longer verified.'}
            [SflCleanupNativeV1]::NoAlternateStreams($keepPath,$false)
            $ReadStreams[$row.relative_path].Dispose()
            $path=Join-Path $Root $row.relative_path;Assert-CleanupChild $Root $path
            $s=[SflCleanupNativeV1]::OpenFile($path,$true);$writeIntentHandles[$row.relative_path]=$s
            if($s.Length -ne $row.length -or (Get-QHash $s) -cne $row.sha256 -or
                [SflCleanupNativeV1]::Identity($s.SafeFileHandle,$path,$false) -cne $Identities[$row.relative_path]){throw 'Delete copy changed; no deletion starts.'}
            [SflCleanupNativeV1]::NoAlternateStreams($path,$false)
        }
        foreach($row in $Plan.files){
            Remove-CleanupVerifiedFile $Root $row $Identities[$row.relative_path] $Journal $writeIntentHandles[$row.relative_path] $Confirmed
            Write-Host ('[DELETED] '+$row.relative_path)
        }
    }finally{foreach($s in $writeIntentHandles.Values){$s.Dispose()}}
}

function Assert-ReleasePairInventory {
    param([object]$Tree,[object]$Contract,[string[]]$Metadata)
    $diff=Compare-QTree $Tree $Contract $Metadata
    if(-not $Tree.complete -or $diff.missing.Count -gt 0 -or $diff.unlisted.Count -gt 0){throw 'Post-cleanup inventory changed; no deletion.'}
    $found=@{};foreach($row in $Tree.rows){$found[$row.relative]=$row}
    foreach($name in $Contract.files.Keys){if($found[$name].length -ne $Contract.files[$name].length){throw 'Retained file length changed.'}}
    foreach($name in $Contract.dirs){if(-not $found.ContainsKey($name) -or -not $found[$name].directory){throw 'Original directory missing.'}}
    foreach($name in $Metadata){if(-not $found.ContainsKey($name) -or $found[$name].directory){throw 'Historical metadata missing.'}}
}

$native=[IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
$principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if(-not [Environment]::Is64BitProcess -or $PSVersionTable.PSEdition -cne 'Desktop' -or
    $PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1 -or
    [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName -ine $native -or
    -not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Use native administrator x64 Windows PowerShell 5.1.'}
$savedPairPath=$env:PATH;$savedPairModules=$env:PSModulePath
$pins=[Collections.Generic.List[IDisposable]]::new();$guards=@{};$readStreams=@{};$ids=@{}
$confirmed=[Collections.Generic.List[object]]::new();$journal=$null;$output=''
$root='C:\Users\user\Desktop\SmartFactory_Archive\pre_v1020_quarantine_20260813_092302'
$firstReceipt='C:\ProgramData\SFLOps\inventory\q20-20260915-103611-1597b3d9\cleanup.jsonl'
$clock=[Diagnostics.Stopwatch]::StartNew()
try {
    $env:PATH=[Environment]::SystemDirectory+';'+[IO.Path]::GetDirectoryName($native)
    $env:PSModulePath=[IO.Path]::GetDirectoryName($native)+'\Modules'
    foreach($dep in @(@('read-quarantine-pre-v1020.ps1','EBEB041A42D0FC2232ADCDDA13547C8151209C22E8D85F1B1B1D70D7021A1765'),
        @('cleanup-archive-core.ps1','CD9F2387581C52FA9A26EC6E217909919F472CB5DF9853C2E96A2A368FF40A28'))){
        $s=[IO.File]::Open((Join-Path $PSScriptRoot $dep[0]),'Open','Read','Read');$pins.Add($s)
        $sha=[Security.Cryptography.SHA256]::Create();try{$actual=[BitConverter]::ToString($sha.ComputeHash($s)).Replace('-','')}finally{$sha.Dispose()}
        if($actual -cne $dep[1]){throw 'Helper dependency hash mismatch.'}
        $s.Position=0;$reader=[IO.StreamReader]::new($s,[Text.UTF8Encoding]::new($false,$true),$true,4096,$true)
        try{$text=$reader.ReadToEnd()}finally{$reader.Dispose()}
        $tokens=$null;$errors=$null;$ast=[Management.Automation.Language.Parser]::ParseInput($text,[ref]$tokens,[ref]$errors)
        if(@($errors).Count -ne 0){throw 'Helper syntax error.'}
        foreach($fn in $ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst]},$true)){. ([scriptblock]::Create($fn.Extent.Text))}
    }
    Initialize-CleanupNative
    if([IO.DriveInfo]::new('C:\').DriveFormat -cne 'NTFS'){throw 'Local NTFS required.'}
    Write-Host '[1/6] Verify original manifest and exact completed first cleanup receipt.'
    Open-CleanupDirectoryGuard $root $guards
    Open-CleanupDirectoryGuard ([IO.Path]::GetDirectoryName($firstReceipt)) $guards
    $specs=@(
        @('quarantine_manifest_before_move.json',198366L,'F918CAF4ABCC65124E86F50D2DD79DFCC962ECC221FD8E0997DB2402FE468752'),
        @('quarantine_verification_after_move.json',656L,'4CB03191D3E8816A713EA4A65D6EC03FDAC6FB94606E06B62B7F4EB1D9893D14'),
        @('quarantine_verification_after_move_R1_1.json',1628L,'4D6A6984ED3B1E2AEEEA58C9C8403FC0E3543F649EBE296E5BB2DCB671C20671'))
    $metadata=@();$manifest=$null
    foreach($spec in $specs){
        $s=Open-QPinned (Join-Path $root $spec[0]) $spec[1] $spec[2] $pins
        if($null -eq $manifest){$manifest=ConvertFrom-Json -InputObject (Read-QText $s)}
        $metadata+=@($spec[0],($spec[0]+'.sha256.txt'))
        $path=Join-Path $root ($spec[0]+'.sha256.txt');Assert-QPlain $path
        $side=[IO.File]::Open($path,'Open','Read','Read');$pins.Add($side)
        if($side.Length -gt 70 -or (Read-QText $side) -cnotmatch ('\A'+$spec[2]+'(?:\r?\n)?\z')){throw 'Historical sidecar mismatch.'}
    }
    if($manifest.quarantine_root -cne $root){throw 'Unexpected quarantine root.'}
    $receiptStream=Open-QPinned $firstReceipt 118341L '79A9C3534C2CB4DB56C865391516152582FB4A8006EE97F265889D766561EBD5' $pins
    $records=@((Read-QText $receiptStream).Split([char]10)|Where-Object {-not [string]::IsNullOrWhiteSpace($_)}|ForEach-Object {ConvertFrom-Json -InputObject $_})
    $contract=Get-PostCleanupContract $manifest $records
    $plan=Get-ReleasePairPlan $manifest 'release_private_unsigned_v1_0_19_0c1ad4f_20260810_R1' 'release_private_unsigned_v1_0_19_0c1ad4f_20260810_R2_clean'
    Assert-ReviewedReleasePair $plan
    $before=Get-QTree $root;Assert-ReleasePairInventory $before $contract $metadata
    Write-Host '[2/6] Pin and rehash BOTH copies and both unique JSONs: 46 files. No ZIP reconstruction or installer execution.'
    $pairRows=@($manifest.files|Where-Object {$_.relative_path.StartsWith($plan.delete_top+'\',[StringComparison]::Ordinal) -or $_.relative_path.StartsWith($plan.keep_top+'\',[StringComparison]::Ordinal)})
    foreach($row in $pairRows){
        if(-not $contract.files.ContainsKey($row.relative_path)){throw 'Pair intersects earlier deletion.'}
        $path=Join-Path $root $row.relative_path;Open-CleanupDirectoryGuard ([IO.Path]::GetDirectoryName($path)) $guards
        Assert-CleanupChild $root $path;$s=[SflCleanupNativeV1]::OpenFile($path,$false);$pins.Add($s)
        if($s.Length -ne $row.length -or (Get-QHash $s) -cne $row.sha256){throw 'Pair file bytes changed.'}
        [SflCleanupNativeV1]::NoAlternateStreams($path,$false)
        $readStreams[$row.relative_path]=$s;$ids[$row.relative_path]=[SflCleanupNativeV1]::Identity($s.SafeFileHandle,$path,$false)
        Write-Host ('[PAIR HASH] '+$readStreams.Count+'/46')
    }
    Write-Host '[3/6] Check bounded system, shortcut and retained-text references. No live product API queries.'
    $needles=@($plan.delete_top)
    $system=Get-QSystemReferences $needles
    if(@($system.coverage|Where-Object {$_.status -cne 'SNAPSHOT_QUERIED' -or $_.omitted_hits -gt 0}).Count -gt 0 -or $system.hits.Count -gt 0){throw 'System reference exists or query incomplete.'}
    $scopes=@(
        [pscustomobject]@{path='C:\Users\user\Desktop';depth=0;kind='shortcut'},
        [pscustomobject]@{path='C:\Users\Public\Desktop';depth=0;kind='shortcut'},
        [pscustomobject]@{path='C:\Users\user\AppData\Roaming\Microsoft\Windows\Start Menu';depth=5;kind='shortcut'},
        [pscustomobject]@{path='C:\ProgramData\Microsoft\Windows\Start Menu';depth=5;kind='shortcut'},
        [pscustomobject]@{path='C:\Users\user\Desktop\SmartFactory';depth=0;kind='text'})
    foreach($stage in @('SFL-76B317D0A2901C6EFC649404211C8109','SFL-9B645BE54EB0C6C7A7F1C482248174EB','SFL-B63483AD9AB07924E5F291076F911BDA',
        'SFL-v1023-v11-8C1B97EF0F3BA3DAC26F38CD7B8D5656','SFL26S-29aee83c36044389828d6d20eb645503','SFL26S-ae681d39b54a40c59da518292d259f95')){
        $scopes += [pscustomobject]@{path=('C:\ProgramData\'+$stage);depth=3;kind='text'}
    }
    $refs=Get-QFileReferences $needles $scopes;Assert-CleanupReferenceCoverage $refs.coverage
    if($refs.hits.Count -gt 0){$refs.hits|ConvertTo-Json -Depth 5;throw 'External retained reference to R1 exists.'}
    $deleteNames=@{};foreach($row in $plan.files){$deleteNames[$row.relative_path]=$true}
    $textBytes=0L;$textCount=0
    $uniqueNames=@($plan.left_unique[0].relative_path,$plan.right_unique[0].relative_path)
    foreach($row in @($contract.files.Values|Sort-Object relative_path)){
        if($deleteNames.ContainsKey($row.relative_path)){continue}
        $ext=[IO.Path]::GetExtension($row.relative_path).ToLowerInvariant()
        if($ext -notin @('.json','.txt','.md','.ps1','.psm1','.cmd','.bat','.ini','.before_reattestation') -and $row.relative_path -notmatch '(?i)config\.ini'){continue}
        if($row.length -gt 1MB -or $textBytes+$row.length -gt 32MB){throw 'Retained text inspection budget exceeded.'}
        $s=$null;$dispose=$false
        try{
            if($readStreams.ContainsKey($row.relative_path)){$s=$readStreams[$row.relative_path]}
            else{
                $path=Join-Path $root $row.relative_path;Assert-QPlain $path;$s=[IO.File]::Open($path,'Open','Read','Read');$dispose=$true
                if($s.Length -ne $row.length -or (Get-QHash $s) -cne $row.sha256){throw 'Retained reference file changed.'}
            }
            $textBytes+=$s.Length;$textCount++
            if(@(Find-QReferences (Read-QText $s) $needles).Count -gt 0){
                Write-Host ('[REFERENCE] '+$row.relative_path)
                throw 'Retained text references R1; preserve all pair copies pending review.'
            }
        }finally{if($dispose -and $null -ne $s){$s.Dispose()}}
        if($clock.Elapsed.TotalSeconds -gt 600){throw 'Inspection budget exceeded.'}
    }
    Write-Host '[PLAN] R1 copies only: 22 files, 157989430 bytes. Keep all 23 R2_clean files and the R1 unique JSON. Delete NO directories.'
    if(-not $Execute){[pscustomobject]@{result='RELEASE_PAIR_PLAN_ONLY';plan=$plan;deletion_performed=$false}|ConvertTo-Json -Depth 8;return}
    Write-Host '[4/6] Write a new durable plan; preserve previous receipts and all source metadata.'
    foreach($path in @('C:\ProgramData\SFLOps','C:\ProgramData\SFLOps\inventory')){New-CleanupPrivateDirectory $path;Open-CleanupDirectoryGuard $path $guards}
    $output='C:\ProgramData\SFLOps\inventory\q19-pair-'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'-'+[Guid]::NewGuid().ToString('N').Substring(0,8)
    if([IO.File]::Exists($output) -or [IO.Directory]::Exists($output)){throw 'Receipt path collision.'}
    New-CleanupPrivateDirectory $output;Open-CleanupDirectoryGuard $output $guards
    $journal=[IO.File]::Open(($output+'\cleanup.jsonl'),'CreateNew','Write','Read')
    Write-CleanupRecord $journal ([pscustomobject]@{event='PLAN';at=[DateTimeOffset]::Now.ToString('o');root=$root;plan=$plan;
        policy='fixed-v1019-R1-to-R2-clean-22-files-v1';authorization='USER_APPROVED_RELEASE_PAIR_DUPLICATE_CLEANUP';
        source_manifest_sha256=$specs[0][2];previous_receipt_sha256='79A9C3534C2CB4DB56C865391516152582FB4A8006EE97F265889D766561EBD5';
        system_coverage=$system.coverage;file_coverage=$refs.coverage;retained_texts_checked=$textCount;
        limitations=@('R1 retired duplicate files only; no server-wide cleanup claim.','Historical unique JSON paths are not rewritten; restoration uses retained_relative_path mapping.',
        'Literal bounded reference search is not complete no-use proof; other users/drives/COM/encoded references unresolved.',
        'File main bytes remain in R2_clean; ACL/creation-time restoration is not promised. Do not run retired R1 tooling.')})
    $fresh=Get-QTree $root;Assert-ReleasePairInventory $fresh $contract $metadata
    Write-Host '[5/6] Open all 22 delete handles, reverify pairs and permanently delete R1 duplicates only.'
    Invoke-ReleasePairDeletion $root $plan $readStreams $ids $journal $confirmed
    Write-Host '[6/6] Rehash the 24 retained pair files; verify global file inventory and unchanged directories.'
    foreach($row in $pairRows){
        if($deleteNames.ContainsKey($row.relative_path)){continue}
        $s=$readStreams[$row.relative_path]
        if($s.Length -ne $row.length -or (Get-QHash $s) -cne $row.sha256){throw 'Retained pair verification failed.'}
    }
    $final=Get-QTree $root
    if(-not $final.complete){throw 'Final inventory incomplete.'}
    $actual=@{};foreach($row in $final.rows){$actual[$row.relative]=$row}
    foreach($dir in $contract.dirs){if(-not $actual.ContainsKey($dir) -or -not $actual[$dir].directory){throw 'An original directory changed.'}}
    foreach($relative in $contract.files.Keys){
        if($deleteNames.ContainsKey($relative)){if($actual.ContainsKey($relative)){throw 'A deleted path remains.'}}
        elseif(-not $actual.ContainsKey($relative) -or $actual[$relative].directory -or $actual[$relative].length -ne $contract.files[$relative].length){throw 'Retained inventory differs.'}
    }
    foreach($name in $metadata){if(-not $actual.ContainsKey($name) -or $actual[$name].directory){throw 'Historical metadata missing.'}}
    if($actual.Count -ne ($contract.dirs.Count+448+6) -or $confirmed.Count -ne 22){throw 'Unexpected final count.'}
    $result=[pscustomobject]@{event='COMPLETE';result='V1019_RELEASE_PAIR_DUPLICATES_REMOVED';at=[DateTimeOffset]::Now.ToString('o');
        deleted_files=$confirmed.Count;deleted_bytes=157989430L;deleted_directories=0;retained_pair_files=24;retained_original_files=448;metadata_files_retained=6;
        pair_files_rehashed_before=46;pair_files_rehashed_after=24;other_retained_files_full_hash_recheck=$false;
        receipt_directory=$output;retained_copy_root=(Join-Path $root $plan.keep_top);unique_jsons_preserved=$uniqueNames;
        recovery='Copy retained_relative_path main bytes to the corresponding missing relative_path only; no automatic restore.';
        product_changes_made=$false;app_restart_performed=$false;installation_started=$false;server_cleanup_complete=$false}
    Write-CleanupRecord $journal $result;$result|ConvertTo-Json -Depth 6
    $journal.Dispose();$journal=$null
    $s=[IO.File]::Open(($output+'\cleanup.jsonl'),'Open','Read','Read');try{Write-Host ('[JOURNAL SHA256] '+(Get-QHash $s))}finally{$s.Dispose()}
    Write-Host '[DONE] Return complete output. Do not rerun this completed cleanup.'
}catch{
    if($null -ne $journal){try{Write-CleanupRecord $journal ([pscustomobject]@{event='HOLD';at=[DateTimeOffset]::Now.ToString('o');confirmed_deleted_files=$confirmed.Count})}catch{Write-Host '[WARNING] HOLD journal write failed; preserve preceding intent records.'}}
    Write-Host ('[HOLD] No automatic retry/restore/install. Confirmed deleted files='+$confirmed.Count+' receipt='+$output)
    throw
}finally{
    if($null -ne $journal){$journal.Dispose()};foreach($s in $pins){$s.Dispose()};foreach($g in $guards.Values){$g.handle.Dispose()}
    $env:PATH=$savedPairPath;$env:PSModulePath=$savedPairModules
}
