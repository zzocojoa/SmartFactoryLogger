param([Parameter(Mandatory=$true)][string]$OutputRoot)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$source=Join-Path $PSScriptRoot 'install-health-observed.ps1'
$library=Join-Path $PSScriptRoot 'install-field-candidate.ps1'
if(Test-Path -LiteralPath $OutputRoot){throw 'New test output required'}
$null=[IO.Directory]::CreateDirectory($OutputRoot)
$script:held=[Collections.Generic.List[IDisposable]]::new()
$checks=[Collections.Generic.List[string]]::new()
function Pass([bool]$Value,[string]$Name){if(-not $Value){throw ('FAILED: '+$Name)};$checks.Add($Name)}
function Reject([scriptblock]$Action,[string]$Message,[string]$Name){
    $caught=$null;try{& $Action}catch{$caught=$_.Exception.Message}
    Pass ($null -ne $caught -and $caught.Contains($Message)) ($Name+': '+$caught)
}
foreach($path in @($library,$source)){
    $tokens=$null;$errors=$null
    $ast=[Management.Automation.Language.Parser]::ParseFile($path,[ref]$tokens,[ref]$errors)
    Pass ($errors.Count -eq 0) ('parse:'+ [IO.Path]::GetFileName($path))
    foreach($definition in $ast.FindAll({param($n)$n -is [Management.Automation.Language.FunctionDefinitionAst]},$false)){
        . ([scriptblock]::Create($definition.Extent.Text))
    }
}
Pass ((Fact $library).sha256 -ceq 'a95ec69d7fef3371745ad32685fa10b26f858ef9f93fe1a8669c39b25e225c1a') 'unchanged-legacy-library-pin'
$pins=Get-HealthInstallPins
$request=[pscustomobject][ordered]@{
    schema='sfl-health-observed-install-request-v1';candidate_commit=$pins.candidate_commit;preceding_commit=$pins.previous_commit
    signature_policy='UNSIGNED_INTERNAL';field_sequence_approval_path='C:\inputs\approval.json';field_sequence_approval_sha256=$pins.sequence_approval
    observation_root='C:\factory\O12345678';observation_result_sha256=('a'*64);observation_manifest_sha256=('b'*64)
    close_review_path='C:\inputs\close.json';close_review_sha256=('c'*64);candidate_installer='C:\inputs\candidate.exe'
    rollback_installer='C:\inputs\rollback.exe';preceding_payload_reference='C:\inputs\previous.json'
    payload_reference='C:\inputs\candidate.json';legacy_stream_engine='C:\inputs\engine.dll';observation_engine='C:\inputs\observation.dll';new_full_backup_policy='OMITTED_FOR_1029_HEALTH_ONLY';config_sha256=('d'*64)
}
Assert-HealthInstallRequest $request;Pass $true 'exact-new-build-request-accepted'
$request.signature_policy='SIGNED';Reject {Assert-HealthInstallRequest $request} 'request-identity' 'reject-wrong-signature-policy';$request.signature_policy='UNSIGNED_INTERNAL'
$request.preceding_commit='541d701d544eea6a8a4e4836047077eaf9cfaf30';Reject {Assert-HealthInstallRequest $request} 'request-identity' 'reject-other-previous-build';$request.preceding_commit=$pins.previous_commit
$request.config_sha256='D'*64;Reject {Assert-HealthInstallRequest $request} 'health-install-pin:config_sha256' 'reject-invalid-external-pin';$request.config_sha256='d'*64
$request|Add-Member unexpected $true;Reject {Assert-HealthInstallRequest $request} 'request-members' 'reject-unknown-request-member';$request.PSObject.Properties.Remove('unexpected')
Assert-HealthInstallPaths $request 'C:\factory' 'C:\installed' @('C:\data-a','C:\data-b');Pass $true 'disjoint-operating-and-input-paths'
Reject {Assert-HealthInstallPaths $request 'C:\factory' 'C:\installed' @('C:\data-a','C:\data-a')} 'distinct-roots' 'reject-duplicate-data-root'
Reject {Assert-HealthInstallPaths $request 'C:\factory' 'C:\factory\installed' @('C:\data-a','C:\data-b')} 'overlapping-roots' 'reject-overlapping-output-install-root'
$request.candidate_installer='C:\data-a\candidate.exe';Reject {Assert-HealthInstallPaths $request 'C:\factory' 'C:\installed' @('C:\data-a','C:\data-b')} 'input-inside-operating-root' 'reject-locked-input-in-preserved-data';$request.candidate_installer='C:\inputs\candidate.exe'

