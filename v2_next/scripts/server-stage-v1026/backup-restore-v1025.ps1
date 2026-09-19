param([switch]$Execute)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
# Prepared helper only; execution needs a separate user authorization plus token.
if(-not $Execute){Write-Host '[PREPARED ONLY] No queries or writes. Separate execution approval and -Execute are required.';return}
$savedBackupPath=$env:PATH;$savedBackupModules=$env:PSModulePath
$workRoot=$null;$phase='host';$stopped=$false;$answerAccepted=$false
$clock=[Diagnostics.Stopwatch]::StartNew();$enginePin=$null;$mainProcess=$null;$backendProcess=$null
$expectedEngine='3B8B3649C623EB8A7112C762D95A00AD9745231291C50CCC2B66E0AA2C7F8A71'
$install='C:\Users\user\AppData\Local\Programs\smart-factory-logger-v2'
$data='C:\Users\user\AppData\Roaming\SmartFactoryLogger'
$profile='C:\Users\user\AppData\Roaming\smart-factory-logger-v2'
$config=$data+'\config.ini'
$recovery='C:\ProgramData\SFL-76B317D0A2901C6EFC649404211C8109\SmartFactoryLogger_v1.0.25_a203baf_unsigned_internal_20260909T012500Z\smart-factory-logger-v2 Setup 1.0.25.exe'
$configHash='6841C848A443DF91966C991707C2B21CA57C575993DCA36FACFF2592D070147E'
$recoveryHash='9EE81CD9B809275B7E49E1441CBBF11C2B7BBC1E2A372A7D7163E4DCFFE6ADA1'
$commit='a203baf62b544d38072a32d71ef411c7cf8b6490'
$rootPaths=[string[]]@($data,$profile,$install)
$coldMode=$false;$estimatedBytes=[long]0;$closeoutFactBytes=[long]0

