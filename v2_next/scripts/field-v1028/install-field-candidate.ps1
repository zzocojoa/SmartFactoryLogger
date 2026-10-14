[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$RequestPath,
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{64}$')][string]$ExpectedRequestSha256
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$script:held=[Collections.Generic.List[IDisposable]]::new()
$script:resultRoot=$null
$script:installerExit=$null
$script:installerStarted=$false
$script:configurationChanged=$false
$script:phase='environment'

function Require([bool]$Value,[string]$Reason) { if(-not $Value){throw $Reason} }
function Plain([string]$Path) {
    Require ($Path -cmatch '^[A-Za-z]:[\\/]' -and $Path.Substring(2) -notmatch ':' -and $Path -notmatch '[\x00-\x1f]') 'absolute-local-path'
    $full=[IO.Path]::GetFullPath($Path).TrimEnd('\')
    Require ($full.Length -gt 3 -and $full.Length -le 240) 'path-budget'
    $node=[IO.FileInfo]::new($full)
    while($null -ne $node){
        Require ([int]$node.Attributes -eq -1 -or ($node.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'reparse-path'
        if($node -is [IO.FileInfo]){$node=$node.Directory}else{$node=$node.Parent}
    }
    return $full
}
function HashStream([IO.Stream]$Stream) {
    $hash=[Security.Cryptography.SHA256]::Create()
    try{$Stream.Position=0;return [BitConverter]::ToString($hash.ComputeHash($Stream)).Replace('-','').ToLowerInvariant()}finally{$hash.Dispose()}
}
function Fact([string]$Path) {
    $s=[IO.File]::Open((Plain $Path),'Open','Read','Read')
    try{return [ordered]@{bytes=$s.Length;sha256=(HashStream $s)}}finally{$s.Dispose()}
}
function LockFile([string]$Path,[string]$Sha,[long]$Size=-1) {
    Require ($Sha -cmatch '^[a-f0-9]{64}$') 'external-hash-format'
    $s=[IO.File]::Open((Plain $Path),'Open','Read','Read');$script:held.Add($s)
    Require ((HashStream $s) -ceq $Sha -and ($Size -lt 0 -or $s.Length -eq $Size)) 'locked-file-fact'
    return $s
}
function ReadLockedJson([IO.Stream]$Stream,[long]$Limit=2097152) {
    Require ($Stream.Length -gt 0 -and $Stream.Length -le $Limit) 'json-byte-budget'
    $Stream.Position=0;$reader=[IO.StreamReader]::new($Stream,[Text.UTF8Encoding]::new($false,$true),$true,4096,$true)
    try{return ($reader.ReadToEnd()|ConvertFrom-Json)}finally{$reader.Dispose()}
}
function ImportBackupEngine([string]$Path) {
    $stream=LockFile $Path 'fb12e3acb370d86999156600efb3cd23083d890dfec1216cf4e06e9c1cce2a26' 24576
    # Load the same hash-verified, held bytes. Preserve the file and its named streams.
    $bytes=New-Object byte[] ([int]$stream.Length);$stream.Position=0;$offset=0
    while($offset -lt $bytes.Length){
        $read=$stream.Read($bytes,$offset,$bytes.Length-$offset)
        Require ($read -gt 0) 'backup-engine-truncated';$offset+=$read
    }
    [void][Reflection.Assembly]::Load($bytes)
}
function SaveJson([string]$Name,$Value) {
    Require ($Name -cmatch '^[a-z0-9-]+$') 'receipt-name'
    $Name += '.json'
    $bytes=[Text.UTF8Encoding]::new($false).GetBytes(($Value|ConvertTo-Json -Depth 35))
    $s=[IO.File]::Open((Join-Path $script:resultRoot $Name),'CreateNew','Write','None')
    try{$s.Write($bytes,0,$bytes.Length);$s.Flush($true)}finally{$s.Dispose()}
}
function ReceiptFacts {
    $facts=[ordered]@{}
    foreach($file in Get-ChildItem -LiteralPath $script:resultRoot -File -Force){$facts[$file.Name]=Fact $file.FullName}
    return $facts
}
function AssertResultAcl([string]$Path,[Security.AccessControl.DirectorySecurity]$Expected) {
    $actual=[IO.Directory]::GetAccessControl((Plain $Path))
    Require ($actual.AreAccessRulesProtected -and $actual.GetOwner([Security.Principal.SecurityIdentifier]).Value -ceq $Expected.GetOwner([Security.Principal.SecurityIdentifier]).Value) 'result-owner-inheritance'
    $rules=@($actual.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    $expectedRules=@($Expected.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    Require ($rules.Count -eq $expectedRules.Count) 'result-rule-count'
    $seen=@{}
    foreach($rule in $rules){
        $sid=$rule.IdentityReference.Value;$match=@($expectedRules|Where-Object{$_.IdentityReference.Value -ceq $sid})
        Require ($match.Count -eq 1 -and -not $seen.ContainsKey($sid)) 'result-rule-sid'
        Require (-not $rule.IsInherited -and $rule.AccessControlType -eq 'Allow' -and $rule.FileSystemRights -eq $match[0].FileSystemRights -and $rule.InheritanceFlags -eq $match[0].InheritanceFlags -and $rule.PropagationFlags -eq 'None') 'result-rule-rights'
        $seen[$sid]=$true
    }
}
function ColdSnapshot {
    return [ordered]@{
        processes=@(Get-CimInstance Win32_Process -Filter "Name='smart-factory.exe' OR Name='SmartFactoryBackend.exe'" | Select-Object ProcessId,ParentProcessId,ExecutablePath,CreationDate)
        listeners=@(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object LocalPort -EQ 8000 | Select-Object LocalAddress,LocalPort,OwningProcess)
    }
}
function AssertCold($Snapshot) { Require (@($Snapshot.processes).Count -eq 0 -and @($Snapshot.listeners).Count -eq 0) 'application-or-port-active' }
function CheckBackup($Backup,$Review,[string]$BackupRoot,[string]$BackupSha,[string]$ManifestSha,[string[]]$Roots) {
    Require ($Backup.status -ceq 'SELECTED_COLD_COPY_DEFAULT_AND_NAMED_DATA_STREAMS_VERIFIED' -and $Backup.run_root -ieq $BackupRoot) 'backup-result-status-path'
    Require (($Backup.source_roots -join '|') -ceq ($Roots -join '|') -and $Backup.file_manifest_sha256.ToLowerInvariant() -ceq $ManifestSha) 'backup-scope-manifest'
    foreach($key in @('source_streams_preserved','source_and_copy_default_and_named_streams_rehashed','source_metadata_and_default_named_stream_membership_unchanged','app_backend_port_absence_observed')){
        Require ($Backup.$key -is [bool] -and $Backup.$key) ('backup-proof:'+ $key)
    }
    Require ($Review.schema -ceq 'sfl-field-preinstall-close-review-v1' -and $Review.backup_result_sha256 -ceq $BackupSha -and $Review.backup_manifest_sha256 -ceq $ManifestSha) 'close-review-backup-binding'
    Require ($Review.normal_shutdown_observed -is [bool] -and $Review.normal_shutdown_observed -and @($Review.failed_checks).Count -eq 0) 'normal-shutdown-review'
    Require ($Review.logger_service_instance_id -ceq $Backup.preceding_logger_service_instance_id -and $Review.backend_pid -eq $Backup.preceding_operating_identity.backend_pid) 'close-review-generation'
    $age=([DateTimeOffset]::UtcNow-[DateTimeOffset]::Parse($Backup.time)).TotalMinutes
    Require ($age -ge -1 -and $age -le 180) 'backup-freshness'
}
function PayloadFacts([string]$Root,$Specs) {
    $Root=Plain $Root;$expected=@{};$actual=@{};$pending=[Collections.Generic.Queue[string]]::new();$pending.Enqueue($Root)
    foreach($p in $Specs.PSObject.Properties){
        Require ($p.Name -notmatch '[\\:\x00-\x1f]' -and -not $p.Name.StartsWith('/') -and @($p.Name.Split('/')|Where-Object{$_ -in @('','.','..') -or $_ -match '[. ]$'}).Count -eq 0) 'payload-entry-name'
        Require (-not $expected.ContainsKey($p.Name) -and $p.Value.sha256 -cmatch '^[a-f0-9]{64}$' -and $p.Value.bytes -ge 0) 'payload-entry-fact'
        $expected[$p.Name]=$p.Value
    }
    $count=0
    while($pending.Count -gt 0){
        foreach($item in Get-ChildItem -LiteralPath $pending.Dequeue() -Force){
            $count++;Require ($count -le 6000) 'installed-entry-budget';$null=Plain $item.FullName
            if($item.PSIsContainer){$pending.Enqueue($item.FullName);continue}
            $name=$item.FullName.Substring($Root.Length+1).Replace('\','/')
            Require (-not $actual.ContainsKey($name) -and ($expected.ContainsKey($name) -or $name -cin @('Uninstall smart-factory.exe','uninstallerIcon.ico'))) 'unexpected-installed-file'
            $f=Fact $item.FullName;$actual[$name]=$f
            if($expected.ContainsKey($name)){Require ($f.bytes -eq $expected[$name].bytes -and $f.sha256 -ceq $expected[$name].sha256) ('installed-payload-mismatch:'+ $name)}
        }
    }
    foreach($name in $expected.Keys){Require ($actual.ContainsKey($name)) ('installed-file-missing:'+ $name)}
    Require ($actual.ContainsKey('Uninstall smart-factory.exe')) 'uninstaller-missing'
    return $actual
}
function RunInstaller([string]$Path,[int]$LimitMs=300000) {
    $info=[Diagnostics.ProcessStartInfo]::new();$info.FileName=$Path;$info.Arguments='/S /currentuser';$info.WorkingDirectory=[IO.Path]::GetDirectoryName($Path)
    $info.UseShellExecute=$false;$info.CreateNoWindow=$true;$info.WindowStyle='Hidden'
    $started=[DateTimeOffset]::UtcNow;$process=[Diagnostics.Process]::Start($info);$script:installerStarted=$true
    try{
        $identity=[ordered]@{path=$Path;pid=$process.Id;started_at_utc=$started.ToString('o');arguments=$info.Arguments}
        SaveJson 'installer-start' $identity
        Require ($process.WaitForExit($LimitMs)) 'installer-timeout-no-force-no-retry'
        $script:installerExit=[ordered]@{identity=$identity;actual_exit_code=$process.ExitCode;ended_at_utc=[DateTimeOffset]::UtcNow.ToString('o');forced_termination=$false}
        SaveJson 'installer-exit' $script:installerExit
        Require ($process.ExitCode -eq 0) 'installer-nonzero-exit'
    }finally{$process.Dispose()}
}
function DisableComparator([byte[]]$Bytes) {
    # Latin-1 is used only as a reversible byte mapping; non-ASCII INI bytes survive.
    $encoding=[Text.Encoding]::GetEncoding(28591);$text=$encoding.GetString($Bytes)
    Require (-not ($Bytes.Length -ge 2 -and (($Bytes[0] -eq 255 -and $Bytes[1] -eq 254) -or ($Bytes[0] -eq 254 -and $Bytes[1] -eq 255)))) 'unsupported-utf16-config'
    $sections=[regex]::Matches($text,'(?im)^\[SPOT\][ \t]*\r?\n(?:(?!^\[)[\s\S])*')
    Require ($sections.Count -eq 1) 'single-spot-section-required'
    $section=$sections[0];$keys=[regex]::Matches($section.Value,'(?im)^(?<prefix>[ \t]*low_signal_comparator_verified[ \t]*=[ \t]*)(?<value>true|false)(?<suffix>[ \t]*\r?)$')
    Require ($keys.Count -eq 1 -and [regex]::Matches($section.Value,'(?im)^[ \t]*low_signal_comparator_verified[ \t]*=').Count -eq 1) 'single-comparator-boolean-required'
    Require ([regex]::Matches($section.Value,'(?im)^[ \t]*low_signal_alarm_enabled[ \t]*=[ \t]*false[ \t]*\r?$').Count -eq 1 -and [regex]::Matches($section.Value,'(?im)^[ \t]*low_signal_alarm_enabled[ \t]*=').Count -eq 1) 'low-signal-alarm-must-be-false'
    $value=$keys[0].Groups['value'];$offset=$section.Index+$value.Index
    return ,$encoding.GetBytes($text.Substring(0,$offset)+'false'+$text.Substring($offset+$value.Length))
}
function ConfigStreamFacts([string]$Path) {
    $null=Plain $Path;$facts=[ordered]@{};$streams=@(Get-Item -LiteralPath $Path -Stream '*' | Sort-Object Stream)
    Require ($streams.Count -le 32) 'config-stream-count'
    foreach($stream in $streams){
        if($stream.Stream -ceq ':$DATA'){continue}
        Require ($stream.Length -ge 0 -and $stream.Length -le 1MB) 'config-stream-size'
        [byte[]]$bytes=Get-Content -LiteralPath $Path -Stream $stream.Stream -Encoding Byte -ReadCount 0
        if($null -eq $bytes){$bytes=[byte[]]@()}
        Require ($bytes.Length -eq $stream.Length) 'config-stream-read-size'
        $hash=[Security.Cryptography.SHA256]::Create()
        try{$facts[$stream.Stream]=@{bytes=$bytes.Length;sha256=[BitConverter]::ToString($hash.ComputeHash($bytes)).Replace('-','').ToLowerInvariant()}}finally{$hash.Dispose()}
    }
    return $facts
}
function RegistrationFacts($Registration,[string]$Location) {
    # Registry provider objects contain recursive PSDrive/PSProvider metadata.
    # Record only the scalar fields used to verify this installation.
    foreach($key in @('PSChildName','DisplayName','DisplayVersion','UninstallString')){
        Require ($Registration.$key -is [string]) ('registration-field-type:'+ $key)
    }
    return [ordered]@{key_name=$Registration.PSChildName;display_name=$Registration.DisplayName;display_version=$Registration.DisplayVersion;uninstall_string=$Registration.UninstallString;install_location=$Location}
}

try {
    $native=[Environment]::SystemDirectory+'\WindowsPowerShell\v1.0\powershell.exe'
    $sid='S-1-5-21-2762931165-1280404403-2847611662-1001'
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent();$principal=[Security.Principal.WindowsPrincipal]::new($identity)
    Require ([Environment]::Is64BitProcess -and $PSVersionTable.PSEdition -ceq 'Desktop' -and $PSVersionTable.PSVersion.Major -eq 5 -and $PSVersionTable.PSVersion.Minor -eq 1 -and [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName -ieq $native) 'native-ps51-x64-required'
    Require ($env:COMPUTERNAME -ceq 'DESKTOP-CIIT7LK' -and $identity.User.Value -ceq $sid -and $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) 'server-operator-admin-required'
    Require ($env:APPDATA -ieq 'C:\Users\user\AppData\Roaming' -and $env:LOCALAPPDATA -ieq 'C:\Users\user\AppData\Local') 'operator-profile'
    $env:PATH=[Environment]::SystemDirectory+';'+[IO.Path]::GetDirectoryName($native);$env:PSModulePath=[IO.Path]::GetDirectoryName($native)+'\Modules'
    $request=ReadLockedJson (LockFile $RequestPath $ExpectedRequestSha256)
    Require ($request.schema -ceq 'sfl-field-install-request-v1' -and $request.candidate_commit -ceq '4cc7393e1bafbf90a329726aed9470fe0daacb21' -and $request.approval_sha256 -ceq '6517011d8f51eb4cff560bf83c8dcbb471bd4add99f21cdac59387d3d1c93685') 'request-contract'
    $null=LockFile $request.approval_path $request.approval_sha256
    $factory=Plain ([Environment]::GetFolderPath('Desktop')+'\SmartFactory');Require ($factory -ieq 'C:\Users\user\Desktop\SmartFactory') 'desktop-root'
    $script:resultRoot=$factory+'\I'+[Guid]::NewGuid().ToString('N').Substring(0,8)
    Require (-not [IO.Directory]::Exists($script:resultRoot) -and -not [IO.File]::Exists($script:resultRoot)) 'fresh-result-required'
    $acl=[Security.AccessControl.DirectorySecurity]::new();$acl.SetAccessRuleProtection($true,$false);$acl.SetOwner([Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))
    foreach($reader in @('S-1-5-32-544','S-1-5-18',$sid)){$rights=if($reader -ceq $sid){'ReadAndExecute'}else{'FullControl'};$acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($reader),$rights,'ContainerInherit,ObjectInherit','None','Allow'))}
    $null=[IO.Directory]::CreateDirectory($script:resultRoot,$acl)
    AssertResultAcl $script:resultRoot $acl
    SaveJson 'request' $request
    $script:phase='backup-and-cold-preconditions'
    $roots=@('C:\Users\user\AppData\Roaming\SmartFactoryLogger','C:\Users\user\AppData\Roaming\smart-factory-logger-v2')
    $backupRoot=Plain $request.backup_root;Require ($backupRoot -imatch '^C:\\Users\\user\\Desktop\\SmartFactory\\Q[0-9a-f]{6}$') 'backup-root-contract'
    $backup=ReadLockedJson (LockFile ($backupRoot+'\result.json') $request.backup_result_sha256)
    $null=LockFile ($backupRoot+'\files.tsv') $request.backup_manifest_sha256
    $review=ReadLockedJson (LockFile $request.close_review_path $request.close_review_sha256)
    CheckBackup $backup $review $backupRoot $request.backup_result_sha256 $request.backup_manifest_sha256 $roots
    $cold=ColdSnapshot;AssertCold $cold;SaveJson 'runtime-before' $cold
    $installRoot='C:\Users\user\AppData\Local\Programs\smart-factory-logger-v2'
    $old=ReadLockedJson (LockFile ($installRoot+'\resources\backend\bundle-manifest.json') $request.old_bundle_manifest_sha256)
    Require ($old.build_git_commit -ceq '541d701d544eea6a8a4e4836047077eaf9cfaf30') 'preceding-operating-build'
    # Release the old installed file before NSIS replaces it. It is not an input executable.
    $script:held[$script:held.Count-1].Dispose();$script:held.RemoveAt($script:held.Count-1)
    $candidate=Plain $request.candidate_installer
    $null=LockFile $candidate '8821746bbed47850ead68c66894e5580afac63483b1569865915dadc30cfc848' 164618981
    $null=LockFile $request.rollback_installer '08c061ee35a1a01788f05b00ee7395aa40774150c92c06726a92f3df1bf75c3c' 163826264
    foreach($path in @($candidate,$request.rollback_installer)){Require ((Get-AuthenticodeSignature -LiteralPath $path).Status.ToString() -ceq 'NotSigned') 'unsigned-installer-state'}
    $payload=ReadLockedJson (LockFile $request.payload_reference 'a5de26c2db81c8d69418fd3e574d4180b2dd895ab94b9cbf064959369644af5c')
    Require ($payload.candidate_commit -ceq $request.candidate_commit -and $payload.payload_file_count -eq 1814 -and @($payload.payload_files.PSObject.Properties).Count -eq 1814) 'payload-reference-contract'
    ImportBackupEngine $request.backup_engine
    $configPath=$roots[0]+'\config.ini';Require ((Fact $configPath).sha256 -ceq $request.config_sha256) 'preinstall-config-pin'
    $configBefore=[IO.File]::ReadAllBytes($configPath);$configAfter=DisableComparator $configBefore;$configStreams=ConfigStreamFacts $configPath
    $beforePath=$script:resultRoot+'\config-before.ini';[IO.File]::WriteAllBytes($beforePath,$configBefore)
    Require ((Fact $beforePath).sha256 -ceq $request.config_sha256) 'captured-config-pin'
    $cold=ColdSnapshot;AssertCold $cold
    $script:phase='installer';RunInstaller $candidate
    $script:phase='installed-payload';AssertCold (ColdSnapshot)
    SaveJson 'installed-files' (PayloadFacts $installRoot $payload.payload_files)
    $registrations=@(Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*' | Where-Object { $_.PSObject.Properties['DisplayName'] -and $_.DisplayName -like '*smart-factory*' })
    Require ($registrations.Count -eq 1 -and $registrations[0].DisplayVersion -ceq '1.0.28' -and $registrations[0].UninstallString -like ('*'+$installRoot+'\Uninstall smart-factory.exe*')) 'installed-registration'
    $registeredLocation=(Get-ItemProperty -LiteralPath ('HKCU:\Software\'+$registrations[0].PSChildName) -Name InstallLocation).InstallLocation
    Require ($registeredLocation -ieq $installRoot) 'registered-install-location'
    SaveJson 'registration' (RegistrationFacts $registrations[0] $registeredLocation)
    $script:phase='postinstall-original-data-preservation'
    $guard=[Action]{AssertCold (ColdSnapshot)};$progress=[Action[string,long,long,long]]{param($phase,$bytes,$files,$elapsed) Write-Host ('VERIFY phase='+$phase+' files='+$files+' bytes='+$bytes)}
    $engine=[SflColdCopyStreamsV2.Engine]::new($roots,$guard,$progress)
    $verified=$engine.Verify($backupRoot+'\files.tsv',$request.backup_manifest_sha256.ToUpperInvariant(),$backupRoot+'\c',$null,$false)
    Require ($verified.Files -eq $backup.copied_files -and $verified.Bytes -eq $backup.copied_bytes_including_named_streams -and $verified.NamedStreams -eq $backup.copied_named_streams) 'postinstall-preservation-totals'
    SaveJson 'preserved-data' $verified
    $script:phase='approved-comparator-flag'
    AssertCold (ColdSnapshot);Require ((Fact $configPath).sha256 -ceq $request.config_sha256) 'config-changed-before-correction'
    $afterPath=$script:resultRoot+'\config-after.ini';[IO.File]::WriteAllBytes($afterPath,$configAfter)
    $temporary=$configPath+'.field-off-'+[Guid]::NewGuid().ToString('N')
    [IO.File]::WriteAllBytes($temporary,$configAfter)
    [IO.File]::Replace($temporary,$configPath,[NullString]::Value);$script:configurationChanged=$true
    Require ((Fact $configPath).sha256 -ceq (Fact $afterPath).sha256) 'corrected-config-byte-check'
    Require (((ConfigStreamFacts $configPath)|ConvertTo-Json -Compress) -ceq ($configStreams|ConvertTo-Json -Compress)) 'config-named-streams-changed'
    SaveJson 'configuration-change' ([ordered]@{before=(Fact $beforePath);after=(Fact $configPath);named_streams_preserved=$configStreams;changed_key='SPOT.low_signal_comparator_verified';value=$false;alarm_enabled=$false;operator_attestation_applied=$false})
    AssertCold (ColdSnapshot);$script:phase='complete-pending-standard-user-start'
    SaveJson 'result' ([ordered]@{status='CANDIDATE_INSTALLED_LOW_SIGNAL_OFF_PENDING_RUNTIME';phase=$script:phase;request_sha256=$ExpectedRequestSha256;candidate_commit=$request.candidate_commit;installer_exit=$script:installerExit;backup_result_sha256=$request.backup_result_sha256;installed_payload_verified=$true;original_data_preserved_before_flag_correction=$true;configuration_changed=$true;physical_boundary='NOT_TESTED';formal_qa='HOLD';release_gate='HOLD';promotion_allowed=$false;application_started=$false;automatic_rollback=$false;evidence_files=(ReceiptFacts)})
    Write-Host ('RESULT_PATH='+$script:resultRoot);Write-Host ('RESULT_SHA256='+(Fact ($script:resultRoot+'\result.json')).sha256)
    Write-Host 'Start the installed app through the existing standard-user desktop shortcut after result review.'
    exit 0
} catch {
    $failure=$_.Exception.Message
    if($script:resultRoot -and [IO.Directory]::Exists($script:resultRoot)){
        SaveJson 'hold' ([ordered]@{status='HOLD';phase=$script:phase;error=$failure;installer_started=$script:installerStarted;installer_exit=$script:installerExit;configuration_changed=$script:configurationChanged;automatic_rollback=$false;force_calls=0;promotion_allowed=$false;evidence_files=(ReceiptFacts)})
        Write-Host ('RESULT_PATH='+$script:resultRoot)
        Write-Host ('HOLD_SHA256='+(Fact ($script:resultRoot+'\hold.json')).sha256)
    }
    Write-Host ('INSTALL_HOLD='+$failure);exit 1
} finally {foreach($handle in $script:held){$handle.Dispose()}}