$identity=[pscustomobject]@{main_pid=123;main_created_at_utc='2026-10-15T01:02:03Z';backend_pid=456;backend_created_at_utc='2026-10-15T01:02:04Z'}
$backup=[pscustomobject]@{preceding_operating_identity=$identity}
$review=[pscustomobject]@{preceding_commit=$pins.previous_commit;main_pid=123;main_created_at_utc='2026-10-15T01:02:03Z';backend_pid=456;backend_created_at_utc='2026-10-15T01:02:04Z'}
Assert-HealthCloseGeneration $backup $review;Pass $true 'both-native-generations-bound'
Assert-HealthCloseGeneration ($backup|ConvertTo-Json -Depth 5|ConvertFrom-Json) ($review|ConvertTo-Json|ConvertFrom-Json)
Pass $true 'json-deserialized-native-pids-accepted'
$review.main_created_at_utc='2026-10-15T01:02:04Z';Reject {Assert-HealthCloseGeneration $backup $review} 'native-generation:main_created' 'reject-reused-main-pid';$review.main_created_at_utc=$identity.main_created_at_utc
$review.backend_pid=457;Reject {Assert-HealthCloseGeneration $backup $review} 'native-generation:backend_pid' 'reject-other-backend';$review.backend_pid=$identity.backend_pid
$review.main_pid=0;$identity.main_pid=0;Reject {Assert-HealthCloseGeneration $backup $review} 'native-pid' 'reject-invalid-native-pid';$review.main_pid=123;$identity.main_pid=123
$review.main_created_at_utc='2026-10-15T10:02:03+09:00';$identity.main_created_at_utc=$review.main_created_at_utc;Reject {Assert-HealthCloseGeneration $backup $review} 'native-time' 'reject-non-utc-time';$review.main_created_at_utc='2026-10-15T01:02:03Z';$identity.main_created_at_utc=$review.main_created_at_utc
$review.PSObject.Properties.Remove('backend_created_at_utc');Reject {Assert-HealthCloseGeneration $backup $review} 'native-generation:backend_created' 'reject-missing-native-time'


