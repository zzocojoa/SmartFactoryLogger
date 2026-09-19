& {
    Set-StrictMode -Version Latest
    $ErrorActionPreference='Stop'
    $savedStoragePath=$env:PATH; $savedStorageModules=$env:PSModulePath
    $storageClock=[Diagnostics.Stopwatch]::StartNew()
    $appDataRoot='C:\Users\user\AppData\Roaming\SmartFactoryLogger'
    $electronRoot='C:\Users\user\AppData\Roaming\smart-factory-logger-v2'
    $installRoot='C:\Users\user\AppData\Local\Programs\smart-factory-logger-v2'
    $backendRoot=$installRoot+'\resources\backend'
    $backupCandidateRoot='C:\Users\user\Desktop\SmartFactory'
    $dataRoot=$appDataRoot+'\logs\test_data'
    $configPath=$appDataRoot+'\config.ini'
    $recoveryExe='C:\ProgramData\SFL-76B317D0A2901C6EFC649404211C8109\SmartFactoryLogger_v1.0.25_a203baf_unsigned_internal_20260909T012500Z\smart-factory-logger-v2 Setup 1.0.25.exe'
    $commit='a203baf62b544d38072a32d71ef411c7cf8b6490'
    $allowedRoots=@($appDataRoot,$electronRoot,$backendRoot,$backupCandidateRoot)

    function Need { param([bool]$OK,[string]$Code) if(-not $OK){throw ('STORAGE_CHECK:'+ $Code)} }
    function Field {
        param([object]$Object,[string]$Name)
        Need ($Object -is [pscustomobject] -and $Object -isnot [Array]) 'object-shape'
        $p=$Object.PSObject.Properties[$Name]
        Need ($null -ne $p -and $p.Value -isnot [Array]) ('field-'+$Name)
        return ,($p.Value)
    }
    function Counter {
        param([object]$Object,[string]$Name)
        $v=Field $Object $Name
        Need (($v -is [int] -or $v -is [long]) -and $v -ge 0) ('counter-'+$Name)
        return [long]$v
    }
    function TextHash {
        param([string]$Value)
        $s=[Security.Cryptography.SHA256]::Create()
        try {return [BitConverter]::ToString($s.ComputeHash([Text.UTF8Encoding]::new($false).GetBytes($Value))).Replace('-','')}
        finally {$s.Dispose()}
    }
    function FullLocal {
        param([object]$Value)
        Need ($Value -is [string] -and $Value.Length -ge 4 -and $Value.Length -le 240) 'path-shape'
        Need ($Value -cmatch '^[A-Za-z]:[\\/]' -and $Value -notmatch '[\x00-\x1F<>"|?*~]' -and $Value.Substring(2) -notmatch ':') 'path-syntax'
        $p=$Value.Replace('/','\').TrimEnd('\')
        Need ($p.Length -gt 3) 'broad-root-rejected'
        foreach($part in $p.Substring(3).Split('\')) {
            Need ($part.Length -gt 0 -and $part -ne '.' -and $part -ne '..' -and $part -notmatch '[ .]$' -and
                $part -notmatch '^(?i:CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\.|$)') 'path-component'
        }
        return [IO.Path]::GetFullPath($p)
    }
    function Within {
        param([string]$Path,[string]$Root)
        return $Path.Equals($Root,[StringComparison]::OrdinalIgnoreCase) -or $Path.StartsWith($Root+'\',[StringComparison]::OrdinalIgnoreCase)
    }
    function Approved {
        param([object]$Path)
        $p=FullLocal $Path; $ok=$p.Equals($recoveryExe,[StringComparison]::OrdinalIgnoreCase)
        foreach($root in $allowedRoots) {if(Within $p $root){$ok=$true}}
        Need $ok 'outside-approved-roots'
        return $p
    }
    function AttributesOrMissing {
        param([string]$Path)
        try {return [IO.File]::GetAttributes($Path)} catch {
            $e=$_.Exception
            while($null -ne $e.InnerException){$e=$e.InnerException}
            if($e -is [IO.FileNotFoundException] -or $e -is [IO.DirectoryNotFoundException]){return $null}
            throw 'STORAGE_CHECK:metadata-access-failed'
        }
    }
    function Metadata {
        param([string]$Path)
        $p=Approved $Path
        # Reject reparse points observed in ancestors before touching descendants.
        # Separate path checks are not native-handle no-follow protection against hostile path replacement.
        $node=[IO.FileInfo]::new($p); $ancestors=[Collections.Generic.List[string]]::new()
        while($null -ne $node) {
            $ancestors.Add($node.FullName)
            if($node -is [IO.FileInfo]){$node=$node.Directory}else{$node=$node.Parent}
        }
        $a=$null
        for($i=$ancestors.Count-1;$i -ge 0;$i--) {
            $a=AttributesOrMissing $ancestors[$i]
            if($null -eq $a){return [pscustomobject]@{path=$p;exists=$false;kind='missing';bytes=$null;last_write_utc=$null}}
            Need (($a -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'reparse-path-rejected'
        }
        $isDirectory=($a -band [IO.FileAttributes]::Directory) -ne 0
        $info=if($isDirectory){[IO.DirectoryInfo]::new($p)}else{[IO.FileInfo]::new($p)}
        $info.Refresh()
        Need ($info.Exists -and ($info.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'metadata-race'
        return [pscustomobject]@{path=$p;exists=$true;kind=$(if($isDirectory){'directory'}else{'file'});
            bytes=$(if($isDirectory){$null}else{$info.Length});last_write_utc=$info.LastWriteTimeUtc.ToString('o')}
    }
    function BoundedHash {
        param([string]$Path,[string]$Expected,[long]$Maximum,[bool]$Shared)
        $p=Approved $Path
        Need ($p -ieq $configPath -or $p -ieq $recoveryExe) 'unapproved-content-read'
        $m=Metadata $p; Need ($m.exists -and $m.kind -ceq 'file' -and $m.bytes -gt 0 -and $m.bytes -le $Maximum) 'pinned-file-shape'
        $share=if($Shared){[IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete}else{[IO.FileShare]::Read}
        $s=[IO.File]::Open($p,'Open','Read',$share); $sha=[Security.Cryptography.SHA256]::Create()
        try {
            Need ($s.Length -eq $m.bytes) 'pinned-file-size-changed'
            # A bounded stream copy avoids reading an unbounded growing file under shared access.
            $remaining=$s.Length; $chunk=New-Object byte[] 65536; $clock=[Diagnostics.Stopwatch]::StartNew()
            while($remaining -gt 0) {
                Need ($clock.Elapsed.TotalSeconds -le 30) 'hash-time-budget'
                $n=$s.Read($chunk,0,[int][Math]::Min($chunk.Length,$remaining))
                Need ($n -gt 0) 'pinned-file-truncated'
                [void]$sha.TransformBlock($chunk,0,$n,$chunk,0); $remaining-=$n
            }
            [void]$sha.TransformFinalBlock((New-Object byte[] 0),0,0)
            $actual=[BitConverter]::ToString($sha.Hash).Replace('-','')
            Need ($s.Length -eq $m.bytes -and $actual -ceq $Expected) 'pinned-file-hash-mismatch'
            return [pscustomobject]@{path=$p;bytes=$m.bytes;sha256=$actual;matches_pin=$true}
        } finally {$sha.Dispose();$s.Dispose()}
    }
    function Decode {
        param([string]$Text)
        Need (-not [string]::IsNullOrWhiteSpace($Text) -and $Text.TrimStart().StartsWith('{',[StringComparison]::Ordinal)) 'json-root'
        $v=ConvertFrom-Json -InputObject $Text
        Need ($v -is [pscustomobject] -and $v -isnot [Array]) 'json-shape'
        return ,$v
    }
    function LocalGet {
        param([string]$Endpoint)
        Need ($Endpoint -cin @('health','api/config','api/spot/config')) 'endpoint-rejected'
        $r=[Net.HttpWebRequest]::Create('http://127.0.0.1:8000/'+$Endpoint)
        $r.Method='GET';$r.Proxy=$null;$r.AllowAutoRedirect=$false;$r.Timeout=10000;$r.ReadWriteTimeout=10000
        $response=$null;$stream=$null;$buffer=[IO.MemoryStream]::new();$clock=[Diagnostics.Stopwatch]::StartNew()
        try {
            $response=$r.GetResponse();Need ([int]$response.StatusCode -eq 200) 'http-status'
            $stream=$response.GetResponseStream();$chunk=New-Object byte[] 8192
            while(($n=$stream.Read($chunk,0,$chunk.Length)) -gt 0) {
                Need ($buffer.Length+$n -le 2097152 -and $clock.Elapsed.TotalSeconds -le 20) 'response-budget'
                $buffer.Write($chunk,0,$n)
            }
            return Decode ([Text.UTF8Encoding]::new($false,$true).GetString($buffer.ToArray()))
        } finally {if($null -ne $stream){$stream.Dispose()};if($null -ne $response){$response.Dispose()};$buffer.Dispose()}
    }
    function RuntimeAnchor {
        $backends=@(Get-Process -Name SmartFactoryBackend -ErrorAction SilentlyContinue)
        $apps=@(Get-Process -Name smart-factory -ErrorAction SilentlyContinue)
        $owners=@(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue|Select-Object -ExpandProperty OwningProcess -Unique)
        Need ($backends.Count -eq 1 -and $owners.Count -eq 1 -and $owners[0] -eq $backends[0].Id) 'runtime-listener'
        $backend=$backends[0];$backendCim=Get-CimInstance Win32_Process -Filter ('ProcessId = '+$backend.Id)
        $main=@($apps|Where-Object Id -eq $backendCim.ParentProcessId)
        Need ($main.Count -eq 1 -and $backend.Path -ieq ($backendRoot+'\SmartFactoryBackend.exe')) 'runtime-parent-path'
        foreach($app in $apps){Need ($app.Path -ieq ($installRoot+'\smart-factory.exe')) 'app-path'}
        $currentSid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
        $mainCim=Get-CimInstance Win32_Process -Filter ('ProcessId = '+$main[0].Id)
        foreach($process in @($backendCim,$mainCim)) {
            $owner=Invoke-CimMethod -InputObject $process -MethodName GetOwnerSid
            Need ($owner.ReturnValue -eq 0 -and $owner.Sid -ceq $currentSid) 'process-user-differs'
        }
        return [pscustomobject]@{main_pid=$main[0].Id;main_ticks=$main[0].StartTime.ToUniversalTime().Ticks;
            backend_pid=$backend.Id;backend_ticks=$backend.StartTime.ToUniversalTime().Ticks;owner_matches_current_user=$true}
    }
    function SameRuntime {
        param([object]$A,[object]$B)
        foreach($n in @('main_pid','main_ticks','backend_pid','backend_ticks')) {Need ($A.$n -eq $B.$n) 'runtime-changed'}
    }
    function StorageSettings {
        param([object]$Response)
        $settings=Field (Field $Response 'values') 'settings'
        $capture=Field (Field (Field $Response 'values') 'spot') 'image_capture'
        $config=FullLocal (Field $Response 'config_path');$log=FullLocal (Field $settings 'logpath');$snap=FullLocal (Field $settings 'snapshotpath')
        Need ($config -ieq $configPath -and $log -ieq $dataRoot -and $snap -ieq ($appDataRoot+'\snapshots')) 'storage-setting-path-changed'
        $imagePath=Field $capture 'path';Need ($imagePath -is [string] -and $imagePath -ceq 'spot_images') 'capture-setting-path-changed'
        $restart=Field $Response 'restart_required';Need ($restart -is [bool] -and -not $restart) 'pending-config-restart'
        return [pscustomobject]@{config_path=$config;configured_log_root=$log;configured_snapshot_root=$snap;configured_image_relative=$imagePath;
            pending_restart=$restart;active_runtime_paths_proven=$false}
    }
    function RecentCapture {
        param([object]$Response)
        $c=Field $Response 'image_capture';$raw=Field $c 'last_capture_path'
        Need ($raw -is [string] -and $raw -cmatch '^spot_images/[0-9]{4}/[0-9]{2}/[0-9]{2}/spotimg_[0-9]{8}T[0-9]{12}Z_[0-9a-f]{12}\.(jpg|bin)$') 'capture-relative-path'
        $id=Field $c 'last_capture_id'
        Need ($id -is [string] -and [IO.Path]::GetFileNameWithoutExtension($raw) -ceq $id) 'capture-id-path'
        $enabled=Field $c 'enabled';Need ($enabled -is [bool]) 'capture-enabled'
        $fact=Metadata ($dataRoot+'\'+$raw.Replace('/','\'))
        return [pscustomobject]@{capture_id=$id;api_path=$raw;file=$fact;enabled=$enabled;written_count=(Counter $c 'written_count');
            enqueued_count=(Counter $c 'enqueued_count');dropped_count=(Counter $c 'dropped_count');failure_count=(Counter $c 'failure_count');
            queue_size=(Counter $c 'queue_size');candidate_path_exists=($fact.exists -and $fact.kind -ceq 'file');
            content_hash_verified=$false;entire_capture_root_proven=$false}
    }
    function DirectorySummary {
        param([string]$Path,[int]$Limit=2048)
        Need ($Limit -gt 0 -and $Limit -le 4096) 'inventory-limit'
        $m=Metadata $Path
        if(-not $m.exists){return [pscustomobject]@{path=$m.path;exists=$false;enumeration_complete=$false;recursive=$false;files=$null;bytes=$null}}
        Need ($m.kind -ceq 'directory') 'expected-directory'
        $clock=[Diagnostics.Stopwatch]::StartNew();$entries=0;$files=0;$dirs=0;$bytes=[long]0;$complete=$true
        $types=@{csv=0;json=0;image=0;log=0;archive=0;other=0};$latest=[Collections.Generic.List[object]]::new()
        $archives=[Collections.Generic.List[object]]::new()
        $enumerator=[IO.Directory]::EnumerateFileSystemEntries($m.path).GetEnumerator()
        try {
            while($enumerator.MoveNext()) {
                if($entries -ge $Limit -or $clock.Elapsed.TotalSeconds -gt 15){$complete=$false;break}
                $p=[string]$enumerator.Current;Need (Within (FullLocal $p) $m.path) 'inventory-boundary'
                $v=Metadata $p;$entries++
                if(-not $v.exists){$complete=$false;continue}
                if($v.kind -ceq 'directory'){$dirs++;continue}
                $files++;$bytes+=[long]$v.bytes;$ext=[IO.Path]::GetExtension($p).ToLowerInvariant()
                $type=switch($ext){'.csv'{'csv'} '.json'{'json'} '.jpg'{'image'} '.bin'{'image'} '.log'{'log'} '.jsonl'{'log'} '.zip'{'archive'} '.7z'{'archive'} '.tar'{'archive'} '.gz'{'archive'} default{'other'}}
                $types[$type]++
                if($type -ceq 'archive' -and $archives.Count -lt 20) {
                    $archives.Add([pscustomobject]@{filename_sha256=(TextHash ([IO.Path]::GetFileName($p)));bytes=$v.bytes;
                        last_write_utc=$v.last_write_utc;contents_opened=$false;is_verified_backup=$false})
                }
                # Only fixed generated CSV names are shareable; no arbitrary filenames or file contents.
                if([IO.Path]::GetFileName($p) -cmatch '^Factory_Integrated_Log(?:_v2)?_[0-9_-]+\.csv$') {
                    $latest.Add($v)
                    if($latest.Count -gt 4) {
                        $keep=@($latest|Sort-Object last_write_utc -Descending|Select-Object -First 4)
                        $latest.Clear();foreach($item in $keep){$latest.Add($item)}
                    }
                }
                if(($entries % 256) -eq 0){Write-Host ('[METADATA] entries='+$entries+' elapsed='+[int]$clock.Elapsed.TotalSeconds+'s; no file contents read')}
            }
        } finally {$enumerator.Dispose()}
        return [pscustomobject]@{path=$m.path;exists=$true;enumeration_complete=$complete;recursive=$false;immediate_entries=$entries;
            files=$files;directories=$dirs;immediate_file_bytes=$bytes;file_types=[pscustomobject]$types;latest_csv=$latest.ToArray();
            archive_metadata=$archives.ToArray();archive_listing_truncated=($types.archive -gt $archives.Count);
            bytes_are_backup_size=$false;limitation='Immediate children only, live metadata may change; not an atomic inventory or full backup scope.'}
    }

    try {
        $native=[IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
        $principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
        Need ([Environment]::Is64BitProcess -and $PSVersionTable.PSEdition -ceq 'Desktop' -and $PSVersionTable.PSVersion.Major -eq 5 -and
            $PSVersionTable.PSVersion.Minor -eq 1 -and [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName -ieq $native -and
            $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) 'native-admin-ps51-required'
        Need ((FullLocal $env:APPDATA) -ieq 'C:\Users\user\AppData\Roaming') 'operator-profile-differs'
        $env:PATH=[Environment]::SystemDirectory+';'+[IO.Path]::GetDirectoryName($native)
        $env:PSModulePath=[IO.Path]::GetDirectoryName($native)+'\Modules'
        Write-Host '[STEP 1/5] Verify same v1.0.25 runtime, config and recovery EXE. No backup, write test, restart or installation.' -ForegroundColor Cyan
        $anchor=RuntimeAnchor
        SameRuntime ([pscustomobject]@{main_pid=6728;main_ticks=639245234920357237;backend_pid=7620;backend_ticks=639245234936285878}) $anchor
        $health=LocalGet 'health'
        Need ((Field $health 'app_version') -ceq '1.0.25' -and (Field (Field $health 'spot_temperature') 'build_git_commit') -ceq $commit) 'version-commit'
        $settings=StorageSettings (LocalGet 'api/config')
        $configBefore=BoundedHash $configPath '6841C848A443DF91966C991707C2B21CA57C575993DCA36FACFF2592D070147E' 1048576 $true
        $recovery=BoundedHash $recoveryExe '9EE81CD9B809275B7E49E1441CBBF11C2B7BBC1E2A372A7D7163E4DCFFE6ADA1' 536870912 $false
        Write-Host '[STEP 2/5] Read metadata of fixed state/profile files and storage candidates. Contents are not exported.'
        $stateFiles=@('config.ini','config.bak','config.pending.json','config_meta.json','config_cache.json','layout.json','layout.backup.json',
            'operator_metadata.json','operator_metadata_runtime_state.json','state.json')
        $states=@(foreach($name in $stateFiles){Metadata ($appDataRoot+'\'+$name)})
        $profiles=@(foreach($name in @('Local State','Preferences','Cookies','Network\Cookies','Local Storage\leveldb','Session Storage','IndexedDB','debug_electron.log')){Metadata ($electronRoot+'\'+$name)})
        $candidateFolders=@($dataRoot,($appDataRoot+'\logs\data'),($appDataRoot+'\snapshots'),($appDataRoot+'\logs\system'),
            ($appDataRoot+'\logs\comm'),$electronRoot,($backendRoot+'\logs\data'),($backendRoot+'\logs\test_data'),($backendRoot+'\snapshots'))
        $folders=@(foreach($p in $candidateFolders){DirectorySummary $p})
        $backupCandidate=DirectorySummary $backupCandidateRoot
        $facts=@(foreach($name in @('spot_image_fact.csv','spot_observation_fact.csv','spot_image_linkage_fact.csv','process_phase_event_fact.csv',
            'changeover_candidate_resolution_fact.csv','spot_image_fact_manifest.final.json','spot_image_linkage_report.json')){Metadata ($dataRoot+'\'+$name)})
        $portableConfig=@(Metadata ($backendRoot+'\config.ini');Metadata ($backendRoot+'\config\config.ini');Metadata ($backendRoot+'\.env'))
        [pscustomobject]@{settings=$settings;state_files=$states;electron_profile_candidates=$profiles;directories=$folders;fact_files=$facts;
            installed_config_candidates=$portableConfig;suggested_backup_folder=$backupCandidate}|ConvertTo-Json -Depth 9
        Write-Host '[STEP 3/5] Match the last capture path to file metadata; compare selected file activity over 10 seconds.'
        $beforeCapture=RecentCapture (LocalGet 'api/spot/config')
        $follow=@($facts|Where-Object {$_.exists -and $_.kind -ceq 'file'})
        foreach($folder in $folders){if($folder.exists){$follow+=@($folder.latest_csv)}}
        $beforeCapture|ConvertTo-Json -Depth 6
        for($i=1;$i -le 2;$i++){Start-Sleep -Seconds 5;Write-Host ('[WAIT] '+($i*5)+'/10 seconds; no added image requests')}
        $fileChanges=@(foreach($prior in $follow){$now=Metadata $prior.path;[pscustomobject]@{path=$prior.path;before_bytes=$prior.bytes;after_bytes=$now.bytes;
            after_exists=$now.exists;metadata_changed=($prior.bytes -ne $now.bytes -or $prior.last_write_utc -cne $now.last_write_utc);active_writer_identity_proven=$false}})
        Write-Host '[STEP 4/5] Recheck cached paths, shared config hash, image capture and process continuity.'
        $settingsAfter=StorageSettings (LocalGet 'api/config')
        $afterCapture=RecentCapture (LocalGet 'api/spot/config')
        $configAfter=BoundedHash $configPath '6841C848A443DF91966C991707C2B21CA57C575993DCA36FACFF2592D070147E' 1048576 $true
        SameRuntime $anchor (RuntimeAnchor)
        $deltas=[ordered]@{}
        foreach($n in @('written_count','enqueued_count','dropped_count','failure_count')) {
            $delta=[long]$afterCapture.$n-[long]$beforeCapture.$n;Need ($delta -ge 0) 'capture-counter-decreased';$deltas[$n]=$delta
        }
        Write-Host '[STEP 5/5] Report candidates only. No archive contents opened, backup created or final YES.'
        [pscustomobject]@{result='V1025_STORAGE_RECOVERY_INVENTORY_REVIEW_REQUIRED';checked_at=[DateTimeOffset]::Now.ToString('o');elapsed_seconds=$storageClock.Elapsed.TotalSeconds;
            runtime=$anchor;config_before=$configBefore;config_after=$configAfter;recovery_exe=$recovery;settings_after=$settingsAfter;
            latest_capture_after=$afterCapture;capture_counter_deltas=[pscustomobject]$deltas;selected_file_changes=$fileChanges;
            disk_free_gib=[Math]::Round(([IO.DriveInfo]::new('C:\')).AvailableFreeSpace/1GB,2);
            backup_candidates=@($appDataRoot,$electronRoot);installed_data_candidates_require_review=$true;
            user_suggested_backup_location=$backupCandidateRoot;existing_backup_verified=$false;backup_candidate_on_same_volume=$true;
            active_storage_paths_fully_verified=$false;electron_profile_path_directly_observed=$false;process_environment_audited=$false;
            all_file_content_readability_verified=$false;backup_size_verified=$false;backup_destination_selected=$false;
            consistent_backup_created=$false;restore_test_performed=$false;profile_downgrade_tested=$false;installation_ready=$false;
            file_writes_performed=$false;application_restart_performed=$false;installation_started=$false;automatic_rollback_performed=$false;
            product_changes_made=$false;new_camera_requests=$false;packet_capture_started=$false;production_promotion_allowed=$false;
            limitation='Metadata only except pinned config/installer hashes. Existing files are not backups. Same SID is not a full token or process-environment audit. Paths are candidates, not exhaustive active-runtime proof. Path checks assume no hostile concurrent replacement; budgets cannot preempt a blocked OS call. Closeout, separate protected backup, restore rehearsal and destination capacity remain pending.'}|ConvertTo-Json -Depth 10
        Write-Host '[DONE] Return complete output privately. Keep app and error queue unchanged; no new files to transfer.' -ForegroundColor Green
    } catch {
        $message=$_.Exception.Message
        $safe=if($message -cmatch '^STORAGE_CHECK:[a-z0-9-]+$'){$message}else{'STORAGE_CHECK:unexpected-error-details-withheld'}
        Write-Host '[HOLD] Preserve output. No automatic retry, backup, clear, restart, install or rollback.' -ForegroundColor Yellow
        [pscustomobject]@{reason=$safe;exception_class=$_.Exception.GetType().Name;message_sha256=(TextHash $message)}|ConvertTo-Json
        throw 'Read-only storage inspection HOLD. See filtered reason above.'
    } finally {$env:PATH=$savedStoragePath;$env:PSModulePath=$savedStorageModules}
}
