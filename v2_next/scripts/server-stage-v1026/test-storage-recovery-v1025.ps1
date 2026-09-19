param([Parameter(Mandatory=$true)][string]$OutputRoot)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$source=Join-Path $PSScriptRoot 'read-storage-recovery-v1025.ps1'
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($source,[ref]$tokens,[ref]$errors)
if($errors.Count -ne 0){throw ($errors|Out-String)}
$checks=[Collections.Generic.List[string]]::new()
function Check {param([bool]$OK,[string]$Name) if(-not $OK){throw ('TEST FAILED: '+$Name)};$checks.Add($Name)}
function Reject {param([scriptblock]$Code,[string]$Name) $failed=$false;try{& $Code|Out-Null}catch{$failed=$true};Check $failed $Name}
$functions=@($ast.FindAll({param($n)$n -is [Management.Automation.Language.FunctionDefinitionAst]},$true))
foreach($fn in $functions){. ([scriptblock]::Create($fn.Extent.Text))}
$text=[IO.File]::ReadAllText($source)
Check ($functions.Count -eq 17) 'parse and import only functions; no server main'
$allowed=@($functions.Name)+@('Set-StrictMode','ConvertFrom-Json','ConvertTo-Json','New-Object','Get-Process','Get-NetTCPConnection',
    'Select-Object','Where-Object','Sort-Object','Get-CimInstance','Invoke-CimMethod','Write-Host','Start-Sleep')
