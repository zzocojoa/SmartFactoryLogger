param([switch]$Execute)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $Execute) {
    Write-Host '[PREPARED ONLY] No queries, stop or writes. Separate execution approval and -Execute are required.'
    return
}

$savedPath = $env:PATH
$savedModulePath = $env:PSModulePath
$clock = [Diagnostics.Stopwatch]::StartNew()
$phase = 'host'
$workRoot = $null
$enginePin = $null
$mainProcess = $null
$backendProcess = $null
$operatorApproved = $false
$stopped = $false
$coldMode = $false
$estimatedBytes = [long]0

$engineHash = '3B8B3649C623EB8A7112C762D95A00AD9745231291C50CCC2B66E0AA2C7F8A71'
$commit = 'a203baf62b544d38072a32d71ef411c7cf8b6490'
$mainId = 13432
$mainTicks = [long]639249359473432800
$backendId = 15240
$backendTicks = [long]639249359490446273
$installRoot = 'C:\Users\user\AppData\Local\Programs\smart-factory-logger-v2'
$roamingRoot = 'C:\Users\user\AppData\Roaming'
$dataRoot = $roamingRoot + '\SmartFactoryLogger'
$profileRoot = $roamingRoot + '\smart-factory-logger-v2'
$layoutsRoot = $dataRoot + '\layouts'
$configPath = $dataRoot + '\config.ini'
$configHash = '6841C848A443DF91966C991707C2B21CA57C575993DCA36FACFF2592D070147E'
$recoveryPath = 'C:\ProgramData\SFL-76B317D0A2901C6EFC649404211C8109\SmartFactoryLogger_v1.0.25_a203baf_unsigned_internal_20260909T012500Z\smart-factory-logger-v2 Setup 1.0.25.exe'
$recoveryHash = '9EE81CD9B809275B7E49E1441CBBF11C2B7BBC1E2A372A7D7163E4DCFFE6ADA1'
$opsRoot = 'C:\ProgramData\SFLOps'
$backupParent = $opsRoot + '\backups'
$stateSpecs = [ordered]@{
    'config.ini' = $true
    'config.bak' = $true
    'config.pending.json' = $false
    'config_meta.json' = $true
    'config_cache.json' = $false
    'layout.json' = $true
    'layout.backup.json' = $true
    'operator_metadata.json' = $true
    'operator_metadata_runtime_state.json' = $true
    'state.json' = $true
}