$review|Add-Member backend_created_at_utc $identity.backend_created_at_utc
$review|Add-Member schema 'sfl-observed-preinstall-close-review-v1'
$review|Add-Member observation_result_sha256 ('a'*64)
$review|Add-Member observation_manifest_sha256 ('b'*64)
$review|Add-Member normal_shutdown_observed $true
$review|Add-Member failed_checks @()
$review|Add-Member logger_service_instance_id 'fixture-logger'
$observation=[pscustomobject]@{schema='sfl-health-preservation-result-v1';status='CLOSED_ORIGINAL_OBSERVED_AND_REVERIFIED_NO_BACKUP';run_root='C:\factory\O12345678';source_roots=@('C:\data-a','C:\data-b');file_manifest_sha256=('B'*64);totals=[pscustomobject]@{Files=4;Directories=3;NamedStreams=3;Bytes=210;ManifestSha256=('B'*64);RecoverableBackupCreated=$false};original_default_named_streams_and_metadata_reverified=$true;app_backend_port_absence_observed=$true;new_full_data_backup_created=$false;installation_performed=$false;application_started=$false;preceding_operating_identity=$identity;preceding_logger_service_instance_id='fixture-logger';time=[DateTimeOffset]::UtcNow.ToString('o')}
function ValidateObservation {Assert-ClosedObservation $observation $review 'C:\factory\O12345678' ('a'*64) ('b'*64) @('C:\data-a','C:\data-b')}
ValidateObservation;Pass $true 'closed-observation-and-normal-close-binding'
$request.new_full_backup_policy='SKIP_ANY_BACKUP';Reject {Assert-HealthInstallRequest $request} 'request-identity' 'only-specific-health-no-copy-policy';$request.new_full_backup_policy='OMITTED_FOR_1029_HEALTH_ONLY'
$observation.status='SELECTED_COLD_COPY_DEFAULT_AND_NAMED_DATA_STREAMS_VERIFIED';Reject {ValidateObservation} 'observation-status' 'backup-result-not-accepted-as-observation';$observation.status='CLOSED_ORIGINAL_OBSERVED_AND_REVERIFIED_NO_BACKUP'
$observation.new_full_data_backup_created=$true;Reject {ValidateObservation} 'observation-actions' 'cannot-claim-fresh-backup';$observation.new_full_data_backup_created=$false
$observation.totals.RecoverableBackupCreated=$true;Reject {ValidateObservation} 'observation-not-backup' 'cannot-claim-recoverable-observation';$observation.totals.RecoverableBackupCreated=$false
$observation.application_started=$true;Reject {ValidateObservation} 'observation-actions' 'reject-restarted-after-observation';$observation.application_started=$false
$observation.source_roots=@('C:\other','C:\data-b');Reject {ValidateObservation} 'observation-scope' 'reject-other-source-roots';$observation.source_roots=@('C:\data-a','C:\data-b')
$review.schema='sfl-field-preinstall-close-review-v1';Reject {ValidateObservation} 'close-review-observation-binding' 'reject-old-backup-review-schema';$review.schema='sfl-observed-preinstall-close-review-v1'
$review.normal_shutdown_observed=$false;Reject {ValidateObservation} 'normal-shutdown-review' 'absence-alone-not-normal-close';$review.normal_shutdown_observed=$true
$review.failed_checks=@('worker-not-drained');Reject {ValidateObservation} 'normal-shutdown-review' 'reject-failed-close-check';$review.failed_checks=@()
$review.logger_service_instance_id='other';Reject {ValidateObservation} 'logger-generation' 'reject-other-logger';$review.logger_service_instance_id='fixture-logger'
$observation.time=[DateTimeOffset]::UtcNow.AddHours(-4).ToString('o');ValidateObservation;Pass $true 'old-reviewed-baseline-eligible-for-mandatory-full-reverification'
$observation.time=[DateTimeOffset]::UtcNow.AddMinutes(5).ToString('o');Reject {ValidateObservation} 'observation-time-in-future' 'reject-future-observation';$observation.time=[DateTimeOffset]::UtcNow.ToString('o')
$fresh=[pscustomobject]@{freshness_clock=[Diagnostics.Stopwatch]::StartNew()}
Assert-HealthReverificationFreshness $fresh;Pass $true 'fresh-monotonic-reverification-window'
Reject {Assert-HealthReverificationFreshness $fresh 120001} 'preinstall-reverification-freshness' 'cannot-extend-reverification-window'
Start-Sleep -Milliseconds 20
Reject {Assert-HealthReverificationFreshness $fresh 1} 'preinstall-reverification-freshness' 'reject-expired-monotonic-window'
$fresh.freshness_clock.Stop();Reject {Assert-HealthReverificationFreshness $fresh} 'preinstall-reverification-freshness' 'reject-stopped-verification-clock'
$fresh.freshness_clock=$null;Reject {Assert-HealthReverificationFreshness $fresh} 'preinstall-reverification-freshness' 'reject-missing-reverification-clock'
$observation.totals.Files=-1;Reject {ValidateObservation} 'original-preservation-totals' 'reject-negative-count';$observation.totals.Files=4

$text="[SPOT]`r`nlow_signal_alarm_enabled = false`r`nlow_signal_comparator_verified = false`r`n[OTHER]`r`nvalue = 보존 시험`r`n"
$encoding=[Text.UTF8Encoding]::new($true);$bytes=$encoding.GetPreamble()+$encoding.GetBytes($text)
$before=[Convert]::ToBase64String($bytes);Assert-HealthConfiguration $bytes
Pass ([Convert]::ToBase64String($bytes) -ceq $before) 'utf8-bom-crlf-korean-config-no-mutation'
Reject {Assert-HealthConfiguration $encoding.GetBytes($text.Replace('comparator_verified = false','comparator_verified = true'))} 'comparator-must-already-be-false' 'reject-config-that-would-require-mutation'
Reject {Assert-HealthConfiguration $encoding.GetBytes($text.Replace('alarm_enabled = false','alarm_enabled = true'))} 'alarm-must-be-false' 'reject-enabled-alarm'
$cp949=[Text.Encoding]::GetEncoding(949);Assert-HealthConfiguration $cp949.GetBytes($text);Pass $true 'cp949-config-accepted-without-mutation'
Reject {AssertCold @{processes=@(@{ProcessId=123});listeners=@()}} 'application-or-port-active' 'reject-running-app'
Reject {AssertCold @{processes=@();listeners=@(@{LocalPort=8000;OwningProcess=456})}} 'application-or-port-active' 'reject-owned-or-unrelated-port-listener'
Reject {Get-HealthPayloadFacts 'C:\unused' ([pscustomobject]@{version='1.0.26'}) 'unsupported'} 'payload-contract' 'reject-wrong-payload-version-before-filesystem-read'

