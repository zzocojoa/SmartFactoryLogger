[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$RequestPath,
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{64}$')][string]$ExpectedRequestSha256,
    [string]$LibraryPath=''
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$script:held=[Collections.Generic.List[IDisposable]]::new()
$script:resultRoot=$null
$script:installerStarted=$false
$script:installerExit=$null
$script:configurationChanged=$false
$script:phase='environment'


function Import-ObservationEngine([string]$Path) {
    $stream=LockFile $Path '7a9e267917d61eaf625e4f7e0b2eb57a9a8bef1f31fc774c4a37f2be0b0f963c'
    $memory=[IO.MemoryStream]::new()
    try{$stream.Position=0;$stream.CopyTo($memory);[void][Reflection.Assembly]::Load($memory.ToArray())}finally{$memory.Dispose()}
}
function Assert-ObservationInstallSpace([string]$Factory) {
    $drive=[IO.DriveInfo]::new([IO.Path]::GetPathRoot($Factory))
    Require ($drive.DriveType -eq 'Fixed' -and $drive.DriveFormat -ceq 'NTFS' -and
        $drive.AvailableFreeSpace -ge [long](12GB+256MB)) 'installer-workspace-and-operating-reserve'
}
function Assert-ObservationTotals($Actual,$Expected) {
    foreach($key in @('Files','Directories','NamedStreams','Bytes')){
        Require ($Expected.$key -ge 0 -and $Actual.$key -eq $Expected.$key) ('original-preservation-totals:'+ $key)
    }
    Require ($Actual.RecoverableBackupCreated -is [bool] -and -not $Actual.RecoverableBackupCreated -and
        $Expected.RecoverableBackupCreated -is [bool] -and -not $Expected.RecoverableBackupCreated) 'observation-not-backup'
}
function Assert-ClosedObservation($Observation,$Review,[string]$Root,[string]$ResultSha,[string]$ManifestSha,[string[]]$Roots,[string]$CandidateCommit='acaf77d95101a050f4d3ecd76125d3502036f5a7') {
    Require ($Observation.schema -ceq 'sfl-health-preservation-result-v1' -and
        $Observation.status -ceq 'CLOSED_ORIGINAL_OBSERVED_AND_REVERIFIED_NO_BACKUP' -and
        $Observation.run_root -ieq $Root) 'observation-status-path'
    Require (($Observation.source_roots -join '|') -ceq ($Roots -join '|') -and
        $Observation.file_manifest_sha256.ToLowerInvariant() -ceq $ManifestSha -and
        $Observation.totals.ManifestSha256.ToLowerInvariant() -ceq $ManifestSha) 'observation-scope-manifest'
    foreach($key in @('original_default_named_streams_and_metadata_reverified','app_backend_port_absence_observed')){
        Require ($Observation.$key -is [bool] -and $Observation.$key) ('observation-proof:'+ $key)
    }
    Require ($Observation.new_full_data_backup_created -is [bool] -and -not $Observation.new_full_data_backup_created -and
        $Observation.installation_performed -is [bool] -and -not $Observation.installation_performed -and
        $Observation.application_started -is [bool] -and -not $Observation.application_started) 'observation-actions'
    Assert-ObservationTotals $Observation.totals $Observation.totals
    Require ($Review.schema -ceq 'sfl-observed-preinstall-close-review-v1' -and
        $Review.observation_result_sha256 -ceq $ResultSha -and $Review.observation_manifest_sha256 -ceq $ManifestSha) 'close-review-observation-binding'
    Require ($Review.normal_shutdown_observed -is [bool] -and $Review.normal_shutdown_observed -and
        @($Review.failed_checks).Count -eq 0) 'normal-shutdown-review'
    Require ($Review.logger_service_instance_id -ceq $Observation.preceding_logger_service_instance_id) 'close-review-logger-generation'
    Assert-HealthCloseGeneration $Observation $Review $CandidateCommit
    $age=([DateTimeOffset]::UtcNow-[DateTimeOffset]::Parse($Observation.time)).TotalMinutes
    # The original timestamp remains provenance. Installation requires a new full
    # verification below, even when this reviewed baseline is less than 180 minutes old.
    Require ($age -ge -1) 'observation-time-in-future'
}

function Invoke-HealthOriginalReverification($Engine,[string]$ManifestPath,[string]$ManifestSha,$ExpectedTotals) {
    AssertCold (ColdSnapshot)
    $started=[DateTimeOffset]::UtcNow.ToString('o')
    $verified=$Engine.Verify($ManifestPath,$ManifestSha.ToUpperInvariant())
    Assert-ObservationTotals $verified $ExpectedTotals
    Require ($verified.ManifestSha256.ToLowerInvariant() -ceq $ManifestSha) 'reverification-manifest-pin'
    AssertCold (ColdSnapshot)
    return @{totals=$verified;started_at_utc=$started;finished_at_utc=[DateTimeOffset]::UtcNow.ToString('o');
        freshness_clock=[Diagnostics.Stopwatch]::StartNew()}
}
function Assert-HealthReverificationFreshness($Verification,[int]$LimitMs=120000) {
    Require ($LimitMs -gt 0 -and $LimitMs -le 120000 -and
        $Verification.freshness_clock -is [Diagnostics.Stopwatch] -and
        $Verification.freshness_clock.IsRunning -and
        $Verification.freshness_clock.ElapsedMilliseconds -le $LimitMs) 'preinstall-reverification-freshness'
}

function Get-HealthInstallPins([string]$CandidateCommit='acaf77d95101a050f4d3ecd76125d3502036f5a7') {
    $common=@{
        rollback_installer='08c061ee35a1a01788f05b00ee7395aa40774150c92c06726a92f3df1bf75c3c'
        sequence_approval='6517011d8f51eb4cff560bf83c8dcbb471bd4add99f21cdac59387d3d1c93685'
    }
    if($CandidateCommit -ceq 'acaf77d95101a050f4d3ecd76125d3502036f5a7') { return $common+@{
        request_schema='sfl-health-observed-install-request-v1'
        backup_policy='OMITTED_FOR_1029_HEALTH_ONLY'
        previous_version='1.0.28';candidate_version='1.0.29';candidate_installer_bytes=164824610
        previous_commit='4cc7393e1bafbf90a329726aed9470fe0daacb21'
        candidate_commit='acaf77d95101a050f4d3ecd76125d3502036f5a7'
        previous_reference='a5de26c2db81c8d69418fd3e574d4180b2dd895ab94b9cbf064959369644af5c'
        candidate_reference='658b096408ddb82022c53f9802c1300e6da7ca7cfbd077a60db4efc07935fe69'
        candidate_installer='3394a23de82f0d40749f020af320592a33cd9630113ba02b1e40f63f41549de7'
    }}
    Require ($CandidateCommit -ceq '0732c8e810be3c46096b397812f53a9767354229') 'unsupported-install-candidate'
    return $common+@{
        request_schema='sfl-history-observed-install-request-v1'
        backup_policy='OMITTED_FOR_1030_HISTORY_ONLY'
        previous_version='1.0.29';candidate_version='1.0.30';candidate_installer_bytes=164941077
        previous_commit='acaf77d95101a050f4d3ecd76125d3502036f5a7'
        candidate_commit='0732c8e810be3c46096b397812f53a9767354229'
        previous_reference='658b096408ddb82022c53f9802c1300e6da7ca7cfbd077a60db4efc07935fe69'
        candidate_reference='4e3e95be87d8ea51a509ba62c8eb29236eefe402f5f353bb78c9a342d7825a97'
        candidate_installer='e72c042dd4554d5c31e27b8a2edfa6ecdcbdd08c58ed43769e7a84d782b370c1'
        previous_installer='3394a23de82f0d40749f020af320592a33cd9630113ba02b1e40f63f41549de7'
        previous_installer_bytes=164824610
    }
}
function Assert-HealthInstallRequest($Request) {
    $pins=Get-HealthInstallPins $Request.candidate_commit
    $keys=@('schema','candidate_commit','preceding_commit','signature_policy','field_sequence_approval_path',
        'field_sequence_approval_sha256','observation_root','observation_result_sha256','observation_manifest_sha256',
        'close_review_path','close_review_sha256','candidate_installer','rollback_installer',
        'preceding_payload_reference','payload_reference','legacy_stream_engine','observation_engine','new_full_backup_policy','config_sha256')
    if($pins.ContainsKey('previous_installer')){$keys+=@('preceding_installer')}
    $actual=@($Request.PSObject.Properties.Name)
    Require ($actual.Count -eq $keys.Count -and @($actual|Where-Object{$_ -cnotin $keys}).Count -eq 0) 'health-install-request-members'
    Require ($Request.schema -ceq $pins.request_schema -and
        $Request.candidate_commit -ceq $pins.candidate_commit -and $Request.preceding_commit -ceq $pins.previous_commit -and
        $Request.signature_policy -ceq 'UNSIGNED_INTERNAL' -and
        $Request.new_full_backup_policy -ceq $pins.backup_policy -and
        $Request.field_sequence_approval_sha256 -ceq $pins.sequence_approval) 'health-install-request-identity'
    foreach($key in @('observation_result_sha256','observation_manifest_sha256','close_review_sha256','config_sha256')){
        Require ($Request.$key -is [string] -and $Request.$key -cmatch '^[a-f0-9]{64}$') ('health-install-pin:'+ $key)
    }
    $paths=@('field_sequence_approval_path','observation_root','close_review_path','candidate_installer',
        'rollback_installer','preceding_payload_reference','payload_reference','legacy_stream_engine','observation_engine')
    if($pins.ContainsKey('previous_installer')){$paths+=@('preceding_installer')}
    foreach($key in $paths){
        Require ($Request.$key -is [string]) ('health-install-path-type:'+ $key)
        $null=Plain $Request.$key
    }
}
function Assert-HealthCloseGeneration($Backup,$Review,[string]$CandidateCommit='acaf77d95101a050f4d3ecd76125d3502036f5a7') {
    Require ($Review.preceding_commit -ceq (Get-HealthInstallPins $CandidateCommit).previous_commit) 'close-review-preceding-build'
    foreach($name in @('main_pid','main_created_at_utc','backend_pid','backend_created_at_utc')){
        Require ($null -ne $Review.PSObject.Properties[$name] -and
            $null -ne $Backup.preceding_operating_identity.PSObject.Properties[$name] -and
            $Review.$name -ceq $Backup.preceding_operating_identity.$name) ('close-review-native-generation:'+ $name)
    }
    foreach($name in @('main_pid','backend_pid')){
        Require (($Review.$name -is [int] -or $Review.$name -is [long]) -and
            $Review.$name -gt 0 -and $Review.$name -le [int]::MaxValue) 'close-review-native-pid'
    }
    foreach($name in @('main_created_at_utc','backend_created_at_utc')){
        Require ($Review.$name -is [string] -and [DateTimeOffset]::Parse($Review.$name).Offset -eq [TimeSpan]::Zero) 'close-review-native-time'
    }
}
function Assert-HealthInstallPaths($Request,[string]$Factory,[string]$InstallRoot,[string[]]$Roots) {
    Require ($Roots.Count -eq 2) 'health-install-data-roots'
    $areas=@($Factory,$InstallRoot)+$Roots
    foreach($left in $areas){
        $left=Plain $left
        Require (@($areas|Where-Object{(Plain $_) -ieq $left}).Count -eq 1) 'health-install-distinct-roots'
        foreach($right in $areas){
            Require (-not $left.StartsWith((Plain $right)+'\',[StringComparison]::OrdinalIgnoreCase)) 'health-install-overlapping-roots'
        }
    }
    $paths=@('field_sequence_approval_path','observation_root','close_review_path','candidate_installer',
        'rollback_installer','preceding_payload_reference','payload_reference','legacy_stream_engine','observation_engine')
    if((Get-HealthInstallPins $Request.candidate_commit).ContainsKey('previous_installer')){$paths+=@('preceding_installer')}
    foreach($key in $paths){
        $path=Plain $Request.$key
        foreach($area in @($InstallRoot)+$Roots){
            Require ($path -ine $area -and -not $path.StartsWith($area+'\',[StringComparison]::OrdinalIgnoreCase)) 'health-input-inside-operating-root'
        }
    }
}
function Assert-HealthConfiguration([byte[]]$Bytes) {
    # Reuse the tested byte-preserving parser only to assert both flags already false.
    # The old correction function is never used to write the operating configuration.
    $content=$Bytes
    if($Bytes.Length -ge 3 -and $Bytes[0] -eq 239 -and $Bytes[1] -eq 187 -and $Bytes[2] -eq 191){
        $content=[byte[]]::new($Bytes.Length-3);[Array]::Copy($Bytes,3,$content,0,$content.Length)
    }
    $checked=DisableComparator $content
    Require ([Convert]::ToBase64String($checked) -ceq [Convert]::ToBase64String($content)) 'comparator-must-already-be-false'
}
function Get-HealthPayloadFacts([string]$Root,$Reference,[string]$Version) {
    $known=@{
        '1.0.28'=@{commit='4cc7393e1bafbf90a329726aed9470fe0daacb21';count=1814;size=234260;sha='0b2ddc44640a139ab3b5c5a4febdf75e7039a37fadc6871866d7b0d78a46bc6b'}
        '1.0.29'=@{commit='acaf77d95101a050f4d3ecd76125d3502036f5a7';count=1867;size=234261;sha='37ebae1149f7b1ce587ea040c9e0575c16794242eadc147e4d8df58c54a28921'}
        '1.0.30'=@{commit='0732c8e810be3c46096b397812f53a9767354229';count=1899;size=234260;sha='a9f2f1785d7e1c41ba5b6db75253b91da716eaf565017ed213091bff29091910'}
    }
    Require ($known.ContainsKey($Version)) 'health-install-payload-contract'
    $pin=$known[$Version];$count=$pin.count
    Require ($Reference.version -ceq $Version -and
        $Reference.candidate_commit -ceq $pin.commit -and $Reference.payload_file_count -eq $count -and
        @($Reference.payload_files.PSObject.Properties).Count -eq $count) 'health-install-payload-contract'
    $facts=PayloadFacts $Root $Reference.payload_files
    $extra=$facts['Uninstall smart-factory.exe']
    Require ($facts.Count -eq $count+1 -and $extra.sha256 -ceq $pin.sha -and $extra.bytes -eq $pin.size) 'health-install-uninstaller-pin'
    return $facts
}
function Save-HealthInput([string]$Name,[IO.Stream]$Stream) {
    Require ($Name -cmatch '^[a-z0-9-]+\.(json|ps1|dll)$') 'health-input-name'
    $target=$script:resultRoot+'\'+$Name
    $out=[IO.File]::Open($target,'CreateNew','Write','None')
    try{$Stream.Position=0;$Stream.CopyTo($out);$out.Flush($true)}finally{$out.Dispose()}
    Require ((Fact $target).sha256 -ceq (HashStream $Stream)) 'health-input-copy-pin'
}
function Invoke-HealthInstaller([string]$Path,[int]$LimitMs=300000) {
    $start=[Diagnostics.ProcessStartInfo]::new()
    $start.FileName=$Path;$start.Arguments='/S /currentuser';$start.WorkingDirectory=[IO.Path]::GetDirectoryName($Path)
    $start.UseShellExecute=$false;$start.CreateNoWindow=$true;$start.WindowStyle='Hidden'
    $process=[Diagnostics.Process]::new();$process.StartInfo=$start
    try{
        Require ($process.Start()) 'installer-start-failed'
        $script:installerStarted=$true
        $retained=$process.Handle
        Require ($retained -ne [IntPtr]::Zero) 'installer-native-handle'
        $identity=[ordered]@{path=$Path;pid=$process.Id;started_at_utc=$process.StartTime.ToUniversalTime().ToString('o');arguments=$start.Arguments;handle_retained=$true}
        SaveJson 'installer-start' $identity
        Require ($process.WaitForExit($LimitMs)) 'installer-timeout-no-force-no-retry'
        Require ($process.HasExited -and $null -ne $process.ExitCode) 'installer-exit-unavailable'
        $script:installerExit=[ordered]@{identity=$identity;actual_exit_code=[int]$process.ExitCode;ended_at_utc=[DateTimeOffset]::UtcNow.ToString('o');forced_termination=$false}
        SaveJson 'installer-exit' $script:installerExit
        Require ($process.ExitCode -eq 0) 'installer-nonzero-exit'
    }finally{$process.Dispose()}
}
function Invoke-HealthInstallTransaction([IO.Stream]$RequestStream,[string]$RequestSha,[string]$Factory,[string]$InstallRoot,[string[]]$Roots,[string]$OperatorSid,[IO.Stream]$LibraryStream,[IO.Stream]$ControllerStream) {
    Require ($RequestSha -cmatch '^[a-f0-9]{64}$' -and (HashStream $RequestStream) -ceq $RequestSha) 'health-request-stream-pin'
    Require ((HashStream $LibraryStream) -ceq 'a95ec69d7fef3371745ad32685fa10b26f858ef9f93fe1a8669c39b25e225c1a') 'health-library-stream-pin'
    Require ($ControllerStream.Length -gt 0 -and $ControllerStream.Length -lt 1MB) 'health-controller-stream'
    $Request=ReadLockedJson $RequestStream
    Assert-HealthInstallRequest $Request
    $pins=Get-HealthInstallPins $Request.candidate_commit
    $Factory=Plain $Factory;$InstallRoot=Plain $InstallRoot
    $Roots=@($Roots|ForEach-Object{Plain $_})
    Assert-HealthInstallPaths $Request $Factory $InstallRoot $Roots
    $observationRoot=Plain $Request.observation_root
    Require ([IO.Path]::GetDirectoryName($observationRoot) -ieq $Factory -and
        [IO.Path]::GetFileName($observationRoot) -cmatch '^O[0-9a-f]{8}$') 'observation-root-contract'
    $script:resultRoot=$Factory+'\J'+[Guid]::NewGuid().ToString('N').Substring(0,8)
    Require (-not (Test-Path -LiteralPath $script:resultRoot)) 'fresh-result-required'
    $acl=[Security.AccessControl.DirectorySecurity]::new();$acl.SetAccessRuleProtection($true,$false)
    $acl.SetOwner([Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))
    foreach($reader in @('S-1-5-32-544','S-1-5-18',$OperatorSid)){
        $rights=if($reader -ceq $OperatorSid){'ReadAndExecute'}else{'FullControl'}
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($reader),$rights,'ContainerInherit,ObjectInherit','None','Allow'))
    }
    $null=[IO.Directory]::CreateDirectory($script:resultRoot,$acl);AssertResultAcl $script:resultRoot $acl
    Save-HealthInput 'request.json' $RequestStream
    Save-HealthInput 'install-library.ps1' $LibraryStream
    Save-HealthInput 'install-controller.ps1' $ControllerStream
    $script:phase='closed-original-and-cold-preconditions'
    $observationStream=LockFile ($observationRoot+'\result.json') $Request.observation_result_sha256
    $observation=ReadLockedJson $observationStream;Save-HealthInput 'observation-result.json' $observationStream
    $null=LockFile ($observationRoot+'\observed.tsv') $Request.observation_manifest_sha256
    $closeStream=LockFile $Request.close_review_path $Request.close_review_sha256
    $review=ReadLockedJson $closeStream;Save-HealthInput 'close-review.json' $closeStream
    Assert-ClosedObservation $observation $review $observationRoot $Request.observation_result_sha256 $Request.observation_manifest_sha256 $Roots $Request.candidate_commit
    Assert-HealthCloseGeneration $observation $review $Request.candidate_commit
    $cold=ColdSnapshot;AssertCold $cold;SaveJson 'runtime-before' $cold
    # Historical permission context is preserved unchanged. It is not new-candidate approval evidence.
    $approval=LockFile $Request.field_sequence_approval_path $pins.sequence_approval
    Save-HealthInput 'historical-sequence-approval.json' $approval
    $oldStream=LockFile $Request.preceding_payload_reference $pins.previous_reference
    $oldReference=ReadLockedJson $oldStream;Save-HealthInput 'preceding-payload.json' $oldStream
    $newStream=LockFile $Request.payload_reference $pins.candidate_reference
    $newReference=ReadLockedJson $newStream;Save-HealthInput 'candidate-payload.json' $newStream
    SaveJson 'preceding-installed-files' (Get-HealthPayloadFacts $InstallRoot $oldReference $pins.previous_version)
    $candidate=Plain $Request.candidate_installer
    $null=LockFile $candidate $pins.candidate_installer $pins.candidate_installer_bytes
    $null=LockFile $Request.rollback_installer $pins.rollback_installer 163826264
    $installerPaths=@($candidate,$Request.rollback_installer)
    if($pins.ContainsKey('previous_installer')){
        $null=LockFile $Request.preceding_installer $pins.previous_installer $pins.previous_installer_bytes
        $installerPaths+=@($Request.preceding_installer)
    }
    foreach($path in $installerPaths){
        Require ((Get-AuthenticodeSignature -LiteralPath $path).Status.ToString() -ceq 'NotSigned') 'unsigned-installer-state'
    }
    ImportBackupEngine $Request.legacy_stream_engine
    Save-HealthInput 'legacy-stream-engine.dll' $script:held[$script:held.Count-1]
    Import-ObservationEngine $Request.observation_engine
    Save-HealthInput 'observation-engine.dll' $script:held[$script:held.Count-1]
    $guard=[Action]{AssertCold (ColdSnapshot)}
    $progress=[Action[string,long,long,long]]{param($phase,$bytes,$files,$elapsed) Write-Host ('VERIFY phase='+$phase+' files='+$files+' bytes='+$bytes)}
    $engine=[SflColdObservationV1.Observer]::new($Roots,$guard,$progress)
    $script:phase='preinstall-original-data-reverification'
    $reverification=Invoke-HealthOriginalReverification $engine ($observationRoot+'\observed.tsv') $Request.observation_manifest_sha256 $observation.totals
    SaveJson 'original-data-before-install' $reverification.totals
    $script:phase='preinstall-configuration-and-freshness'
    $installerFacts=@{candidate=(Fact $candidate);rollback=(Fact $Request.rollback_installer);signature_policy='UNSIGNED_INTERNAL'}
    if($pins.ContainsKey('previous_installer')){$installerFacts.preceding=Fact $Request.preceding_installer}
    SaveJson 'installer-inputs' $installerFacts
    $configPath=$Roots[0]+'\config.ini'
    Require ((Fact $configPath).sha256 -ceq $Request.config_sha256) 'preinstall-config-pin'
    $configBefore=[IO.File]::ReadAllBytes($configPath);Assert-HealthConfiguration $configBefore
    $configStreams=ConfigStreamFacts $configPath
    [IO.File]::WriteAllBytes($script:resultRoot+'\config-before.ini',$configBefore)
    Require ((Fact ($script:resultRoot+'\config-before.ini')).sha256 -ceq $Request.config_sha256) 'captured-config-pin'
    AssertCold (ColdSnapshot)
    Assert-ObservationInstallSpace $Factory
    SaveJson 'original-data-before-install-freshness' @{baseline_observation_time=$observation.time;
        baseline_observation_result_sha256=$Request.observation_result_sha256;
        baseline_manifest_sha256=$Request.observation_manifest_sha256;
        full_reverification_started_at_utc=$reverification.started_at_utc;
        full_reverification_finished_at_utc=$reverification.finished_at_utc;
        elapsed_since_reverification_ms=$reverification.freshness_clock.ElapsedMilliseconds;
        maximum_elapsed_ms=120000;full_original_reverification_completed=$true}
    Assert-HealthReverificationFreshness $reverification
    $script:phase='installer';Invoke-HealthInstaller $candidate
    $script:phase='installed-payload';AssertCold (ColdSnapshot)
    SaveJson 'installed-files' (Get-HealthPayloadFacts $InstallRoot $newReference $pins.candidate_version)
    $registrations=@(Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*'|Where-Object{$_.PSObject.Properties['DisplayName'] -and $_.DisplayName -like '*smart-factory*'})
    Require ($registrations.Count -eq 1 -and $registrations[0].DisplayVersion -ceq $pins.candidate_version -and
        $registrations[0].UninstallString -like ('*'+$InstallRoot+'\Uninstall smart-factory.exe*')) 'installed-registration'
    $location=(Get-ItemProperty -LiteralPath ('HKCU:\Software\'+$registrations[0].PSChildName) -Name InstallLocation).InstallLocation
    Require ($location -ieq $InstallRoot) 'registered-install-location'
    SaveJson 'registration' (RegistrationFacts $registrations[0] $location)
    $script:phase='postinstall-original-data-preservation'
    $verified=$engine.Verify($observationRoot+'\observed.tsv',$Request.observation_manifest_sha256.ToUpperInvariant())
    Assert-ObservationTotals $verified $observation.totals
    SaveJson 'preserved-data' $verified
    Require ((Fact $configPath).sha256 -ceq $Request.config_sha256) 'configuration-byte-preservation'
    Require (((ConfigStreamFacts $configPath)|ConvertTo-Json -Compress) -ceq ($configStreams|ConvertTo-Json -Compress)) 'configuration-stream-preservation'
    SaveJson 'configuration-preserved' @{before=(Fact ($script:resultRoot+'\config-before.ini'));after=(Fact $configPath);named_streams=$configStreams;configuration_changed=$false;low_signal_alarm_enabled=$false;comparator_verified=$false;new_runtime_attestation_applied=$false}
    AssertCold (ColdSnapshot);$script:phase='complete-pending-standard-user-start'
    SaveJson 'result' ([ordered]@{schema='sfl-health-observed-install-result-v1';status='CANDIDATE_INSTALLED_CONFIGURATION_PRESERVED_PENDING_RUNTIME';phase=$script:phase;request_sha256=$RequestSha;candidate_commit=$Request.candidate_commit;preceding_commit=$Request.preceding_commit;installer_exit=$script:installerExit;observation_result_sha256=$Request.observation_result_sha256;installed_payload_verified=$true;original_data_default_and_named_streams_preserved=$true;original_metadata_and_membership_preserved=$true;new_full_data_backup_created=$false;configuration_changed=$false;physical_boundary='NOT_TESTED';formal_qa='HOLD';release_gate='HOLD';promotion_allowed=$false;application_started=$false;automatic_rollback=$false;evidence_files=(ReceiptFacts)})
    Write-Host ('RESULT_PATH='+$script:resultRoot)
    Write-Host ('RESULT_SHA256='+(Fact ($script:resultRoot+'\result.json')).sha256)
}

try {
    $native=[Environment]::SystemDirectory+'\WindowsPowerShell\v1.0\powershell.exe'
    $sid='S-1-5-21-2762931165-1280404403-2847611662-1001'
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
    $principal=[Security.Principal.WindowsPrincipal]::new($identity)
    if(-not ([Environment]::Is64BitProcess -and $PSVersionTable.PSEdition -ceq 'Desktop' -and
        $PSVersionTable.PSVersion.Major -eq 5 -and $PSVersionTable.PSVersion.Minor -eq 1 -and
        [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName -ieq $native)){throw 'native-ps51-x64-required'}
    if(-not ($env:COMPUTERNAME -ceq 'DESKTOP-CIIT7LK' -and $identity.User.Value -ceq $sid -and
        $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))){throw 'server-operator-admin-required'}
    if($env:APPDATA -ine 'C:\Users\user\AppData\Roaming' -or $env:LOCALAPPDATA -ine 'C:\Users\user\AppData\Local'){throw 'operator-profile'}
    if([string]::IsNullOrEmpty($LibraryPath)){$LibraryPath=Join-Path $PSScriptRoot 'install-field-candidate.ps1'}
    $env:PATH=[Environment]::SystemDirectory+';'+[IO.Path]::GetDirectoryName($native)
    $env:PSModulePath=[IO.Path]::GetDirectoryName($native)+'\Modules'
    $library=[IO.File]::Open($LibraryPath,'Open','Read','Read');$script:held.Add($library)
    $sha=[Security.Cryptography.SHA256]::Create()
    try{$digest=[BitConverter]::ToString($sha.ComputeHash($library)).Replace('-','').ToLowerInvariant()}finally{$sha.Dispose()}
    if($digest -cne 'a95ec69d7fef3371745ad32685fa10b26f858ef9f93fe1a8669c39b25e225c1a'){throw 'install-library-pin'}
    $library.Position=0;$reader=[IO.StreamReader]::new($library,[Text.UTF8Encoding]::new($false,$true),$true,4096,$true)
    try{$text=$reader.ReadToEnd()}finally{$reader.Dispose()}
    $tokens=$null;$parseErrors=$null;$ast=[Management.Automation.Language.Parser]::ParseInput($text,[ref]$tokens,[ref]$parseErrors)
    if($parseErrors.Count){throw 'install-library-parse'}
    foreach($definition in $ast.FindAll({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst]},$false)){
        . ([scriptblock]::Create($definition.Extent.Text))
    }
    $null=Plain $LibraryPath
    $requestStream=LockFile $RequestPath $ExpectedRequestSha256
    $controllerStream=LockFile $PSCommandPath (Fact $PSCommandPath).sha256
    $factory=Plain ([Environment]::GetFolderPath('Desktop')+'\SmartFactory')
    Require ($factory -ieq 'C:\Users\user\Desktop\SmartFactory') 'desktop-root'
    Invoke-HealthInstallTransaction $requestStream $ExpectedRequestSha256 $factory 'C:\Users\user\AppData\Local\Programs\smart-factory-logger-v2' @('C:\Users\user\AppData\Roaming\SmartFactoryLogger','C:\Users\user\AppData\Roaming\smart-factory-logger-v2') $sid $library $controllerStream
    exit 0
} catch {
    $failure=$_.Exception.Message
    if($script:resultRoot -and [IO.Directory]::Exists($script:resultRoot)){
        SaveJson 'hold' @{status='HOLD';phase=$script:phase;error=$failure;installer_started=$script:installerStarted;installer_exit=$script:installerExit;configuration_changed=$false;automatic_rollback=$false;force_calls=0;promotion_allowed=$false;evidence_files=(ReceiptFacts)}
        Write-Host ('RESULT_PATH='+$script:resultRoot)
        Write-Host ('HOLD_SHA256='+(Fact ($script:resultRoot+'\hold.json')).sha256)
    }
    Write-Host ('INSTALL_HOLD='+$failure);exit 1
} finally {foreach($handle in $script:held){$handle.Dispose()}}