function Need { param([bool]$OK,[string]$Code) if (-not $OK) { throw ('MINIMAL_COLD_BACKUP:' + $Code) } }
function Field {
    param([object]$Object,[string]$Name)
    Need ($Object -is [pscustomobject] -and $Object -isnot [Array]) 'object-shape'
    $property = $Object.PSObject.Properties[$Name]
    Need ($null -ne $property -and $property.Value -isnot [Array]) ('field-' + $Name)
    return ,$property.Value
}
function HashStream {
    param([IO.Stream]$Stream)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { $Stream.Position=0;return [BitConverter]::ToString($sha.ComputeHash($Stream)).Replace('-','') }
    finally { $sha.Dispose() }
}
function PlainLoaderPath {
    param([string]$Path)
    Need ($Path -cmatch '^[A-Za-z]:\\' -and $Path -notmatch '[\x00-\x1F<>"|?*~]' -and
        $Path.Substring(2) -notmatch ':') 'loader-path'
    $node = [IO.FileInfo]::new([IO.Path]::GetFullPath($Path))
    while ($null -ne $node) {
        Need (($node.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'loader-reparse'
        if ($node -is [IO.FileInfo]) { $node=$node.Directory } else { $node=$node.Parent }
    }
}
function LocalHealth {
    $request = [Net.HttpWebRequest]::Create('http://127.0.0.1:8000/health')
    $request.Method='GET';$request.Proxy=$null;$request.AllowAutoRedirect=$false
    $request.Timeout=10000;$request.ReadWriteTimeout=10000
    $response=$null;$reader=$null
    try {
        $response=$request.GetResponse();Need ([int]$response.StatusCode -eq 200) 'health-status'
        $reader=[IO.StreamReader]::new($response.GetResponseStream(),[Text.UTF8Encoding]::new($false,$true),$true)
        $text=$reader.ReadToEnd();Need ($text.Length -le 1048576 -and $text.TrimStart().StartsWith('{')) 'health-body'
        return ConvertFrom-Json -InputObject $text
    }
    finally {if($null-ne$reader){$reader.Dispose()};if($null-ne$response){$response.Dispose()}}
}
function Runtime {
    $apps=@(Get-Process -Name smart-factory -ErrorAction SilentlyContinue)
    $backends=@(Get-Process -Name SmartFactoryBackend -ErrorAction SilentlyContinue)
    $listeners=@(Get-NetTCPConnection -State Listen -ErrorAction Stop|Where-Object LocalPort -eq 8000)
    return [pscustomobject]@{apps=$apps;backends=$backends;listeners=$listeners}
}
function LiveGuard {
    $runtime=Runtime
    Need ($runtime.backends.Count -eq 1 -and $runtime.backends[0].Id -eq $backendId -and
        $runtime.backends[0].StartTime.ToUniversalTime().Ticks -eq $backendTicks -and
        $runtime.backends[0].Path -ieq ($installRoot+'\resources\backend\SmartFactoryBackend.exe')) 'backend-identity'
    $main=@($runtime.apps|Where-Object Id -eq $mainId)
    Need ($main.Count -eq 1 -and $main[0].StartTime.ToUniversalTime().Ticks -eq $mainTicks) 'main-identity'
    foreach($app in $runtime.apps){Need ($app.Path -ieq ($installRoot+'\smart-factory.exe')) 'app-path'}
    Need ($runtime.listeners.Count -gt 0 -and @($runtime.listeners|Where-Object OwningProcess -ne $backendId).Count -eq 0) 'listener-identity'
}
function ColdGuard {
    $runtime=Runtime
    Need ($runtime.apps.Count -eq 0 -and $runtime.backends.Count -eq 0 -and $runtime.listeners.Count -eq 0) 'application-not-stopped'
}
function CheckProduct {
    $health=LocalHealth
    Need ((Field $health 'app_version') -ceq '1.0.25' -and
        (Field (Field $health 'spot_temperature') 'build_git_commit') -ceq $commit) 'version-commit'
}
function CheckLiveConfig {
    for($pass=0;$pass -lt 2;$pass++) {
        [SflColdBackupV1.Engine]::Plain($configPath,$false)
        $stream=[IO.File]::Open($configPath,'Open','Read',([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
        $sha=[Security.Cryptography.SHA256]::Create()
        try {
            Need ($stream.Length -gt 0 -and $stream.Length -le 1048576) 'config-size'
            $actual=[BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-','')
            Need ($actual -ceq $configHash) 'config-pin'
        }
        finally {$sha.Dispose();$stream.Dispose()}
    }
}
function CheckStatePresence {
    $rows=[Collections.Generic.List[object]]::new()
    foreach($entry in $stateSpecs.GetEnumerator()) {
        $path=$dataRoot+'\'+$entry.Key
        [SflColdBackupV1.Engine]::Plain($path,(-not [bool]$entry.Value))
        $exists=[IO.File]::Exists($path)
        Need ($exists -eq [bool]$entry.Value) ('state-presence-'+$entry.Key.Replace('.','-'))
        if($exists) {
            [SflColdBackupV1.Engine]::OrdinaryData($path)
            $info=[IO.FileInfo]::new($path);Need ($info.Length -ge 0 -and $info.Length -le 16777216) 'state-size'
            $rows.Add([pscustomobject]@{name=$entry.Key;path=$path;bytes=[long]$info.Length;
                last_write_utc=$info.LastWriteTimeUtc.ToString('o')})
        }
    }
    return ,$rows.ToArray()
}
function LifecycleEvents {
    $events=[Collections.Generic.List[object]]::new()
    foreach($suffix in @('','.1','.2','.3')) {
        $path=$profileRoot+'\debug_electron.log'+$suffix
        if(-not [IO.File]::Exists($path)){continue}
        [SflColdBackupV1.Engine]::Plain($path,$false)
        $stream=[IO.File]::Open($path,'Open','Read',([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
        try {
            Need ($stream.Length -le 9437184) 'lifecycle-log-size'
            $bytes=New-Object byte[] ([int]$stream.Length);$offset=0
            while($offset-lt$bytes.Length){$count=$stream.Read($bytes,$offset,$bytes.Length-$offset);Need($count-gt 0)'lifecycle-log-truncated';$offset+=$count}
            $text=[Text.UTF8Encoding]::new($false,$true).GetString($bytes)
            foreach($line in $text.Split("`n")) {
                if($line -cnotmatch '^\[([0-9TZ:.+-]+)\] STARTUP (\{.*\})\r?$'){continue}
                $when=[DateTimeOffset]::Parse($Matches[1],[Globalization.CultureInfo]::InvariantCulture)
                $event=ConvertFrom-Json -InputObject $Matches[2];$kind=Field $event 'event'
                if($kind -cnotin @('backend.spawned','backend.shutdown-complete','backend.shutdown-failed')){continue}
                $session=Field $event 'session_id';Need($session-is[string])'lifecycle-session'
                if(-not $session.StartsWith(($mainId.ToString()+'-'),[StringComparison]::Ordinal)){continue}
                $events.Add([pscustomobject]@{at=$when;event=$kind;session=$session;payload=(Field $event 'payload')})
                Need ($events.Count -le 1000) 'lifecycle-event-limit'
            }
        }
        finally {$stream.Dispose()}
    }
    return ,$events.ToArray()
}
function ShutdownProof {
    param([object[]]$Events,[string]$Session,[DateTimeOffset]$After)
    $fresh=@($Events|Where-Object {$_.session-ceq$Session -and $_.at-ge$After -and $_.at-le[DateTimeOffset]::Now})
    Need (@($fresh|Where-Object event -CEQ 'backend.shutdown-failed').Count -eq 0) 'shutdown-failed-event'
    $complete=@($fresh|Where-Object event -CEQ 'backend.shutdown-complete')
    Need ($complete.Count -eq 1) 'shutdown-complete-not-unique'
    $payload=$complete[0].payload
    Need ([long](Field $payload 'pid') -eq $backendId -and (Field $payload 'reason') -cin @('close','already_exited') -and
        [long](Field $payload 'exit_code') -eq 0 -and $null -eq (Field $payload 'signal_code')) 'shutdown-event-result'
    $forced=Field $payload 'forced';Need($forced-is[bool]-and-not$forced)'forced-shutdown'
    return [pscustomobject]@{at=$complete[0].at.ToString('o');session=$Session;backend_pid=$backendId;exit_code=0;forced=$false}
}
function NewPrivateAcl {
    $acl=[Security.AccessControl.DirectorySecurity]::new();$acl.SetAccessRuleProtection($true,$false)
    $acl.SetOwner([Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))
    foreach($sid in @('S-1-5-32-544','S-1-5-18')) {
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
            [Security.Principal.SecurityIdentifier]::new($sid),'FullControl','ContainerInherit,ObjectInherit','None','Allow'))
    }
    return $acl
}
function CheckPrivateAcl {
    param([string]$Path)
    [SflColdBackupV1.Engine]::Plain($Path,$false)
    $acl=[IO.Directory]::GetAccessControl($Path)
    Need ($acl.AreAccessRulesProtected -and
        $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -ceq 'S-1-5-32-544') 'private-acl-owner'
    $rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]));Need($rules.Count-eq 2)'private-acl-count'
    $seen=@{}
    foreach($rule in $rules) {
        $sid=$rule.IdentityReference.Value
        Need ($sid-cin@('S-1-5-32-544','S-1-5-18') -and -not$seen.ContainsKey($sid) -and -not$rule.IsInherited -and
            $rule.AccessControlType-eq'Allow' -and $rule.FileSystemRights-eq'FullControl' -and
            $rule.InheritanceFlags-eq'ContainerInherit,ObjectInherit' -and $rule.PropagationFlags-eq'None') 'private-acl-rule'
        $seen[$sid]=$true
    }
}
function CheckOpsRoot {
    [SflColdBackupV1.Engine]::Plain($opsRoot,$false)
    Need ([IO.Directory]::Exists($opsRoot)) 'sflops-root-missing'
    $acl=[IO.Directory]::GetAccessControl($opsRoot)
    $owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value
    Need ($owner-cin@('S-1-5-18','S-1-5-32-544')) 'sflops-owner'
    foreach($rule in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])) {
        $mask=[Security.AccessControl.FileSystemRights]::Write -bor [Security.AccessControl.FileSystemRights]::Modify -bor
            [Security.AccessControl.FileSystemRights]::FullControl
        Need (-not($rule.AccessControlType-eq'Allow' -and $rule.IdentityReference.Value-cin@('S-1-1-0','S-1-5-11','S-1-5-32-545') -and
            ($rule.FileSystemRights-band$mask)-ne 0)) 'sflops-broad-write'
    }
}
function NewProtectedDirectory {
    param([string]$Path)
    [SflColdBackupV1.Engine]::Plain($Path,$true)
    Need (-not[IO.Directory]::Exists($Path)-and-not[IO.File]::Exists($Path)) 'protected-path-exists'
    [void][IO.Directory]::CreateDirectory($Path,(NewPrivateAcl));CheckPrivateAcl $Path
}
function EnsureBackupParent {
    CheckOpsRoot
    if([IO.Directory]::Exists($backupParent)){CheckPrivateAcl $backupParent;return}
    Need (-not[IO.File]::Exists($backupParent)) 'backup-parent-file'
    NewProtectedDirectory $backupParent
}
function WriteNewJson {
    param([string]$Name,[object]$Value)
    Need ($Name-cin@('intent.json','state-map.json','result.json','hold.json')) 'receipt-name'
    CheckPrivateAcl $workRoot
    $path=$workRoot+'\'+$Name;$bytes=[Text.UTF8Encoding]::new($false).GetBytes(($Value|ConvertTo-Json -Depth 10))
    $stream=[IO.File]::Open($path,'CreateNew','Write','None')
    try{$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
    $hash=[SflColdBackupV1.Engine]::FileHash($path,16777216)
    $stream=[IO.File]::Open($path+'.sha256.txt','CreateNew','Write','None')
    try{$bytes=[Text.Encoding]::ASCII.GetBytes($hash+"`n");$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
    return $hash
}
function CopyStateFiles {
    param([string]$Destination)
    [SflColdBackupV1.Engine]::Plain($Destination,$true)
    Need (-not[IO.Directory]::Exists($Destination)-and-not[IO.File]::Exists($Destination)) 'state-source-exists'
    [void][IO.Directory]::CreateDirectory($Destination)
    $rows=[Collections.Generic.List[object]]::new()
    foreach($entry in $stateSpecs.GetEnumerator()) {
        $source=$dataRoot+'\'+$entry.Key;$exists=[IO.File]::Exists($source)
        Need ($exists-eq[bool]$entry.Value) ('cold-state-presence-'+$entry.Key.Replace('.','-'))
        if(-not$exists){continue}
        [SflColdBackupV1.Engine]::OrdinaryData($source)
        $target=$Destination+'\'+$entry.Key
        [SflColdBackupV1.Engine]::Plain($target,$true)
        [IO.File]::Copy($source,$target,$false)
        $sourceHash=[SflColdBackupV1.Engine]::FileHash($source,16777216)
        $targetHash=[SflColdBackupV1.Engine]::FileHash($target,16777216)
        Need ($sourceHash-ceq$targetHash) 'state-copy-hash'
        $info=[IO.FileInfo]::new($source)
        $sddl=[IO.File]::GetAccessControl($source,[Security.AccessControl.AccessControlSections]::Owner -bor
            [Security.AccessControl.AccessControlSections]::Group -bor [Security.AccessControl.AccessControlSections]::Access).
            GetSecurityDescriptorSddlForm([Security.AccessControl.AccessControlSections]::Owner -bor
                [Security.AccessControl.AccessControlSections]::Group -bor [Security.AccessControl.AccessControlSections]::Access)
        $rows.Add([pscustomobject]@{name=$entry.Key;source=$source;staged=$target;bytes=[long]$info.Length;sha256=$sourceHash;
            creation_utc_ticks=$info.CreationTimeUtc.Ticks;last_write_utc_ticks=$info.LastWriteTimeUtc.Ticks;
            attributes=[int]$info.Attributes;source_sddl=$sddl})
    }
    Need ($rows.Count -eq 8) 'state-copy-count'
    return ,$rows.ToArray()
}
function RecheckOriginalStates {
    param([object[]]$Rows)
    foreach($row in $Rows) {
        Need ([IO.File]::Exists($row.source) -and
            [SflColdBackupV1.Engine]::FileHash($row.source,16777216)-ceq$row.sha256) 'original-state-drift'
    }
}

try {
    $native=[IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
    $principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
    Need ([Environment]::Is64BitProcess -and $PSVersionTable.PSEdition-ceq'Desktop' -and
        $PSVersionTable.PSVersion.Major-eq 5 -and $PSVersionTable.PSVersion.Minor-eq 1 -and
        [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName-ieq$native -and
        $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) 'native-admin-ps51-required'
    Need ($env:APPDATA-ieq$roamingRoot) 'operator-profile'
    $env:PATH=[Environment]::SystemDirectory+';'+[IO.Path]::GetDirectoryName($native)
    $env:PSModulePath=[IO.Path]::GetDirectoryName($native)+'\Modules'
    $enginePath=Join-Path $PSScriptRoot 'cold-backup-core.dll';PlainLoaderPath $enginePath
    $enginePin=[IO.File]::Open($enginePath,'Open','Read','Read')
    Need ($enginePin.Length-gt 0 -and $enginePin.Length-le 131072 -and (HashStream $enginePin)-ceq$engineHash) 'engine-pin'
    $engineBytes=New-Object byte[] ([int]$enginePin.Length);$enginePin.Position=0;$offset=0
    while($offset-lt$engineBytes.Length){$read=$enginePin.Read($engineBytes,$offset,$engineBytes.Length-$offset);Need($read-gt 0)'engine-truncated';$offset+=$read}
    [void][Reflection.Assembly]::Load($engineBytes)

    Write-Host '[STEP 1/7] Verify exact v1.0.25 runtime, config, recovery and preflight scope. No shutdown yet.' -ForegroundColor Cyan
    LiveGuard;CheckProduct;CheckLiveConfig;CheckOpsRoot
    foreach($processId in @($mainId,$backendId)) {
        $cim=Get-CimInstance Win32_Process -Filter ('ProcessId = '+$processId)
        if($processId-eq$backendId){Need($cim.ParentProcessId-eq$mainId)'backend-parent'}
        $owner=Invoke-CimMethod -InputObject $cim -MethodName GetOwnerSid
        Need($owner.ReturnValue-eq 0 -and $owner.Sid-ceq[Security.Principal.WindowsIdentity]::GetCurrent().User.Value)'process-user'
    }
    $stateBefore=CheckStatePresence
    Need ([SflColdBackupV1.Engine]::FileHash($recoveryPath,536870912)-ceq$recoveryHash) 'recovery-pin'
    $spawn=@((LifecycleEvents)|Where-Object {$_.event-ceq'backend.spawned' -and [long](Field $_.payload 'pid')-eq$backendId -and
        [Math]::Abs(($_.at.UtcDateTime.Ticks-$backendTicks)/10000000.0)-le 120})
    Need ($spawn.Count-eq 1) 'runtime-session-not-unique';$runtimeSession=$spawn[0].session

    Write-Host '[STEP 2/7] Inventory selected profile/layout trees and capacity. File contents are not copied yet.' -ForegroundColor Cyan
    $guard=[Action]{if($coldMode){ColdGuard}else{LiveGuard}}
    $progressPhase='';$phaseClock=[Diagnostics.Stopwatch]::StartNew()
    $progress=[Action[string,long,long,long]]{param($name,$done,$count,$millis)
        if($script:progressPhase-cne$name){$script:progressPhase=$name;$script:phaseClock.Restart()}
        $total=if($name-ceq'source-and-restored-verification'){$estimatedBytes*2}else{$estimatedBytes}
        $percent=if($total-gt 0){[Math]::Min(99,[Math]::Round(100.0*$done/$total,1))}else{0}
        Write-Host ('[PROGRESS] phase='+$name+' elapsed='+$clock.Elapsed.ToString('hh\:mm\:ss')+' files='+$count+' bytes='+$done+' percent~='+$percent+'%; no image requests')
    }
    $liveEngine=[SflColdBackupV1.Engine]::new([string[]]@($profileRoot,$layoutsRoot),$guard,$progress)
    $prospective=$backupParent+'\v1025-min-YYYYMMDD-HHMMSS-12345678'
    $liveInventory=$liveEngine.Inventory($prospective+'\restore')
    $stateBytes=[long](($stateBefore|Measure-Object bytes -Sum).Sum)
    $estimatedBytes=[long]$liveInventory.Bytes+$stateBytes
    $required=[SflColdBackupV1.Engine]::RequiredSpace($estimatedBytes,($liveInventory.Files+$liveInventory.Directories+$stateBefore.Count+1))
    $drive=[IO.DriveInfo]::new('C:\')
    Need($drive.DriveType-eq'Fixed' -and $drive.DriveFormat-ceq'NTFS' -and $drive.AvailableFreeSpace-ge$required)'insufficient-space-before-shutdown'
    Write-Host ('[SCOPE] files~='+($liveInventory.Files+$stateBefore.Count)+' bytes~='+$estimatedBytes+' required_GiB='+[Math]::Round($required/1GB,2)+' free_GiB='+[Math]::Round($drive.AvailableFreeSpace/1GB,2))
    Write-Host '[EXCLUDED] CSV, images, fact/diagnostic logs, snapshots and installed program directory are NOT backed up.' -ForegroundColor Yellow
    Write-Host '[ACTION] The app will remain stopped after completion. Type the token only during an approved maintenance window.' -ForegroundColor Yellow
    $answer=Read-Host 'Type BACKUP MINIMAL V1.0.25 to approve a new protected backup, restore rehearsal and manual normal shutdown'
    Need($answer-ceq'BACKUP MINIMAL V1.0.25')'operator-not-approved';$operatorApproved=$true

    Write-Host '[STEP 3/7] Recheck live identity, create a new protected destination, then request normal shutdown.' -ForegroundColor Cyan
    LiveGuard;CheckProduct;CheckLiveConfig;[void](CheckStatePresence)
    $mainProcess=Get-Process -Id $mainId;$backendProcess=Get-Process -Id $backendId
    $null=$mainProcess.Handle;$null=$backendProcess.Handle
    EnsureBackupParent
    $workRoot=$backupParent+'\v1025-min-'+[DateTimeOffset]::Now.ToString('yyyyMMdd-HHmmss')+'-'+[Guid]::NewGuid().ToString('N').Substring(0,8)
    Need($workRoot-cmatch'^C:\\ProgramData\\SFLOps\\backups\\v1025-min-[0-9]{8}-[0-9]{6}-[a-f0-9]{8}$')'work-root-pattern'
    NewProtectedDirectory $workRoot
    $intentAt=[DateTimeOffset]::Now
    $intentHash=WriteNewJson 'intent.json' ([ordered]@{schema_version='v1025-minimal-cold-backup-intent-v1';recorded_at=$intentAt.ToString('o');
        product_version='1.0.25';product_commit=$commit;destination=$workRoot;selected_profile=$profileRoot;selected_layouts=$layoutsRoot;
        selected_state_files=@($stateSpecs.Keys);excluded=@('SmartFactoryLogger\logs','SmartFactoryLogger\snapshots',$installRoot);
        live_inventory=$liveInventory;estimated_state_files=$stateBefore;required_bytes=$required;operator_token_accepted=$true;
        installation_authorized=$false;automatic_restart_authorized=$false})
    Write-Host '[ACTION REQUIRED] Close SmartFactory normally using its window X NOW. Do not use Task Manager, taskkill or Stop-Process.' -ForegroundColor Cyan
    $phase='manual-normal-shutdown';$wait=[Diagnostics.Stopwatch]::StartNew()
    while($true){
        $runtime=Runtime
        if($runtime.apps.Count-eq 0 -and $runtime.backends.Count-eq 0 -and $runtime.listeners.Count-eq 0){break}
        Need($wait.Elapsed.TotalSeconds-lt 300)'shutdown-timeout'
        Write-Host ('[SHUTDOWN WAIT] elapsed='+[int]$wait.Elapsed.TotalSeconds+'s / 300s apps='+$runtime.apps.Count+' backend='+$runtime.backends.Count+' listeners='+$runtime.listeners.Count)
        Start-Sleep -Seconds 5
    }
    Need($mainProcess.WaitForExit(0)-and$backendProcess.WaitForExit(0))'pinned-process-still-running'
    Need($mainProcess.ExitCode-eq 0 -and $backendProcess.ExitCode-eq 0)'nonzero-process-exit'
    $coldMode=$true;$stopped=$true;ColdGuard
    $shutdown=ShutdownProof (LifecycleEvents) $runtimeSession $intentAt

    Write-Host '[STEP 4/7] Snapshot only the fixed state files, then bind the stopped source inventory.' -ForegroundColor Cyan
    Need([SflColdBackupV1.Engine]::FileHash($configPath,1048576)-ceq$configHash)'config-changed-at-shutdown'
    $stateSource=$workRoot+'\state-source';$stateRows=CopyStateFiles $stateSource
    $stateMapHash=WriteNewJson 'state-map.json' ([ordered]@{schema_version='v1025-minimal-state-map-v1';files=$stateRows;
        original_files_overwritten=$false;original_files_deleted=$false})
    $engine=[SflColdBackupV1.Engine]::new([string[]]@($profileRoot,$layoutsRoot,$stateSource),$guard,$progress)
    $coldInventory=$engine.Inventory($workRoot+'\restore');$estimatedBytes=$coldInventory.Bytes
    $coldRequired=[SflColdBackupV1.Engine]::RequiredSpace($estimatedBytes,($coldInventory.Files+$coldInventory.Directories))
    Need($drive.AvailableFreeSpace-ge$coldRequired)'insufficient-space-after-shutdown'

    $phase='backup-copy';Write-Host '[STEP 5/7] Copy stopped selected sources and create a file-by-file SHA256 manifest.' -ForegroundColor Cyan
    CheckPrivateAcl $workRoot;ColdGuard
    $backup=$engine.Backup($workRoot+'\backup',$workRoot+'\files.manifest.tsv')
    Need($backup.Files-eq$coldInventory.Files -and $backup.Directories-eq$coldInventory.Directories -and
        $backup.Bytes-eq$coldInventory.Bytes)'cold-inventory-drift'

    $phase='restore-copy';Write-Host '[STEP 6/7] Reopen the backup and restore into a separate rehearsal tree; verify all hashes.' -ForegroundColor Cyan
    $restored=$engine.Verify($workRoot+'\files.manifest.tsv',$backup.ManifestSha256,$workRoot+'\backup',$workRoot+'\restore',$true)
    $verified=$engine.Verify($workRoot+'\files.manifest.tsv',$backup.ManifestSha256,$workRoot+'\restore',$null,$false)
    RecheckOriginalStates $stateRows;ColdGuard;CheckPrivateAcl $workRoot

    $phase='completion-receipt';Write-Host '[STEP 7/7] Publish completion receipt. The app remains stopped; no installation starts.' -ForegroundColor Cyan
    $result=[ordered]@{schema_version='v1025-minimal-cold-backup-result-v1';result='V1025_MINIMAL_COLD_BACKUP_AND_FILE_RESTORE_VERIFIED';
        recorded_at=[DateTimeOffset]::Now.ToString('o');elapsed_seconds=$clock.Elapsed.TotalSeconds;product_version='1.0.25';product_commit=$commit;
        backup_root=($workRoot+'\backup');restore_rehearsal_root=($workRoot+'\restore');intent_sha256=$intentHash;state_map_sha256=$stateMapHash;
        source_file_count=$backup.Files;source_directory_count=$backup.Directories;source_bytes=$backup.Bytes;manifest_sha256=$backup.ManifestSha256;
        config_sha256=$configHash;recovery_installer_sha256=$recoveryHash;main_exit_code=$mainProcess.ExitCode;backend_exit_code=$backendProcess.ExitCode;
        shutdown_event=$shutdown;app_still_stopped=$true;backup_readback_verified=$true;restored_file_hashes_verified=$true;
        source_hashes_rechecked=$true;exact_membership_verified=$true;original_state_hashes_rechecked=$true;
        excluded_business_data=@('SmartFactoryLogger\logs','SmartFactoryLogger\snapshots');installed_program_directory_backed_up=$false;
        source_files_overwritten=$false;source_files_deleted=$false;automatic_restart_performed=$false;installation_started=$false;
        application_restore_test_performed=$false;profile_downgrade_tested=$false;alternate_data_streams_rejected=$true;
        same_volume_only=$true;encrypted_backup=$false;installation_ready=$false;production_promotion_allowed=$false;
        limitation='Minimal same-volume cold byte backup only. Accumulated CSV/image/fact data is excluded and not recoverable from this backup. Restore rehearsal is file-level, not application startup or rollback proof.'}
    $resultHash=WriteNewJson 'result.json' $result
    Write-Host ('[RESULT] '+$workRoot+'\result.json');Write-Host ('[SHA256] '+$resultHash);Write-Host ('[MANIFEST SHA256] '+$backup.ManifestSha256)
    Write-Host '[COMPLETE] Minimal backup verified. APP REMAINS STOPPED. Return output; do not start installation yet.' -ForegroundColor Green
}
catch {
    $exception=$_.Exception;$reason='details-withheld'
    while($null-ne$exception){if($exception.Message-cmatch'MINIMAL_COLD_BACKUP:([a-z0-9.-]+)'){$reason=$Matches[1];break};
        if($exception.Message-cmatch'COLD_BACKUP:([a-z0-9.-]+)'){$reason=$Matches[1];break};$exception=$exception.InnerException}
    Write-Host ('[HOLD] phase='+$phase+' reason='+$reason+' elapsed='+$clock.Elapsed.ToString('hh\:mm\:ss')) -ForegroundColor Yellow
    if($null-ne$workRoot){Write-Host('[PRESERVE] '+$workRoot);try{[void](WriteNewJson 'hold.json' @{result='HOLD';phase=$phase;reason=$reason;
        recorded_at=[DateTimeOffset]::Now.ToString('o');operator_token_accepted=$operatorApproved;stopped_confirmed=$stopped;
        installation_ready=$false;partial_files_preserved=$true})}catch{Write-Host '[HOLD] Receipt write failed; preserve console and partial files.'}}
    Write-Host '[HOLD] No automatic retry, cleanup, force-stop, restart, restore over originals or installation. If closed, keep the app stopped.'
    throw 'MINIMAL_COLD_BACKUP_HOLD: See the sanitized phase and reason above.'
}
finally {
    if($null-ne$enginePin){$enginePin.Dispose()}
    if($null-ne$mainProcess){$mainProcess.Dispose()};if($null-ne$backendProcess){$backendProcess.Dispose()}
    $env:PATH=$savedPath;$env:PSModulePath=$savedModulePath
}