$script:resultRoot=Join-Path $OutputRoot 'archive';$null=[IO.Directory]::CreateDirectory($script:resultRoot)
$raw=[Text.Encoding]::UTF8.GetBytes("{ `r`n  `"schema`" : `"spacing-and-newlines-preserved`"`r`n}`r`n")
$memory=[IO.MemoryStream]::new($raw)
try{Save-HealthInput 'request.json' $memory;Pass ([Convert]::ToBase64String([IO.File]::ReadAllBytes($script:resultRoot+'\request.json')) -ceq [Convert]::ToBase64String($raw)) 'original-request-bytes-archived';Reject {Save-HealthInput '../escape.json' $memory} 'input-name' 'reject-archive-path-escape'}finally{$memory.Dispose()}

$ok=Join-Path $OutputRoot 'health-ok.exe';$bad=Join-Path $OutputRoot 'health-bad.exe';$slow=Join-Path $OutputRoot 'health-slow.exe'
Add-Type -TypeDefinition 'public class HealthOk { public static int Main(string[] args) { return args.Length==2 && args[0]=="/S" && args[1]=="/currentuser" ? 0 : 91; } }' -OutputAssembly $ok -OutputType ConsoleApplication
Add-Type -TypeDefinition 'public class HealthBad { public static int Main() { return 17; } }' -OutputAssembly $bad -OutputType ConsoleApplication
Add-Type -TypeDefinition 'public class HealthSlow { public static int Main() { System.Threading.Thread.Sleep(2000); return 0; } }' -OutputAssembly $slow -OutputType ConsoleApplication
foreach($case in @('ok','bad','timeout')){
    $script:resultRoot=Join-Path $OutputRoot $case;$null=[IO.Directory]::CreateDirectory($script:resultRoot)
    $script:installerStarted=$false;$script:installerExit=$null
    if($case -eq 'ok'){
        Invoke-HealthInstaller $ok
        Pass ($script:installerStarted -and $script:installerExit.actual_exit_code -eq 0 -and $script:installerExit.identity.handle_retained) 'native-success-exit-args-and-retained-handle'
    }elseif($case -eq 'bad'){
        Reject {Invoke-HealthInstaller $bad} 'installer-nonzero-exit' 'reject-native-nonzero-exit'
        Pass ($script:installerExit.actual_exit_code -eq 17) 'native-failure-exit-preserved'
    }else{
        Reject {Invoke-HealthInstaller $slow 50} 'installer-timeout-no-force-no-retry' 'timeout-does-not-retry-or-force'
        $start=Get-Content -LiteralPath ($script:resultRoot+'\installer-start.json') -Raw|ConvertFrom-Json
        $process=[Diagnostics.Process]::GetProcessById($start.pid)
        try{
            Pass (-not $process.HasExited -and $process.StartTime.ToUniversalTime().ToString('o') -ceq $start.started_at_utc) 'timed-out-native-generation-still-alive'
            Pass ($process.WaitForExit(10000)) 'timed-out-fixture-exits-itself'
        }finally{$process.Dispose()}
        Pass ($null -eq $script:installerExit -and -not (Test-Path -LiteralPath ($script:resultRoot+'\installer-exit.json'))) 'timeout-not-misreported-as-completed'
    }
}
$result=[ordered]@{status='PASS';checks=$checks.Count;names=$checks.ToArray();source_sha256=(Fact $source).sha256;library_sha256=(Fact $library).sha256;server_accessed=$false;production_installation_performed=$false;forced_termination=$false}
[IO.File]::WriteAllText((Join-Path $OutputRoot 'tests-result.json'),($result|ConvertTo-Json -Depth 6),[Text.UTF8Encoding]::new($false))
$result|ConvertTo-Json -Depth 6
