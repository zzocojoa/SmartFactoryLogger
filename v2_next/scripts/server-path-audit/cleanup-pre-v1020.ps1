[CmdletBinding()]
param([switch]$Execute)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$native=[IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
$principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not [Environment]::Is64BitProcess -or $PSVersionTable.PSEdition -cne 'Desktop' -or
    $PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1 -or
    [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName -ine $native -or
    -not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Use native administrator x64 Windows PowerShell 5.1.'
}
$savedCleanupPath=$env:PATH; $savedCleanupModules=$env:PSModulePath
$pins=[Collections.Generic.List[IDisposable]]::new(); $guards=@{}; $sourceStreams=@{}; $ids=@{}
$journal=$null; $output=''; $deleted=[Collections.Generic.List[object]]::new()
$clock=[Diagnostics.Stopwatch]::StartNew()
$root='C:\Users\user\Desktop\SmartFactory_Archive\pre_v1020_quarantine_20260813_092302'
$metadata=@('quarantine_manifest_before_move.json','quarantine_verification_after_move.json','quarantine_verification_after_move_R1_1.json')
$specs=@(
    @(198366L,'F918CAF4ABCC65124E86F50D2DD79DFCC962ECC221FD8E0997DB2402FE468752'),
    @(656L,'4CB03191D3E8816A713EA4A65D6EC03FDAC6FB94606E06B62B7F4EB1D9893D14'),
    @(1628L,'4D6A6984ED3B1E2AEEEA58C9C8403FC0E3543F649EBE296E5BB2DCB671C20671'))
try {
    $env:PATH=[Environment]::SystemDirectory+';'+[IO.Path]::GetDirectoryName($native)
    $env:PSModulePath=[IO.Path]::GetDirectoryName($native)+'\Modules'
    # These are trusted helper dependencies, never source-evidence scripts.
    foreach ($dependency in @(
        @('read-quarantine-pre-v1020.ps1','EBEB041A42D0FC2232ADCDDA13547C8151209C22E8D85F1B1B1D70D7021A1765'),
        @('cleanup-archive-core.ps1','CD9F2387581C52FA9A26EC6E217909919F472CB5DF9853C2E96A2A368FF40A28'))) {
        $path=Join-Path $PSScriptRoot $dependency[0]
        $s=[IO.File]::Open($path,'Open','Read','Read'); $pins.Add($s)
        $sha=[Security.Cryptography.SHA256]::Create()
        try { $actual=[BitConverter]::ToString($sha.ComputeHash($s)).Replace('-','') } finally { $sha.Dispose() }
        if ($actual -cne $dependency[1]) { throw 'Helper dependency hash mismatch.' }
        $s.Position=0; $reader=[IO.StreamReader]::new($s,[Text.UTF8Encoding]::new($false,$true),$true,4096,$true)
        try { $text=$reader.ReadToEnd() } finally { $reader.Dispose() }
        $tokens=$null; $errors=$null
        $ast=[Management.Automation.Language.Parser]::ParseInput($text,[ref]$tokens,[ref]$errors)
        if (@($errors).Count -ne 0) { throw 'Helper dependency syntax error.' }
        # Import function definitions only, not the old read-only helper's main.
        foreach ($fn in $ast.FindAll({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst]},$true)) {
            . ([scriptblock]::Create($fn.Extent.Text))
        }
    }
    Initialize-CleanupNative
    Add-Type -AssemblyName System.IO.Compression
    if ([IO.DriveInfo]::new('C:\').DriveFormat -cne 'NTFS') { throw 'Only local NTFS is supported.' }
    Write-Host '[1/6] Verify the fixed historical archive and pin its paths. No product APIs or restart.'
    Open-CleanupDirectoryGuard $root $guards
    $allMetadata=[Collections.Generic.List[string]]::new(); $manifest=$null
    for ($i=0;$i -lt $metadata.Count;$i++) {
        $s=Open-QPinned (Join-Path $root $metadata[$i]) $specs[$i][0] $specs[$i][1] $pins
        if ($i -eq 0) { $manifest=ConvertFrom-Json -InputObject (Read-QText $s) }
        $allMetadata.Add($metadata[$i]); $name=$metadata[$i]+'.sha256.txt'
        Assert-QPlain (Join-Path $root $name)
        $side=[IO.File]::Open((Join-Path $root $name),'Open','Read','Read'); $pins.Add($side)
        if ($side.Length -gt 70 -or (Read-QText $side) -cnotmatch ('\A'+$specs[$i][1]+'(?:\r?\n)?\z')) { throw 'Historical sidecar mismatch.' }
        $allMetadata.Add($name)
    }
    if ($manifest.quarantine_root -cne $root -or $manifest.file_count -ne 558 -or $manifest.total_bytes -ne 1077165719L -or
        @($manifest.top_level_items).Count -ne 136) { throw 'Historical manifest identity differs.' }
    $contract=Get-QContract $manifest; $tree=Get-QTree $root
    $comparison=Compare-QTree $tree $contract $allMetadata.ToArray()
    if (-not $tree.complete -or $comparison.missing.Count -gt 0 -or $comparison.unlisted.Count -gt 0) {
        throw 'Source tree changed or incomplete. No automatic cleanup of extra/missing items.'
    }
    foreach ($dir in @($tree.rows | Where-Object directory | Sort-Object path)) { Open-CleanupDirectoryGuard $dir.path $guards }
    $n=0
    foreach ($row in @($manifest.files)) {
        $path=Join-Path $root $row.relative_path; Assert-CleanupChild $root $path
        $s=[SflCleanupNativeV1]::OpenFile($path,$false); $pins.Add($s)
        if ($s.Length -ne $row.length -or (Get-QHash $s) -cne $row.sha256) { throw 'Source bytes changed; no deletion.' }
        $sourceStreams[$row.relative_path]=$s; $ids[$row.relative_path]=[SflCleanupNativeV1]::Identity($s.SafeFileHandle,$path,$false)
        $n++; if ($n % 50 -eq 0) { Write-Host ('[HASH] '+$n+'/558') }
        if ($clock.Elapsed.TotalSeconds -gt 600) { throw 'Initial verification budget exhausted.' }
    }
    $protected=@{}; $candidates=@{}; $byTop=@{}; $texts=@{}; $zipFailures=@()
    foreach ($top in @($manifest.top_level_items)) {
        $byTop[$top]=@($manifest.files | Where-Object {$_.relative_path.StartsWith($top+'\',[StringComparison]::Ordinal)})
        if ($byTop[$top].Count -eq 0) { $protected[$top]='direct-file-always-retained' }
    }
    foreach ($top in @('install_v1019_0c1ad4f_20260810_115343','reattest_v1019_0c1ad4f_20260810_122209',
        'reattest_v1019_0c1ad4f_R2_1_20260810_125243','reattest_v1019_0c1ad4f_R2_2_20260810_222958',
        'v1019_0c1ad4f_post_canary_closeout_20260812_R4')) { $protected[$top]='historical-backup-config-or-R4-dependency' }
    Write-Host '[2/6] Reopen retained direct ZIPs; compare complete folder contents. Partial matches never qualify.'
    $expanded=0L
    foreach ($zipRow in @($manifest.files | Where-Object {$_.relative_path -notmatch '\\' -and $_.relative_path.EndsWith('.zip',[StringComparison]::Ordinal)} | Sort-Object relative_path)) {
        Write-Host ('[ZIP] '+$zipRow.relative_path)
        try { $index=Get-CleanupZipIndex $sourceStreams[$zipRow.relative_path] ([ref]$expanded) }
        catch { $zipFailures+=@($zipRow.relative_path); continue }
        foreach ($top in @($byTop.Keys | Sort-Object)) {
            if ($protected.ContainsKey($top) -or $candidates.ContainsKey($top)) { continue }
            $mapping=Find-CleanupArchiveMapping $top $byTop[$top] $index
            if ($null -ne $mapping) {
                $candidates[$top]=[pscustomobject]@{top=$top;zip=$zipRow.relative_path;zip_sha256=$zipRow.sha256;files=@($mapping)}
            }
        }
        if ($clock.Elapsed.TotalSeconds -gt 900) { throw 'ZIP verification budget exhausted; no deletion.' }
    }
    Write-Host '[3/6] Protect referenced folders, unknown streams and backups. No evidence content is printed.'
    foreach ($row in @($manifest.files)) {
        $top=$row.relative_path.Split('\')[0]
        if ($candidates.ContainsKey($top)) {
            try { [SflCleanupNativeV1]::NoAlternateStreams((Join-Path $root $row.relative_path),$false) }
            catch { $protected[$top]='unarchived-stream-or-stream-inspection-failed' }
        }
        $ext=[IO.Path]::GetExtension($row.relative_path).ToLowerInvariant()
        if ($ext -in @('.json','.txt','.md','.ps1','.psm1','.cmd','.bat','.ini','.before_reattestation') -or $row.relative_path -match '(?i)config\.ini') {
            # Never discard a folder containing unexpected settings, even if also zipped.
            if ($ext -in @('.ini','.before_reattestation') -or $row.relative_path -match '(?i)config\.ini|backup_before') {
                $protected[$top]='settings-or-backup'
            }
            try { $texts[$row.relative_path]=Read-QText $sourceStreams[$row.relative_path] }
            catch { throw 'Retained-text inspection incomplete; no deletion.' }
        }
    }
    foreach ($dir in @($tree.rows | Where-Object directory)) {
        $top=$dir.relative.Split('\')[0]
        if ($candidates.ContainsKey($top)) {
            try { [SflCleanupNativeV1]::NoAlternateStreams($dir.path,$true) }
            catch { $protected[$top]='directory-stream-or-inspection-failed' }
        }
    }
    $needles=@($candidates.Keys)
    $system=Get-QSystemReferences (@($needles)+@($root,'SmartFactory_Archive'))
    if (@($system.coverage | Where-Object {$_.status -cne 'SNAPSHOT_QUERIED' -or $_.omitted_hits -gt 0}).Count -gt 0) { throw 'System reference query incomplete.' }
    foreach ($hit in $system.hits) {
        foreach ($name in $hit.matched_names) {
            if ($name -in @($root,'SmartFactory_Archive')) { throw 'A system reference points into this archive; no deletion.' }
            $protected[$name]='system-reference'
        }
    }
    $scopes=@(
        [pscustomobject]@{path='C:\Users\user\Desktop';depth=0;kind='shortcut'},
        [pscustomobject]@{path='C:\Users\Public\Desktop';depth=0;kind='shortcut'},
        [pscustomobject]@{path='C:\Users\user\AppData\Roaming\Microsoft\Windows\Start Menu';depth=5;kind='shortcut'},
        [pscustomobject]@{path='C:\ProgramData\Microsoft\Windows\Start Menu';depth=5;kind='shortcut'},
        [pscustomobject]@{path='C:\Users\user\Desktop\SmartFactory';depth=0;kind='text'})
    foreach ($stage in @('SFL-76B317D0A2901C6EFC649404211C8109','SFL-9B645BE54EB0C6C7A7F1C482248174EB',
        'SFL-B63483AD9AB07924E5F291076F911BDA','SFL-v1023-v11-8C1B97EF0F3BA3DAC26F38CD7B8D5656',
        'SFL26S-29aee83c36044389828d6d20eb645503','SFL26S-ae681d39b54a40c59da518292d259f95')) {
        $scopes += [pscustomobject]@{path=('C:\ProgramData\'+$stage);depth=3;kind='text'}
    }
    $refs=Get-QFileReferences $needles $scopes
    Assert-CleanupReferenceCoverage $refs.coverage
    foreach ($hit in $refs.hits) { foreach ($name in $hit.matched_names) { $protected[$name]='external-file-reference' } }
    # The six inventory/verification metadata files enumerate everything by design, not dependencies.
    Protect-CleanupReferences $candidates $texts $protected
    $plan=@($candidates.Values | Where-Object {-not $protected.ContainsKey($_.top)} | Sort-Object top)
    $files=@($plan | ForEach-Object {$_.files}); $bytes=0L
    foreach ($row in $files) { $bytes+=$row.length }
    Write-Host ('[PLAN] complete duplicate folders='+$plan.Count+' files='+$files.Count+' bytes='+$bytes)
    foreach ($folder in $plan) { Write-Host ('[DELETE FOLDER] '+$folder.top+' [KEEP ZIP] '+$folder.zip) }
    if (-not $Execute) {
        [pscustomobject]@{result='PLAN_ONLY';root=$root;plan=$plan;protected=$protected;zip_not_eligible=$zipFailures;deletion_performed=$false} | ConvertTo-Json -Depth 12
        return
    }
    Write-Host '[4/6] Persist exact plan in SFLOps before deletion. Retained ZIPs stay read-locked.'
    foreach ($path in @('C:\ProgramData\SFLOps','C:\ProgramData\SFLOps\inventory')) {
        New-CleanupPrivateDirectory $path; Open-CleanupDirectoryGuard $path $guards
    }
    $output='C:\ProgramData\SFLOps\inventory\q20-'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'-'+[Guid]::NewGuid().ToString('N').Substring(0,8)
    if ([IO.Directory]::Exists($output) -or [IO.File]::Exists($output)) { throw 'Receipt directory already exists.' }
    New-CleanupPrivateDirectory $output; Open-CleanupDirectoryGuard $output $guards
    $journal=[IO.File]::Open(($output+'\cleanup.jsonl'),'CreateNew','Write','Read')
    Write-CleanupRecord $journal ([pscustomobject]@{event='PLAN';at=[DateTimeOffset]::Now.ToString('o');root=$root;
        manifest_sha256=$specs[0][1];authorization='USER_APPROVED_UNNECESSARY_MATERIAL_CLEANUP';policy='only-full-extracted-folder-duplicates-v1';
        plan=$plan;protected=$protected;zip_not_eligible=$zipFailures;system_reference_coverage=$system.coverage;file_reference_coverage=$refs.coverage;
        limitations=@('Only this retired quarantine. No server-wide cleanup claim.','Literal bounded references; other users/drives/indirect references and COM actions unresolved.',
        'Preserved direct ZIP restores main file bytes and relative names, not ACLs/timestamps. No current-data backup assertion.')})
    $fresh=Get-QTree $root; $check=Compare-QTree $fresh $contract $allMetadata.ToArray()
    if (-not $fresh.complete -or $check.missing.Count -gt 0 -or $check.unlisted.Count -gt 0) { throw 'Source enumeration changed before deletion.' }
    Write-Host '[5/6] Permanently remove verified duplicate files only; stop on any unexpected change.'
    foreach ($folder in $plan) {
        $deleteHandles=@{}
        try {
            # Acquire and verify EVERY leaf for this folder before deleting its first leaf.
            foreach ($row in $folder.files) {
                $sourceStreams[$row.relative_path].Dispose()
                $path=Join-Path $root $row.relative_path; Assert-CleanupChild $root $path
                $s=[SflCleanupNativeV1]::OpenFile($path,$true); $deleteHandles[$row.relative_path]=$s
                if ($s.Length -ne $row.length -or (Get-QHash $s) -cne $row.sha256 -or
                    [SflCleanupNativeV1]::Identity($s.SafeFileHandle,$path,$false) -cne $ids[$row.relative_path]) {
                    throw 'Folder changed; no deletion starts for this folder.'
                }
                [SflCleanupNativeV1]::NoAlternateStreams($path,$false)
            }
            foreach ($row in $folder.files) {
                Remove-CleanupVerifiedFile $root $row $ids[$row.relative_path] $journal $deleteHandles[$row.relative_path] $deleted
            }
        } finally { foreach ($s in $deleteHandles.Values) { $s.Dispose() } }
        foreach ($dir in @($tree.rows | Where-Object {$_.directory -and ($_.relative -ceq $folder.top -or $_.relative.StartsWith($folder.top+'\',[StringComparison]::Ordinal))} | Sort-Object @{Expression={$_.path.Length};Descending=$true})) {
            Assert-CleanupChild $root $dir.path
            $guard=$guards[$dir.path]; $guard.handle.Dispose()
            Write-CleanupRecord $journal ([pscustomobject]@{event='EMPTY_DIRECTORY_INTENT';relative_path=$dir.relative})
            [SflCleanupNativeV1]::DeleteEmptyDirectory($dir.path,$guard.identity)
            Write-CleanupRecord $journal ([pscustomobject]@{event='EMPTY_DIRECTORY_DELETED';relative_path=$dir.relative})
        }
        Write-Host ('[DELETED] '+$folder.top)
    }
    Write-Host '[6/6] Rehash all retained source files and verify final inventory.'
    $deletedNames=@{}; foreach ($row in $deleted) { $deletedNames[$row.relative_path]=$true }
    foreach ($row in $manifest.files) {
        if ($deletedNames.ContainsKey($row.relative_path)) { continue }
        $s=$sourceStreams[$row.relative_path]
        if ($s.Length -ne $row.length -or (Get-QHash $s) -cne $row.sha256) { throw 'Retained source verification failed.' }
    }
    $final=Get-QTree $root
    if (-not $final.complete) { throw 'Final enumeration incomplete.' }
    $actual=@{}; foreach ($row in @($final.rows | Where-Object {-not $_.directory})) { $actual[$row.relative]=$true }
    foreach ($name in $contract.files.Keys) {
        if ($actual.ContainsKey($name) -eq $deletedNames.ContainsKey($name)) { throw 'Final file presence differs from plan.' }
    }
    if ($actual.Count -ne (558-$deleted.Count+6)) { throw 'Unexpected final files.' }
    foreach ($dir in @($final.rows | Where-Object directory)) {
        if (-not $contract.dirs.Contains($dir.relative) -or @($plan | Where-Object {$_.top -ceq $dir.relative.Split('\')[0]}).Count -gt 0) {
            throw 'Unexpected or incompletely removed final directory.'
        }
    }
    $result=[pscustomobject]@{event='COMPLETE';result=$(if($deleted.Count -gt 0){'VERIFIED_DUPLICATE_FOLDERS_REMOVED'}else{'NO_ELIGIBLE_DUPLICATE_FOLDERS'});
        at=[DateTimeOffset]::Now.ToString('o');deleted_folders=$plan.Count;deleted_files=$deleted.Count;deleted_bytes=$bytes;
        retained_original_files=(558-$deleted.Count);metadata_files_retained=6;receipt_directory=$output;source_root=$root;
        recovery='Exact main bytes remain in read-verified direct ZIPs; use per-file zip_entry mapping in PLAN. No automatic restore.';
        server_cleanup_complete=$false;product_changes_made=$false;app_restart_performed=$false;installation_started=$false}
    Write-CleanupRecord $journal $result
    $result | ConvertTo-Json -Depth 5
    $journal.Dispose(); $journal=$null
    $receipt=[IO.File]::Open(($output+'\cleanup.jsonl'),'Open','Read','Read')
    try { Write-Host ('[JOURNAL SHA256] '+(Get-QHash $receipt)) } finally { $receipt.Dispose() }
    Write-Host '[DONE] Return the complete output. Other server folders have not been deleted.'
} catch {
    if ($null -ne $journal) {
        try { Write-CleanupRecord $journal ([pscustomobject]@{event='HOLD';at=[DateTimeOffset]::Now.ToString('o');confirmed_deleted_files=$deleted.Count;message='Stopped; preserve journal and ZIPs; no automatic retry.'}) }
        catch { Write-Host '[WARNING] Final HOLD journal write failed; inspect preceding INTENT/DELETED records.' }
    }
    Write-Host ('[HOLD] No automatic retry/cleanup. Confirmed deleted files='+$deleted.Count+' receipt='+$output)
    throw
} finally {
    if ($null -ne $journal) { $journal.Dispose() }
    foreach ($pin in $pins) { $pin.Dispose() }
    foreach ($guard in $guards.Values) { $guard.handle.Dispose() }
    $env:PATH=$savedCleanupPath; $env:PSModulePath=$savedCleanupModules
}