function Need {param([bool]$OK,[string]$Code) if(-not $OK){throw ('COLD_BACKUP:'+ $Code)}}
function Field {
    param([object]$Object,[string]$Name)
    Need ($Object -is [pscustomobject] -and $Object -isnot [Array]) 'object-shape'
    $p=$Object.PSObject.Properties[$Name]
    Need ($null -ne $p -and $p.Value -isnot [Array]) 'required-field'
    return ,$p.Value
}
function CountValue {
    param([object]$Object,[string]$Name)
    $v=Field $Object $Name
    Need (($v -is [int] -or $v -is [long]) -and $v -ge 0) 'counter-shape'
    return [long]$v
}
function HashStream {
    param([IO.Stream]$Stream)
    $s=[Security.Cryptography.SHA256]::Create()
    try {$Stream.Position=0;return [BitConverter]::ToString($s.ComputeHash($Stream)).Replace('-','')}
    finally {$s.Dispose()}
}
function Plain {
    param([string]$Path)
    # Loader bootstrap does not depend on the yet-unloaded assembly.
    Need ($Path -cmatch '^[A-Za-z]:\\' -and $Path -notmatch '[\x00-\x1F<>"|?*~]' -and $Path.Substring(2) -notmatch ':') 'loader-path'
    $node=[IO.FileInfo]::new([IO.Path]::GetFullPath($Path));$ancestors=[Collections.Generic.List[string]]::new()
    while($null -ne $node){$ancestors.Add($node.FullName);if($node -is [IO.FileInfo]){$node=$node.Directory}else{$node=$node.Parent}}
    for($i=$ancestors.Count-1;$i -ge 0;$i--){Need (([IO.File]::GetAttributes($ancestors[$i]) -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'reparse-path'}
}
function LocalGet {
    param([string]$Endpoint)
    Need ($Endpoint -cin @('health','api/config','api/spot/config')) 'endpoint-rejected'
    $r=[Net.HttpWebRequest]::Create('http://127.0.0.1:8000/'+$Endpoint)
    $r.Method='GET';$r.Proxy=$null;$r.AllowAutoRedirect=$false;$r.Timeout=10000;$r.ReadWriteTimeout=10000
    $response=$null;$stream=$null;$buffer=[IO.MemoryStream]::new()
    try {
        $response=$r.GetResponse();Need ([int]$response.StatusCode -eq 200) 'http-status'
        $stream=$response.GetResponseStream();$chunk=New-Object byte[] 8192;$budget=[Diagnostics.Stopwatch]::StartNew()
        while(($n=$stream.Read($chunk,0,$chunk.Length)) -gt 0){Need ($buffer.Length+$n -le 2097152 -and $budget.Elapsed.TotalSeconds -le 20) 'response-budget';$buffer.Write($chunk,0,$n)}
        $text=[Text.UTF8Encoding]::new($false,$true).GetString($buffer.ToArray())
        Need ($text.TrimStart().StartsWith('{')) 'json-root'
        return ConvertFrom-Json -InputObject $text
    }finally{if($null -ne $stream){$stream.Dispose()};if($null -ne $response){$response.Dispose()};$buffer.Dispose()}
}
function Runtime {
    $apps=@(Get-Process -Name smart-factory -ErrorAction SilentlyContinue)
    $backends=@(Get-Process -Name SmartFactoryBackend -ErrorAction SilentlyContinue)
    $listeners=@(Get-NetTCPConnection -State Listen -ErrorAction Stop|Where-Object LocalPort -eq 8000)
    return [pscustomobject]@{apps=$apps;backends=$backends;listeners=$listeners}
}
function LiveGuard {
    $r=Runtime
    Need ($r.backends.Count -eq 1 -and $r.backends[0].Id -eq 7620 -and
        $r.backends[0].StartTime.ToUniversalTime().Ticks -eq 639245234936285878 -and
        $r.backends[0].Path -ieq ($install+'\resources\backend\SmartFactoryBackend.exe')) 'backend-identity'
    $main=@($r.apps|Where-Object Id -eq 6728)
    Need ($main.Count -eq 1 -and $main[0].StartTime.ToUniversalTime().Ticks -eq 639245234920357237) 'main-identity'
    foreach($app in $r.apps){Need ($app.Path -ieq ($install+'\smart-factory.exe')) 'app-path'}
    Need ($r.listeners.Count -gt 0 -and @($r.listeners|Where-Object OwningProcess -ne 7620).Count -eq 0) 'listener-identity'
}
function ColdGuard {
    $r=Runtime
    Need ($r.apps.Count -eq 0 -and $r.backends.Count -eq 0 -and $r.listeners.Count -eq 0) 'application-not-stopped'
}
function CheckSettings {
    $h=LocalGet 'health'
    Need ((Field $h 'app_version') -ceq '1.0.25' -and (Field (Field $h 'spot_temperature') 'build_git_commit') -ceq $commit) 'version-commit'
    $cfg=LocalGet 'api/config';$values=Field $cfg 'values';$settings=Field $values 'settings'
    Need (([string](Field $cfg 'config_path')).Replace('/','\') -ieq $config) 'config-path'
    Need (([string](Field $settings 'logpath')).Replace('/','\') -ieq ($data+'\logs\test_data') -and
        ([string](Field $settings 'snapshotpath')).Replace('/','\') -ieq ($data+'\snapshots')) 'storage-paths'
    $restart=Field $cfg 'restart_required';Need ($restart -is [bool] -and -not $restart) 'pending-restart'
    $imageCapture=Field (Field $values 'spot') 'image_capture'
    Need ((Field $imageCapture 'path') -ceq 'spot_images') 'capture-path'
    $spot=LocalGet 'api/spot/config';$capture=Field $spot 'image_capture'
    $enabled=Field $capture 'enabled';Need ($enabled -is [bool] -and $enabled) 'capture-disabled'
    $mode=Field $capture 'mode';Need ($mode -is [string] -and $mode -cin @('all','interval','event')) 'capture-mode'
    Need ((CountValue $capture 'failure_count') -eq 0) 'capture-failure-needs-review'
    return [pscustomobject]@{checked_at=[DateTimeOffset]::Now.ToString('o');mode=$mode;
        written=(CountValue $capture 'written_count');enqueued=(CountValue $capture 'enqueued_count');rows=(CountValue $capture 'fact_row_count');
        dropped=(CountValue $capture 'dropped_count');failure=(CountValue $capture 'failure_count');queue=(CountValue $capture 'queue_size')}
}
function CheckLiveConfig {
    # Two fresh bounded shared reads; no write/delete lock against the live app.
    for($pass=0;$pass -lt 2;$pass++){
        [SflColdBackupV1.Engine]::Plain($config,$false)
        $s=[IO.File]::Open($config,'Open','Read',([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
        $sha=[Security.Cryptography.SHA256]::Create()
        try{
            Need ($s.Length -gt 0 -and $s.Length -le 1048576) 'live-config-size'
            $b=New-Object byte[] ([int]$s.Length);$offset=0
            while($offset -lt $b.Length){$n=$s.Read($b,$offset,$b.Length-$offset);Need ($n -gt 0) 'live-config-truncated';$offset+=$n}
            Need ($s.Length -eq $b.Length -and [BitConverter]::ToString($sha.ComputeHash($b)).Replace('-','') -ceq $configHash) 'live-config-pin'
        }finally{$sha.Dispose();$s.Dispose()}
    }
}
function ReadSmallJson {
    param([string]$Path)
    [SflColdBackupV1.Engine]::Plain($Path,$false)
    $s=[IO.File]::Open($Path,'Open','Read','Read')
    try {Need ($s.Length -gt 0 -and $s.Length -le 1048576) 'json-size';$b=New-Object byte[] ([int]$s.Length);$offset=0
        while($offset -lt $b.Length){$n=$s.Read($b,$offset,$b.Length-$offset);Need ($n -gt 0) 'json-truncated';$offset+=$n}
        $text=[Text.UTF8Encoding]::new($false,$true).GetString($b);if($text.Length -gt 0 -and [int]$text[0] -eq 0xFEFF){$text=$text.Substring(1)}
        Need ($text.TrimStart().StartsWith('{')) 'json-root';return ConvertFrom-Json -InputObject $text
    }finally{$s.Dispose()}
}
function LifecycleEvents {
    # Read only the four fixed rotating Electron logs, with shared bounded reads.
    # Never print raw lines (they may contain arguments or user paths).
    $events=[Collections.Generic.List[object]]::new()
    foreach($suffix in @('','.1','.2','.3')){
        $p=$profile+'\debug_electron.log'+$suffix
        if(-not [IO.File]::Exists($p)){continue}
        [SflColdBackupV1.Engine]::Plain($p,$false)
        $s=[IO.File]::Open($p,'Open','Read',([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
        try{
            Need ($s.Length -le 9437184) 'lifecycle-log-size'
            $b=New-Object byte[] ([int]$s.Length);$offset=0
            while($offset -lt $b.Length){$n=$s.Read($b,$offset,$b.Length-$offset);Need ($n -gt 0) 'lifecycle-log-truncated';$offset+=$n}
            $text=[Text.UTF8Encoding]::new($false,$true).GetString($b)
            foreach($line in $text.Split("`n")){
                if($line -cnotmatch '^\[([0-9TZ:.+-]+)\] STARTUP (\{.*\})\r?$'){continue}
                $when=[DateTimeOffset]::Parse($Matches[1],[Globalization.CultureInfo]::InvariantCulture)
                $event=ConvertFrom-Json -InputObject $Matches[2]
                $kind=Field $event 'event'
                if($kind -cnotin @('backend.spawned','backend.shutdown-complete','backend.shutdown-failed')){continue}
                $session=Field $event 'session_id';Need ($session -is [string]) 'lifecycle-session-type'
                if(-not $session.StartsWith('6728-',[StringComparison]::Ordinal)){continue}
                $events.Add([pscustomobject]@{at=$when;event=$kind;session=$session;payload=(Field $event 'payload')})
                Need ($events.Count -le 1000) 'lifecycle-event-limit'
            }
        }finally{$s.Dispose()}
    }
    return ,$events.ToArray()
}
function ShutdownProof {
    param([object[]]$Events,[string]$Session,[DateTimeOffset]$After)
    $fresh=@($Events|Where-Object {$_.session -ceq $Session -and $_.at -ge $After -and $_.at -le [DateTimeOffset]::Now})
    Need (@($fresh|Where-Object event -CEQ 'backend.shutdown-failed').Count -eq 0) 'shutdown-failed-event'
    $complete=@($fresh|Where-Object event -CEQ 'backend.shutdown-complete')
    Need ($complete.Count -eq 1) 'shutdown-complete-not-unique'
    $p=$complete[0].payload
    Need ((CountValue $p 'pid') -eq 7620 -and (Field $p 'reason') -cin @('close','already_exited') -and
        (CountValue $p 'exit_code') -eq 0 -and $null -eq (Field $p 'signal_code')) 'shutdown-event-result'
    $forced=Field $p 'forced';Need ($forced -is [bool] -and -not $forced) 'forced-shutdown'
    return [pscustomobject]@{at=$complete[0].at.ToString('o');session=$Session;backend_pid=7620;exit_code=0;forced=$false}
}
function CheckAcl {
    param([string]$Path)
    [SflColdBackupV1.Engine]::Plain($Path,$false)
    $acl=[IO.Directory]::GetAccessControl($Path)
    Need ($acl.AreAccessRulesProtected -and $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -ceq 'S-1-5-32-544') 'backup-owner-protection'
    $rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]));Need ($rules.Count -eq 2) 'backup-acl-count'
    $seen=@{}
    foreach($r in $rules){$sid=$r.IdentityReference.Value
        Need ($sid -cin @('S-1-5-32-544','S-1-5-18') -and -not $seen.ContainsKey($sid) -and -not $r.IsInherited -and
            $r.AccessControlType -eq 'Allow' -and $r.FileSystemRights -eq 'FullControl' -and
            $r.InheritanceFlags -eq 'ContainerInherit,ObjectInherit' -and $r.PropagationFlags -eq 'None') 'backup-acl-rule';$seen[$sid]=$true}
}
function NewProtectedRoot {
    param([string]$Path)
    Need ($Path -cmatch '^C:\\ProgramData\\SFL26B-[a-f0-9]{32}$') 'backup-root-pattern'
    [SflColdBackupV1.Engine]::Plain($Path,$true)
    Need (-not [IO.Directory]::Exists($Path) -and -not [IO.File]::Exists($Path)) 'backup-root-exists'
    $acl=[Security.AccessControl.DirectorySecurity]::new();$acl.SetAccessRuleProtection($true,$false)
    $acl.SetOwner([Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))
    foreach($sid in @('S-1-5-32-544','S-1-5-18')){$acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
        [Security.Principal.SecurityIdentifier]::new($sid),'FullControl','ContainerInherit,ObjectInherit','None','Allow'))}
    [void][IO.Directory]::CreateDirectory($Path,$acl);CheckAcl $Path
}
function WriteNewJson {
    param([string]$Name,[object]$Value)
    Need ($Name -cin @('intent.json','result.json','hold.json')) 'receipt-name'
    CheckAcl $workRoot;$p=$workRoot+'\'+$Name
    $bytes=[Text.UTF8Encoding]::new($false).GetBytes(($Value|ConvertTo-Json -Depth 10))
    $s=[IO.File]::Open($p,'CreateNew','Write','None');try{$s.Write($bytes,0,$bytes.Length);$s.Flush($true)}finally{$s.Dispose()}
    $hash=[SflColdBackupV1.Engine]::FileHash($p,1048576)
    $s=[IO.File]::Open($p+'.sha256.txt','CreateNew','Write','None')
    try{$bytes=[Text.Encoding]::ASCII.GetBytes($hash+"`n");$s.Write($bytes,0,$bytes.Length);$s.Flush($true)}finally{$s.Dispose()}
    return $hash
}

try {
    $native=[IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
    $principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
    Need ([Environment]::Is64BitProcess -and $PSVersionTable.PSEdition -ceq 'Desktop' -and $PSVersionTable.PSVersion.Major -eq 5 -and
        $PSVersionTable.PSVersion.Minor -eq 1 -and [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName -ieq $native -and
        $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) 'native-admin-ps51-required'
    Need ($env:APPDATA -ieq 'C:\Users\user\AppData\Roaming') 'operator-profile'
    $env:PATH=[Environment]::SystemDirectory+';'+[IO.Path]::GetDirectoryName($native)
    $env:PSModulePath=[IO.Path]::GetDirectoryName($native)+'\Modules'
    $enginePath=Join-Path $PSScriptRoot 'cold-backup-core.dll';Plain $enginePath
    $enginePin=[IO.File]::Open($enginePath,'Open','Read','Read')
    Need ($enginePin.Length -gt 0 -and $enginePin.Length -le 131072 -and (HashStream $enginePin) -ceq $expectedEngine) 'engine-pin'
    $bytes=New-Object byte[] ([int]$enginePin.Length);$enginePin.Position=0;$offset=0
    while($offset -lt $bytes.Length){$n=$enginePin.Read($bytes,$offset,$bytes.Length-$offset);Need ($n -gt 0) 'engine-truncated';$offset+=$n}
    [void][Reflection.Assembly]::Load($bytes)
    Write-Host '[STEP 1/8] Fixed v1.0.25 runtime and recovery check. No shutdown yet.' -ForegroundColor Cyan
    LiveGuard
    foreach($processId in @(6728,7620)){
        $cim=Get-CimInstance Win32_Process -Filter ('ProcessId = '+$processId)
        if($processId -eq 7620){Need ($cim.ParentProcessId -eq 6728) 'backend-parent'}
        $owner=Invoke-CimMethod -InputObject $cim -MethodName GetOwnerSid
        Need ($owner.ReturnValue -eq 0 -and $owner.Sid -ceq [Security.Principal.WindowsIdentity]::GetCurrent().User.Value) 'process-user'
    }
    $baseline=CheckSettings
    $spawnEvents=@((LifecycleEvents)|Where-Object {$_.event -ceq 'backend.spawned' -and
        (CountValue $_.payload 'pid') -eq 7620 -and
        [Math]::Abs(($_.at.UtcDateTime.Ticks-639245234936285878)/10000000.0) -le 120})
    Need ($spawnEvents.Count -eq 1) 'runtime-session-not-unique'
    $runtimeSession=$spawnEvents[0].session
    CheckLiveConfig
    Need ([SflColdBackupV1.Engine]::FileHash($recovery,536870912) -ceq $recoveryHash) 'recovery-pin'
    $prospective='C:\ProgramData\SFL26B-'+[Guid]::NewGuid().ToString('N')
    $guard=[Action]{if($coldMode){ColdGuard}else{LiveGuard}}
    $progressPhase='';$phaseClock=[Diagnostics.Stopwatch]::StartNew()
    $progress=[Action[string,long,long,long]]{param($name,$done,$count,$millis)
        if($script:progressPhase -cne $name){$script:progressPhase=$name;$script:phaseClock.Restart()}
        $total=if($name -ceq 'source-and-restored-verification'){$estimatedBytes*2}elseif($name -ceq 'closeout-fact-hash'){$closeoutFactBytes}else{$estimatedBytes}
        $pct=if($total -gt 0){[Math]::Min(99,[Math]::Round(100.0*$done/$total,1))}else{0}
        $remaining=if($name -cne 'inventory' -and $done -gt 0 -and $total -gt $done){
            [TimeSpan]::FromSeconds([Math]::Min(864000,($total-$done)*$script:phaseClock.Elapsed.TotalSeconds/$done)).ToString('hh\:mm\:ss')
        }else{'unknown'}
        Write-Host ('[PROGRESS] phase='+$name+' elapsed='+$clock.Elapsed.ToString('hh\:mm\:ss')+' stage_remaining~='+$remaining+' files='+$count+' bytes='+$done+' percent~='+$pct+'%; no image requests')
    }
    $engine=[SflColdBackupV1.Engine]::new($rootPaths,$guard,$progress)
    $phase='live-capacity-inventory'
    Write-Host '[STEP 2/8] Count ALL files under the three fixed roots. Images included; metadata only.'
    $liveInventory=$engine.Inventory($prospective+'\restore')
    $estimatedBytes=$liveInventory.Bytes
    $required=[SflColdBackupV1.Engine]::RequiredSpace($estimatedBytes,($liveInventory.Files+$liveInventory.Directories))
    $drive=[IO.DriveInfo]::new('C:\')
    Need ($drive.DriveType -eq 'Fixed' -and $drive.DriveFormat -ceq 'NTFS' -and $drive.AvailableFreeSpace -ge $required) 'insufficient-space-before-shutdown'
    Write-Host ('[CAPACITY] source_GiB='+[Math]::Round($estimatedBytes/1GB,2)+' required_GiB='+[Math]::Round($required/1GB,2)+' free_GiB='+[Math]::Round($drive.AvailableFreeSpace/1GB,2))
    Write-Host ('[DESTINATION] '+$prospective)
    Write-Host '[LIMITATION] Same C: volume. Two uncompressed copies. This is not disaster recovery or a functional application restore.'
    Write-Host '[ACTION] This requires downtime until copying and verification finish (possibly tens of minutes or longer). No automatic restart or installation.' -ForegroundColor Yellow
    Write-Host '[ACTION] Only proceed during an approved maintenance window. Do not close the app before the instruction below.'
    $answer=Read-Host 'Type BACKUP V1.0.25 to approve this destination, file copies and manual normal shutdown; otherwise cancel'
    Need ($answer -ceq 'BACKUP V1.0.25') 'operator-not-approved';$answerAccepted=$true
    LiveGuard;$baseline=CheckSettings;CheckLiveConfig
    $mainProcess=Get-Process -Id 6728;$backendProcess=Get-Process -Id 7620
    # Retain native process handles BEFORE shutdown; do not infer exit codes from PID disappearance.
    $null=$mainProcess.Handle;$null=$backendProcess.Handle
    NewProtectedRoot $prospective;$workRoot=$prospective
    $intentAt=[DateTimeOffset]::Now
    $intentHash=WriteNewJson 'intent.json' ([ordered]@{schema_version='sfl-cold-backup-intent-v1';recorded_at=$intentAt.ToString('o');
        sources=$rootPaths;destination=$workRoot;product_version='1.0.25';product_commit=$commit;baseline=$baseline;
        live_inventory=$liveInventory;required_bytes=$required;operator_token_accepted=$true;installation_authorized=$false})
    $phase='manual-normal-shutdown'
    Write-Host '[STEP 3/8] Close SmartFactory normally using its window X NOW. Do not use Task Manager, taskkill or Stop-Process.' -ForegroundColor Cyan
    $wait=[Diagnostics.Stopwatch]::StartNew()
    while($true){
        $r=Runtime
        if($r.apps.Count -eq 0 -and $r.backends.Count -eq 0 -and $r.listeners.Count -eq 0){break}
        Need ($wait.Elapsed.TotalSeconds -lt 300) 'shutdown-timeout'
        Write-Host ('[SHUTDOWN WAIT] elapsed='+[int]$wait.Elapsed.TotalSeconds+'s / 300s apps='+$r.apps.Count+' backend='+$r.backends.Count+' listeners='+$r.listeners.Count)
        Start-Sleep -Seconds 5
    }
    Need ($mainProcess.WaitForExit(0) -and $backendProcess.WaitForExit(0)) 'pinned-process-still-running'
    Need ($mainProcess.ExitCode -eq 0 -and $backendProcess.ExitCode -eq 0) 'nonzero-process-exit'
    $coldMode=$true;$stopped=$true;ColdGuard
    $phase='closeout-and-cold-inventory'
    Write-Host '[STEP 4/8] Verify fresh image closeout and recount the stopped sources. No app will be started.'
    $shutdownProof=ShutdownProof (LifecycleEvents) $runtimeSession $intentAt
    $manifestPath=$data+'\logs\test_data\spot_image_fact_manifest.final.json'
    $manifest=ReadSmallJson $manifestPath;$manifestInfo=[IO.FileInfo]::new($manifestPath)
    Need ($manifestInfo.LastWriteTimeUtc -ge $intentAt.UtcDateTime -and $manifestInfo.LastWriteTimeUtc -le [DateTime]::UtcNow) 'stale-closeout-manifest'
    Need ((Field $manifest 'enabled') -is [bool] -and (Field $manifest 'enabled') -and
        (Field $manifest 'mode') -ceq $baseline.mode) 'closeout-mode'
    Need (([string](Field $manifest 'fact_path')).Replace('/','\') -ieq ($data+'\logs\test_data\spot_image_fact.csv') -and
        ([string](Field $manifest 'capture_root')).Replace('/','\') -ieq ($data+'\logs\test_data\spot_images')) 'closeout-paths'
    Need ((CountValue $manifest 'written') -ge $baseline.written -and (CountValue $manifest 'row_count') -ge $baseline.rows -and
        (CountValue $manifest 'dropped') -eq $baseline.dropped -and (CountValue $manifest 'failure') -eq 0) 'closeout-counters'
    $factHash=Field $manifest 'sha256';Need ($factHash -is [string] -and $factHash -cmatch '^[a-fA-F0-9]{64}$') 'closeout-hash-shape'
    $closeoutFactBytes=[IO.FileInfo]::new($data+'\logs\test_data\spot_image_fact.csv').Length
    Need ($engine.EvidenceHash($data+'\logs\test_data\spot_image_fact.csv') -ceq $factHash.ToUpperInvariant()) 'closeout-fact-hash'
    Need ([SflColdBackupV1.Engine]::FileHash($config,1048576) -ceq $configHash) 'config-changed-at-shutdown'
    $coldInventory=$engine.Inventory($workRoot+'\restore');$estimatedBytes=$coldInventory.Bytes
    Need ($drive.AvailableFreeSpace -ge [SflColdBackupV1.Engine]::RequiredSpace($estimatedBytes,($coldInventory.Files+$coldInventory.Directories))) 'insufficient-space-after-shutdown'
    $phase='backup-copy';Write-Host '[STEP 5/8] Copy stopped sources into a NEW protected backup tree; record each source SHA256 and metadata.'
    CheckAcl $workRoot;ColdGuard
    $backup=$engine.Backup($workRoot+'\backup',$workRoot+'\files.manifest.tsv')
    Need ($backup.Files -eq $coldInventory.Files -and $backup.Directories -eq $coldInventory.Directories -and $backup.Bytes -eq $coldInventory.Bytes) 'cold-inventory-drift'
    $phase='restore-copy';Write-Host '[STEP 6/8] Reopen backup files and restore into a SEPARATE new rehearsal tree; compare each SHA256.'
    $restored=$engine.Verify($workRoot+'\files.manifest.tsv',$backup.ManifestSha256,$workRoot+'\backup',$workRoot+'\restore',$true)
    $phase='source-and-restore-recheck';Write-Host '[STEP 7/8] Reopen every restored file and every source; verify hashes and exact membership. No product start.'
    $verified=$engine.Verify($workRoot+'\files.manifest.tsv',$backup.ManifestSha256,$workRoot+'\restore',$null,$false)
    ColdGuard;CheckAcl $workRoot
    $phase='completion-receipt';Write-Host '[STEP 8/8] Publish a separate completion receipt. Keep backup, rehearsal and source unchanged.'
    $result=[ordered]@{schema_version='sfl-cold-backup-result-v1';result='V1025_COLD_BACKUP_AND_FILE_RESTORE_VERIFIED_NOT_INSTALL_READY';
        recorded_at=[DateTimeOffset]::Now.ToString('o');elapsed_seconds=$clock.Elapsed.TotalSeconds;product_version='1.0.25';product_commit=$commit;
        roots=$rootPaths;backup_root=($workRoot+'\backup');restore_rehearsal_root=($workRoot+'\restore');intent_sha256=$intentHash;
        config_sha256=$configHash;recovery_installer_sha256=$recoveryHash;source_file_count=$backup.Files;source_directory_count=$backup.Directories;
        source_bytes=$backup.Bytes;manifest_sha256=$backup.ManifestSha256;closeout_image_fact_sha256=$factHash.ToUpperInvariant();
        main_exit_code=$mainProcess.ExitCode;backend_exit_code=$backendProcess.ExitCode;app_still_stopped=$true;
        shutdown_event=$shutdownProof;
        backup_readback_verified=$true;restored_file_hashes_verified=$true;source_hashes_rechecked=$true;exact_membership_verified=$true;
        source_files_overwritten=$false;source_files_deleted=$false;automatic_restart_performed=$false;installation_started=$false;
        application_restore_test_performed=$false;profile_downgrade_tested=$false;original_acls_applied=$false;all_runtime_storage_paths_proven=$false;
        same_volume_only=$true;encrypted_backup=$false;installation_ready=$false;production_promotion_allowed=$false;
        limitation='Protected byte-level backup and offline file restoration only. Original metadata/SDDL recorded, not applied to copies. No VSS or hostile concurrent path-replacement guarantee. Periodic guards are not continuous uptime proof. Historical errors/drops are not repaired. No automatic cleanup or restart.'}
    $resultHash=WriteNewJson 'result.json' $result
    Write-Host ('[RESULT] '+$workRoot+'\result.json');Write-Host ('[SHA256] '+$resultHash)
    Write-Host ('[MANIFEST SHA256] '+$backup.ManifestSha256)
    Write-Host '[COMPLETE] Files verified. APP REMAINS STOPPED. Do not install or roll back. Return receipt/output privately; do not upload backup/profile data.' -ForegroundColor Green
}catch{
    $e=$_.Exception;$code='details-withheld'
    while($null -ne $e){if($e.Message -cmatch 'COLD_BACKUP:([a-z0-9-]+)'){$code=$Matches[1];break};$e=$e.InnerException}
    Write-Host ('[HOLD] phase='+$phase+' reason='+$code+' elapsed='+$clock.Elapsed.ToString('hh\:mm\:ss')) -ForegroundColor Yellow
    if($null -ne $workRoot){
        Write-Host ('[PRESERVE] '+$workRoot)
        try{$null=WriteNewJson 'hold.json' @{result='HOLD';phase=$phase;reason=$code;recorded_at=[DateTimeOffset]::Now.ToString('o');
            operator_token_accepted=$answerAccepted;stopped_confirmed=$stopped;installation_ready=$false;partial_files_preserved=$true}}
        catch{Write-Host '[HOLD] Receipt could not be written; preserve console and partial files.'}
    }
    Write-Host '[HOLD] No automatic retry, cleanup, force-stop, restart, restore over original data or installation. If already closed, keep app stopped and return output.'
    throw 'COLD_BACKUP_HOLD: See the sanitized phase and reason above.'
}finally{
    if($null -ne $enginePin){$enginePin.Dispose()}
    if($null -ne $mainProcess){$mainProcess.Dispose()};if($null -ne $backendProcess){$backendProcess.Dispose()}
    $env:PATH=$savedBackupPath;$env:PSModulePath=$savedBackupModules
}