foreach($command in @($ast.FindAll({param($n)$n -is [Management.Automation.Language.CommandAst]},$true)|ForEach-Object {$_.GetCommandName()}|Sort-Object -Unique)) {
    Check ($null -ne $command -and $command -cin $allowed) ('allowed command: '+$command)
}
Check ($text -notmatch 'CreateDirectory|WriteAll|WriteAllBytes|Set-Content|Out-File|Copy-Item|Move-Item|Remove-Item|Start-Process|Stop-Process|Invoke-Expression|Import-Module') 'no filesystem mutation, process mutation or product import'
Check ($text -notmatch '\.CommandLine|GetEnvironmentVariables|GetEnvironmentVariable|ReadAllText|ReadAllBytes') 'no environment dump, command-line dump or unbounded file body read'
Check ($text.Contains('$r.Method=''GET'';$r.Proxy=$null;$r.AllowAutoRedirect=$false')) 'only GET with no proxy/redirect'
$queries=@($ast.FindAll({param($n)$n -is [Management.Automation.Language.CommandAst] -and $n.GetCommandName() -ceq 'LocalGet'},$true))
Check ($queries.Count -eq 5) 'five local API calls in main'
$cim=@($ast.FindAll({param($n)$n -is [Management.Automation.Language.CommandAst] -and $n.GetCommandName() -ceq 'Invoke-CimMethod'},$true))
Check ($cim.Count -eq 1 -and $cim[0].Extent.Text.EndsWith('-MethodName GetOwnerSid')) 'CIM method limited to read-only process owner query'
foreach($bad in @('api/observability/export','api/observability/errors/clear','api/spot/live_image.jpg','api/spot/focus','api/config?x=1','http://outside.invalid')) {
    Reject {LocalGet $bad} ('reject before network: '+$bad)
}
foreach($bad in @('null','[]','[{}]','false','2','"abc"','')) {Reject {Decode $bad} ('invalid JSON root: '+$bad)}
Check ((Counter (Decode '{"count":3}') 'count') -eq 3) 'integer counter'
foreach($bad in @('null','-1','1.5','"1"','[]','[1]','true','{}')) {Reject {Counter (Decode ('{"count":'+$bad+'}')) 'count'} ('counter invalid: '+$bad)}
Reject {Field (Decode '{"value":[{}]}') 'value'} 'singleton object array rejected'
Reject {Field (Decode '{}') 'missing'} 'missing field rejected'
Check ((FullLocal 'C:/Users/user/AppData/Roaming/SmartFactoryLogger') -ceq 'C:\Users\user\AppData\Roaming\SmartFactoryLogger') 'slash normalization'
foreach($bad in @('C:\','C:relative','\relative','relative','\\server\share\data','\\?\C:\data','file:///C:/data','C:\data\..\outside',
    'C:\data\.', 'C:\data\\child','C:\data\secret:stream','C:\data\CON','C:\data\con.txt','C:\data\x.','C:\data\x ',
    'C:\data\x*','C:\data\x?','C:\data\PROGRA~1',('C:\data\x'+[char]10+'z'),('C:\'+('x'*240)))) {Reject {FullLocal $bad} ('unsafe path rejected: '+$checks.Count)}
Reject {FullLocal @('C:\data')} 'array path rejected'
Check (Within 'C:\scope\child' 'c:\SCOPE') 'case-insensitive child boundary'
Check (-not (Within 'C:\scope-other\child' 'C:\scope')) 'prefix sibling not child'
Check (-not (Within 'C:\scope2' 'C:\scope')) 'prefix sibling not equal'

if([IO.File]::Exists($OutputRoot) -or [IO.Directory]::Exists($OutputRoot)){throw 'Existing test evidence is preserved.'}
$fixtureRoot=[IO.Path]::GetFullPath($OutputRoot)
[void][IO.Directory]::CreateDirectory($fixtureRoot)
$appDataRoot=Join-Path $fixtureRoot 'AppData'
$electronRoot=Join-Path $fixtureRoot 'Electron'
$backendRoot=Join-Path $fixtureRoot 'InstalledBackend'
$dataRoot=Join-Path $appDataRoot 'logs\test_data'
$configPath=Join-Path $appDataRoot 'config.ini'
$recoveryExe=Join-Path $fixtureRoot 'recovery.exe'
$backupCandidateRoot=Join-Path $fixtureRoot 'SuggestedBackup'
$allowedRoots=@($appDataRoot,$electronRoot,$backendRoot,$backupCandidateRoot)
foreach($dir in @($dataRoot,$electronRoot,$backendRoot)){[void][IO.Directory]::CreateDirectory($dir)}
Check ((Approved $configPath) -ceq $configPath) 'approved config path'
Check ((Approved $recoveryExe) -ceq $recoveryExe) 'exact recovery file allowed'
Reject {Approved (Join-Path $fixtureRoot 'sibling\data')} 'unapproved root rejected'
Reject {Approved ($appDataRoot+'-extra\secret')} 'approved prefix sibling rejected'
Reject {Approved ($recoveryExe+'.unapproved')} 'recovery prefix sibling rejected'
$missing=Metadata (Join-Path $appDataRoot 'missing\file.json')
Check (-not $missing.exists -and $null -eq $missing.bytes) 'missing metadata explicit; not zero bytes'
Check ((Metadata $appDataRoot).kind -ceq 'directory') 'existing directory metadata'
[IO.File]::WriteAllText($configPath,'fixed synthetic config',[Text.UTF8Encoding]::new($false))
[IO.File]::WriteAllText($recoveryExe,'not an executable; hash fixture',[Text.UTF8Encoding]::new($false))
$configExpected=TextHash 'fixed synthetic config'
$hash=BoundedHash $configPath $configExpected 1024 $true
Check ($hash.matches_pin -and $hash.sha256 -ceq $configExpected) 'real bounded shared hash'
$writer=[IO.File]::Open($configPath,'Open','ReadWrite',([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
try {Check ((BoundedHash $configPath $configExpected 1024 $true).matches_pin) 'concurrent writer handle allowed'} finally {$writer.Dispose()}
Reject {BoundedHash $configPath ('0'*64) 1024 $true} 'wrong external hash rejected'
Reject {BoundedHash $configPath $configExpected 1 $true} 'size budget rejected'
Reject {BoundedHash (Join-Path $appDataRoot 'state.json') $configExpected 1024 $true} 'state/profile body read rejected'
Check ((BoundedHash $recoveryExe (TextHash 'not an executable; hash fixture') 1024 $false).matches_pin) 'static recovery bytes hash; never executed'
[IO.File]::WriteAllText((Join-Path $dataRoot 'Factory_Integrated_Log_20260912_001000.csv'),'abc')
[IO.File]::WriteAllText((Join-Path $dataRoot 'unknown-secret-name.txt'),'private content not read')
[void][IO.Directory]::CreateDirectory((Join-Path $dataRoot 'spot_images'))
$summary=DirectorySummary $dataRoot
Check ($summary.enumeration_complete -and -not $summary.recursive -and $summary.files -eq 2 -and $summary.directories -eq 1) 'real nonrecursive metadata inventory'
Check ($summary.latest_csv.Count -eq 1 -and $summary.file_types.csv -eq 1 -and -not $summary.bytes_are_backup_size) 'generated CSV selected without full-backup claim'
Check (($summary|ConvertTo-Json -Depth 8) -notmatch 'unknown-secret-name|private content') 'unapproved names/content not exposed'
$limited=DirectorySummary $dataRoot 1
Check (-not $limited.enumeration_complete -and $limited.immediate_entries -eq 1) 'truncation explicitly reported'
Reject {DirectorySummary $dataRoot 0} 'zero enumeration limit rejected'
$missingSummary=DirectorySummary (Join-Path $appDataRoot 'missing-folder')
Check (-not $missingSummary.exists -and $null -eq $missingSummary.files -and -not $missingSummary.enumeration_complete) 'missing folder not empty/complete'
[void][IO.Directory]::CreateDirectory($backupCandidateRoot)
[IO.File]::WriteAllText((Join-Path $backupCandidateRoot 'installer-private-name.zip'),'not a backup')
$backup=DirectorySummary $backupCandidateRoot
Check ($backup.file_types.archive -eq 1 -and $backup.archive_metadata.Count -eq 1) 'suggested backup folder archive metadata counted'
Check (-not $backup.archive_metadata[0].is_verified_backup -and -not $backup.archive_metadata[0].contents_opened) 'installer archive not approved as backup'
Check (($backup|ConvertTo-Json -Depth 8) -notmatch 'installer-private-name|not a backup') 'arbitrary archive name and contents withheld'

function ConfigFixture {
    return [pscustomobject]@{config_path=$configPath;restart_required=$false;values=[pscustomobject]@{
        settings=[pscustomobject]@{logpath=$dataRoot;snapshotpath=($appDataRoot+'\snapshots')};
        spot=[pscustomobject]@{image_capture=[pscustomobject]@{path='spot_images'}}}}
}
$configured=StorageSettings (ConfigFixture)
Check (-not $configured.active_runtime_paths_proven -and -not $configured.pending_restart) 'configured values not runtime proof'
$mut=ConfigFixture;$mut.values.settings.logpath='\\private-host\share';Reject {StorageSettings $mut} 'configured UNC not accessed'
$mut=ConfigFixture;$mut.values.settings.logpath=$backendRoot;Reject {StorageSettings $mut} 'changed configured root rejected before enumeration'
$mut=ConfigFixture;$mut.values.spot.image_capture.path='..\outside';Reject {StorageSettings $mut} 'relative capture escape rejected'
$mut=ConfigFixture;$mut.restart_required=$true;Reject {StorageSettings $mut} 'pending restart rejected'
$mut=ConfigFixture;$mut.restart_required='false';Reject {StorageSettings $mut} 'string false rejected'
$mut=ConfigFixture;$mut.config_path=@($configPath);Reject {StorageSettings $mut} 'singleton config path array rejected'

$captureId='spotimg_20260911T150145123456Z_123456abcdef'
$captureRelative='spot_images/2026/09/11/'+$captureId+'.jpg'
$captureFile=Join-Path $dataRoot $captureRelative.Replace('/','\')
[void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($captureFile))
[IO.File]::WriteAllText($captureFile,'synthetic image; not decoded')
function CaptureFixture {
    return [pscustomobject]@{image_capture=[pscustomobject]@{last_capture_id=$captureId;last_capture_path=$captureRelative;enabled=$true;
        written_count=10;enqueued_count=10;dropped_count=467;failure_count=0;queue_size=0}}
}
$capture=RecentCapture (CaptureFixture)
Check ($capture.candidate_path_exists -and -not $capture.content_hash_verified -and -not $capture.entire_capture_root_proven) 'actual capture metadata exists; no image content or active-root proof'
foreach($bad in @($null,'','../escape.jpg','C:\private\image.jpg','\\private\share','spot_images/../file.jpg',($captureRelative+'?secret=1'))) {
    $mut=CaptureFixture;$mut.image_capture.last_capture_path=$bad;Reject {RecentCapture $mut} 'bad live capture path rejected before disk access'
}
$mut=CaptureFixture;$mut.image_capture.last_capture_id='different';Reject {RecentCapture $mut} 'capture ID mismatch rejected'
$mut=CaptureFixture;$mut.image_capture.written_count=@(1);Reject {RecentCapture $mut} 'capture counter array rejected'
$mut=CaptureFixture;$mut.image_capture.enabled='true';Reject {RecentCapture $mut} 'capture enabled string rejected'
$mut=CaptureFixture;$mut.image_capture.last_capture_path='spot_images/2026/09/10/'+$captureId+'.jpg'
Check (-not (RecentCapture $mut).candidate_path_exists) 'missing last capture file reported, not defaulted to zero-size success'

# Deterministic reparse/denied-access tests; no native symlink creation or system policy changes.
$savedAttr=(Get-Item Function:AttributesOrMissing).ScriptBlock
function AttributesOrMissing {param([string]$Path) if($Path -ieq $appDataRoot){return [IO.FileAttributes]::Directory -bor [IO.FileAttributes]::ReparsePoint};return [IO.FileAttributes]::Directory}
Reject {Metadata $configPath} 'ancestor reparse rejected before descendant metadata'
Set-Item Function:AttributesOrMissing $savedAttr
$denied=New-Object IO.IOException 'synthetic access failure'
$savedMetadata=(Get-Item Function:Metadata).ScriptBlock
function Metadata {param([string]$Path) throw 'STORAGE_CHECK:metadata-access-failed'}
Reject {DirectorySummary $dataRoot} 'access failure is HOLD, not an empty inventory'
Set-Item Function:Metadata $savedMetadata
SameRuntime ([pscustomobject]@{main_pid=1;main_ticks=2;backend_pid=3;backend_ticks=4}) ([pscustomobject]@{main_pid=1;main_ticks=2;backend_pid=3;backend_ticks=4})
Check $true 'same process instance'
Reject {SameRuntime ([pscustomobject]@{main_pid=1;main_ticks=2;backend_pid=3;backend_ticks=4}) ([pscustomobject]@{main_pid=1;main_ticks=2;backend_pid=3;backend_ticks=5})} 'PID reuse rejected'
foreach($flag in @('active_storage_paths_fully_verified','electron_profile_path_directly_observed','process_environment_audited','all_file_content_readability_verified',
    'backup_size_verified','backup_destination_selected','existing_backup_verified','consistent_backup_created','restore_test_performed','profile_downgrade_tested','installation_ready',
    'file_writes_performed','application_restart_performed','installation_started','automatic_rollback_performed','product_changes_made','new_camera_requests','packet_capture_started','production_promotion_allowed')) {
    Check ($text.Contains($flag+'=$false')) ('no premature approval or unauthorized action: '+$flag)
}
$result=[pscustomobject]@{result='V1025_STORAGE_RECOVERY_LOCAL_FIXTURES_PASS';assertions=$checks.Count;powershell_version=$PSVersionTable.PSVersion.ToString();
    source_sha256=(TextHash $text);server_main_executed=$false;network_queries_performed=$false;product_changes_made=$false;
    real_metadata_and_shared_hash_fixtures=$true;native_reparse_race_tested=$false;checks=$checks.ToArray()}
$json=$result|ConvertTo-Json -Depth 6
[IO.File]::WriteAllText((Join-Path $fixtureRoot 'validation-result.json'),$json,[Text.UTF8Encoding]::new($false))
$json
