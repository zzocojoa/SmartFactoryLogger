[CmdletBinding()]
param(
 [ValidateSet('Run','Guard','Recover')][string]$Mode='Run',
 [Parameter(Mandatory=$true)][string]$PackageRoot,
 [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedManifestSha256,
 [string]$ContractPath,[ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedContractSha256,
 [ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedReadySha256,
 [string]$RunPath,[ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedLeaseSha256
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'

function Get-HealthTracePolicy([string]$Scope){
 $schedulingProfile='603c872d5bb638661eb6e133f2b23b4f778e8bab5f440dbda3017c09ea0ff486'
 if($Scope -ceq 'LOCAL_HEALTH_READY_CONCURRENT_TRACE_DIAGNOSTIC'){
  return @{contract_schema='sfl-health-ready-concurrent-contract-v1';lease_schema='sfl-health-ready-concurrent-lease-v1';duration=900;guard=960;profile_sha256='03220768bee3245513b2ec4d9eeac2affd7ddffcd2c786f6a658146bdd8e2478'}
 }
 if($Scope -ceq 'LOCAL_INSTALLED_HEALTH_TRACE_DIAGNOSTIC'){
  return @{contract_schema='sfl-health-trace-contract-v1';lease_schema='sfl-health-trace-lease-v1';duration=6;guard=30;profile_sha256=$schedulingProfile}
 }
 if($Scope -ceq 'LOCAL_HEALTH_CPU_OUTLIER_TRACE_DIAGNOSTIC'){
  return @{contract_schema='sfl-health-cpu-outlier-contract-v1';lease_schema='sfl-health-cpu-outlier-lease-v1';duration=900;guard=960;profile_sha256='3ad310b110ead5c2867b9632ff96ec71e0381a030bac7f7ec91bddf5f5c94fee'}
 }
 if($Scope -ceq 'LOCAL_HEALTH_CPU_CONCURRENT_TRACE_DIAGNOSTIC'){
  return @{contract_schema='sfl-health-cpu-concurrent-contract-v1';lease_schema='sfl-health-cpu-concurrent-lease-v1';duration=900;guard=960;profile_sha256='3ad310b110ead5c2867b9632ff96ec71e0381a030bac7f7ec91bddf5f5c94fee'}
 }
 Assert-Trace ($Scope -ceq 'LOCAL_HEALTH_OUTLIER_TRACE_DIAGNOSTIC') 'health-trace-scope'
 return @{contract_schema='sfl-health-outlier-contract-v1';lease_schema='sfl-health-outlier-lease-v1';duration=900;guard=960;profile_sha256=$schedulingProfile}
}
function Assert-HealthTraceContract($Contract,[string]$Channel,[string]$PackageSha){
 $policy=Get-HealthTracePolicy $Contract.scope
 Assert-Trace ($Contract.schema -ceq $policy.contract_schema) 'health-trace-contract-schema'
 Assert-Trace (@($Contract.PSObject.Properties).Count -eq 12) 'health-trace-contract-members'
 Assert-Trace ($Contract.run_id -cmatch '^[0-9a-f]{32}$' -and $Contract.channel_path -ieq $Channel -and [IO.Path]::GetFileName($Channel) -ceq 'trace-channel') 'health-trace-channel-run'
 Assert-Trace ($Contract.package_sha256 -ceq $PackageSha) 'health-trace-package-binding'
 Assert-Trace ($Contract.duration_seconds -is [int] -and $Contract.duration_seconds -eq $policy.duration -and $Contract.guard_seconds -is [int] -and $Contract.guard_seconds -eq $policy.guard) 'health-trace-contract-budget'
 Assert-Trace ($Contract.backend_pid -is [int] -and $Contract.backend_pid -gt 0 -and $Contract.main_pid -is [int] -and $Contract.main_pid -gt 0 -and $Contract.main_pid -ne $Contract.backend_pid) 'health-trace-app-pids'
 Assert-Trace ($Contract.backend_created_filetime -is [long] -and $Contract.backend_created_filetime -gt 0) 'health-trace-backend-generation'
 Assert-Trace ($Contract.release_gate -ceq 'HOLD' -and $Contract.promotion_allowed -is [bool] -and -not $Contract.promotion_allowed) 'health-trace-contract-gates'
}
function Assert-HealthTraceLease($Lease,[string]$Directory,[string]$PackageSha){
 $policy=Get-HealthTracePolicy $Lease.scope
 Assert-Trace ($Lease.schema -ceq $policy.lease_schema) 'health-trace-lease-schema'
 Assert-Trace ($Lease.instance -cmatch '^SFLTrace_[0-9a-f]{32}$' -and $Lease.run_id -cmatch '^[0-9a-f]{32}$') 'health-trace-lease-id'
 Assert-Trace ($Lease.run_path -ieq $Directory -and $Lease.parent_pid -is [int] -and $Lease.parent_pid -gt 0 -and $Lease.parent_created_filetime -cmatch '^[0-9]{17,20}$') 'health-trace-parent'
 Assert-Trace ($Lease.guard_seconds -is [int] -and $Lease.guard_seconds -eq $policy.guard -and $Lease.capture_seconds -is [int] -and $Lease.capture_seconds -eq $policy.duration -and $Lease.stop_timeout_seconds -is [int] -and $Lease.stop_timeout_seconds -eq 60) 'health-trace-lease-budget'
 Assert-Trace ($Lease.contract_sha256 -cmatch '^[0-9a-f]{64}$' -and $Lease.package_sha256 -ceq $PackageSha) 'health-trace-lease-pins'
 Assert-Trace ($Lease.profile_sha256 -ceq $policy.profile_sha256) 'health-trace-profile-pin'
 Assert-Trace ($Lease.release_gate -ceq 'HOLD' -and $Lease.promotion_allowed -is [bool] -and -not $Lease.promotion_allowed) 'health-trace-lease-gates'
}
function Write-HealthTraceMessage([string]$Channel,[string]$Name,$Value){
 Assert-Trace ($Name -cin @('capture-go.json','capture-stopped.json','capture-failed.json')) 'health-trace-message-name'
 $temporary=Get-TracePath ($Channel+'\'+$Name+'.writing');$target=Get-TracePath ($Channel+'\'+$Name)
 Write-TraceJson $temporary $Value;[IO.File]::Move($temporary,$target)
}
function Read-HealthTraceJson([string]$Path){
 $clock=[Diagnostics.Stopwatch]::StartNew()
 while($true){
  try{return (Read-TraceJson $Path)}
  catch [IO.IOException]{
   $code=$_.Exception.HResult -band 0xffff
   if($code -ne 32 -and $code -ne 33){throw}
   Assert-Trace ($clock.ElapsedMilliseconds -lt 2000) 'health-trace-json-writer-not-closed'
  }
  [Threading.Thread]::Sleep(25)
 }
}
function Assert-HealthTraceReady($Ready,$Contract,[string]$ContractSha){
 Assert-Trace ($Ready.schema -ceq 'sfl-health-trace-collector-ready-v1' -and $Ready.scope -ceq $Contract.scope -and $Ready.run_id -ceq $Contract.run_id -and $Ready.contract_sha256 -ceq $ContractSha) 'health-trace-ready-binding'
 Assert-Trace ($Ready.worker.pid -is [int] -and $Ready.worker.pid -gt 0 -and $Ready.worker.created_filetime -is [long] -and $Ready.worker.created_filetime -gt 0) 'health-trace-worker-generation'
 Assert-Trace ($Ready.payload_reference_sha256 -cmatch '^[0-9a-f]{64}$' -and $Ready.configuration_reference_sha256 -cmatch '^[0-9a-f]{64}$') 'health-trace-ready-reference-pins'
 Assert-Trace ($Ready.release_gate -ceq 'HOLD' -and $Ready.promotion_allowed -is [bool] -and -not $Ready.promotion_allowed) 'health-trace-ready-gates'
 $names=@('native-initial.json','runtime-initial.json','control-initial.json','configuration-initial.json')
 Assert-Trace (@($Ready.initial_files.PSObject.Properties).Count -eq $names.Count) 'health-trace-initial-file-count'
 foreach($name in $names){Assert-Trace ($Ready.initial_files.$name.bytes -gt 0 -and $Ready.initial_files.$name.bytes -le 1MB -and $Ready.initial_files.$name.sha256 -cmatch '^[0-9a-f]{64}$') 'health-trace-initial-file-fact'}
}

$held=[Collections.Generic.List[IO.Stream]]::new();$guard=$null;$traceParent=$null;$collector=$null;$backend=$null
$directory=$null;$channel=$null;$leaseSha=$null;$windowSha=$null;$contract=$null
$record=[ordered]@{schema='sfl-health-trace-coordinator-v1';status='FAIL';scope='LOCAL_INSTALLED_HEALTH_TRACE_DIAGNOSTIC';errors=@();field_gate='NOT_EVALUATED';trace_quality='NOT_EVALUATED';release_gate='HOLD';promotion_allowed=$false}
try{
 $nativePs=[IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
 if(-not ([Environment]::Is64BitProcess -and $PSVersionTable.PSEdition -ceq 'Desktop' -and $PSVersionTable.PSVersion.Major -eq 5 -and $PSVersionTable.PSVersion.Minor -eq 1 -and [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName -ieq $nativePs)){throw 'native PS5.1 x64 required'}
 $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
 if(-not ([Security.Principal.WindowsPrincipal]::new($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'administrator PowerShell required'}
 $package=[IO.Path]::GetFullPath($PackageRoot).TrimEnd('\')
 $manifestStream=[IO.File]::Open(($package+'\manifest.json'),'Open','Read','Read');$held.Add($manifestStream)
 if($manifestStream.Length -gt 64KB){throw 'manifest budget'}
 $hash=[Security.Cryptography.SHA256]::Create();try{$digest=[BitConverter]::ToString($hash.ComputeHash($manifestStream)).Replace('-','').ToLowerInvariant()}finally{$hash.Dispose()}
 if($digest -cne $ExpectedManifestSha256){throw 'manifest pin'}
 $manifestStream.Position=0;$reader=[IO.StreamReader]::new($manifestStream,[Text.Encoding]::UTF8,$true,4096,$true)
 try{$manifest=$reader.ReadToEnd()|ConvertFrom-Json}finally{$reader.Dispose()}
 $required=@('invoke-field-run.template.ps1','invoke-trace-validation.ps1','SFLThreadScheduling.wprp','invoke-health-trace.ps1')
 if($manifest.schema -cne 'sfl-health-trace-package-v1' -or @($manifest.files.PSObject.Properties).Count -ne $required.Count){throw 'health trace manifest schema/members'}
 foreach($name in $required){
  $stream=[IO.File]::Open(($package+'\'+$name),'Open','Read','Read');$held.Add($stream)
  if($stream.Length -ne $manifest.files.$name.bytes -or $stream.Length -gt 1MB){throw 'package size'}
  $hash=[Security.Cryptography.SHA256]::Create();try{$digest=[BitConverter]::ToString($hash.ComputeHash($stream)).Replace('-','').ToLowerInvariant()}finally{$hash.Dispose()}
  if($digest -cne $manifest.files.$name.sha256){throw 'package pin'}
 }
 foreach($name in @('invoke-field-run.template.ps1','invoke-trace-validation.ps1')){
  $tokens=$null;$errors=$null;$ast=[Management.Automation.Language.Parser]::ParseFile(($package+'\'+$name),[ref]$tokens,[ref]$errors)
  if($errors.Count){throw 'package parse'}
  foreach($f in @($ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst]},$false))){. ([scriptblock]::Create($f.Extent.Text))}
 }
 [void](Get-TracePath $package);Initialize-TraceHandles;Initialize-RunNative
 Assert-Trace ($PSCommandPath -ieq $package+'\invoke-health-trace.ps1') 'health-trace-entry-path'
 Assert-Trace (-not [SflTraceParent]::CurrentInJob()) 'health-trace-controller-must-be-outside-other-job'
 $parent=Get-TracePath ([IO.Path]::Combine([Environment]::GetFolderPath('Desktop'),'SmartFactory'))
 if($Mode -ceq 'Run'){
  $requestPath=Get-TracePath $ContractPath;$channel=Get-TracePath ([IO.Path]::GetDirectoryName($requestPath))
  Assert-Trace ($channel.StartsWith($parent+'\',[StringComparison]::OrdinalIgnoreCase) -and [IO.Path]::GetFileName($requestPath) -ceq 'contract.json') 'health-trace-contract-path'
  $stream=[IO.File]::Open($requestPath,'Open','Read','Read');$held.Add($stream)
  Assert-Trace ($stream.Length -le 64KB -and (Get-TraceHash $stream) -ceq $ExpectedContractSha256) 'health-trace-contract-pin'
  $contract=Read-TraceJson $requestPath;Assert-HealthTraceContract $contract $channel $ExpectedManifestSha256
  $policy=Get-HealthTracePolicy $contract.scope;$record.scope=$contract.scope
  $stream=[IO.File]::Open(($channel+'\collector-ready.json'),'Open','Read','Read');$held.Add($stream)
  Assert-Trace ($stream.Length -le 64KB -and (Get-TraceHash $stream) -ceq $ExpectedReadySha256) 'health-trace-ready-pin'
  $ready=Read-TraceJson ($channel+'\collector-ready.json');Assert-HealthTraceReady $ready $contract $ExpectedContractSha256
  Assert-Trace (@([IO.Directory]::GetFiles($channel)).Count -eq 2 -and @([IO.Directory]::GetDirectories($channel)).Count -eq 0) 'health-trace-channel-already-used'
  $evidence=Get-TracePath $ready.evidence_directory
  Assert-Trace ($evidence.StartsWith($parent+'\',[StringComparison]::OrdinalIgnoreCase) -and [IO.Path]::GetFileName($evidence) -ceq 'evidence') 'health-trace-evidence-path'
  foreach($entry in $ready.initial_files.PSObject.Properties){
   $stream=[IO.File]::Open(($evidence+'\'+$entry.Name),'Open','Read','Read');$held.Add($stream)
   Assert-Trace ($stream.Length -eq $entry.Value.bytes -and (Get-TraceHash $stream) -ceq $entry.Value.sha256) 'health-trace-initial-file-pin'
  }
  $collector=[SflTraceParent]::new([uint32]$ready.worker.pid,[int64]$ready.worker.created_filetime)
  $backend=[SflTraceParent]::new([uint32]$contract.backend_pid,[int64]$contract.backend_created_filetime)
  Assert-Trace ($collector.Alive() -and $backend.Alive()) 'health-trace-participant-not-alive'
  $directory=Get-TracePath ($parent+'\T'+[Guid]::NewGuid().ToString('N').Substring(0,12))
  Assert-Trace (-not [IO.Directory]::Exists($directory) -and -not [IO.File]::Exists($directory)) 'health-trace-new-run'
  [void][IO.Directory]::CreateDirectory($directory,(New-RunAcl $identity.User.Value));Assert-RunAcl $directory $identity.User.Value
  foreach($key in @('APPDATA','LOCALAPPDATA','TEMP','TMP')){[void][IO.Directory]::CreateDirectory(($directory+'\'+$key))}
  $lease=[ordered]@{schema=$policy.lease_schema;scope=$contract.scope;run_id=$contract.run_id;instance='SFLTrace_'+[Guid]::NewGuid().ToString('N');run_path=$directory;parent_pid=$PID;parent_created_filetime=[Diagnostics.Process]::GetCurrentProcess().StartTime.ToUniversalTime().ToFileTimeUtc().ToString();guard_seconds=$policy.guard;capture_seconds=$policy.duration;stop_timeout_seconds=60;contract_sha256=$ExpectedContractSha256;package_sha256=$ExpectedManifestSha256;profile_sha256=$manifest.files.'SFLThreadScheduling.wprp'.sha256;release_gate='HOLD';promotion_allowed=$false}
  Assert-HealthTraceLease ([pscustomobject]$lease) $directory $ExpectedManifestSha256
  Write-TraceJson ($directory+'\lease.json') $lease
  $stream=[IO.File]::Open(($directory+'\lease.json'),'Open','Read','Read');$held.Add($stream);$leaseSha=Get-TraceHash $stream
  $record.run_path=$directory;$record.run_id=$contract.run_id;$record.contract_sha256=$ExpectedContractSha256;$record.collector_ready_sha256=$ExpectedReadySha256
  $arguments=@('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',($package+'\invoke-health-trace.ps1'),'-Mode','Guard','-PackageRoot',$package,'-ExpectedManifestSha256',$ExpectedManifestSha256,'-RunPath',$directory,'-ExpectedLeaseSha256',$leaseSha)
  $line=(@($arguments|ForEach-Object{[SflOwnedRun]::Quote($_)}) -join ' ')
  $guard=Start-TraceProcess $nativePs $line ($directory+'\guard.stdout.log') ($directory+'\guard.stderr.log')
  $guardIdentity=@{pid=$guard.Id;created_filetime=$guard.StartTime.ToUniversalTime().ToFileTimeUtc().ToString()};Write-TraceJson ($directory+'\guard-process.json') $guardIdentity
  $clock=[Diagnostics.Stopwatch]::StartNew()
  while(-not [IO.File]::Exists($directory+'\ready.json') -and -not $guard.HasExited -and $clock.Elapsed.TotalSeconds -lt 45){[Threading.Thread]::Sleep(25)}
  Assert-Trace ([IO.File]::Exists($directory+'\ready.json') -and -not $guard.HasExited -and $collector.Alive() -and $backend.Alive()) 'health-trace-start-not-ready'
  $traceReady=Read-HealthTraceJson ($directory+'\ready.json');Assert-Trace ($traceReady.lease_sha256 -ceq $leaseSha -and $traceReady.instance -ceq $lease.instance) 'health-trace-ready-lease'
  $common=@{scope=$contract.scope;run_id=$contract.run_id;contract_sha256=$ExpectedContractSha256;release_gate='HOLD';promotion_allowed=$false}
  $go=@{schema='sfl-health-trace-go-v1';collector_ready_sha256=$ExpectedReadySha256;worker=$ready.worker;trace_run_path=$directory;lease_sha256=$leaseSha;trace_ready_sha256=(Get-RunFact ($directory+'\ready.json')).sha256;instance=$lease.instance;guard=$guardIdentity}
  foreach($key in $common.Keys){$go[$key]=$common[$key]};Write-HealthTraceMessage $channel 'capture-go.json' $go
  $clock.Restart()
  while(-not [IO.File]::Exists($channel+'\capture-complete.json') -and -not [IO.File]::Exists($channel+'\capture-abort.json') -and $collector.Alive() -and $backend.Alive() -and -not $guard.HasExited -and $clock.Elapsed.TotalSeconds -lt ($policy.duration+9)){[Threading.Thread]::Sleep(25)}
  Assert-Trace ([IO.File]::Exists($channel+'\capture-complete.json') -and -not [IO.File]::Exists($channel+'\capture-abort.json') -and $collector.Alive() -and $backend.Alive() -and -not $guard.HasExited) 'health-trace-window-incomplete'
  $window=Read-TraceJson ($channel+'\capture-complete.json');$windowSha=(Get-RunFact ($channel+'\capture-complete.json')).sha256
  Assert-Trace ($window.schema -ceq 'sfl-health-trace-window-v1' -and $window.run_id -ceq $contract.run_id -and $window.contract_sha256 -ceq $ExpectedContractSha256 -and $window.collector_ready_sha256 -ceq $ExpectedReadySha256 -and $window.worker.pid -eq $ready.worker.pid -and $window.worker.created_filetime -eq $ready.worker.created_filetime) 'health-trace-window-binding'
  Assert-Trace ($window.release_gate -ceq 'HOLD' -and $window.promotion_allowed -is [bool] -and -not $window.promotion_allowed) 'health-trace-window-gates'
  $record.window_sha256=$windowSha
 }else{
  $directory=Get-TracePath $RunPath;Assert-RunAcl $directory $identity.User.Value
  $stream=[IO.File]::Open(($directory+'\lease.json'),'Open','Read','Read');$held.Add($stream)
  Assert-Trace ($stream.Length -le 64KB -and (Get-TraceHash $stream) -ceq $ExpectedLeaseSha256) 'health-trace-lease-pin'
  $lease=Read-TraceJson ($directory+'\lease.json');Assert-HealthTraceLease $lease $directory $ExpectedManifestSha256
  $stream=[IO.File]::Open(($directory+'\owner.lock'),'OpenOrCreate','ReadWrite','None');$held.Add($stream)
  if($Mode -ceq 'Guard'){
   Assert-Trace (-not [IO.File]::Exists($directory+'\start-intent.json')) 'health-trace-start-already-attempted'
   $traceParent=[SflTraceParent]::new([uint32]$lease.parent_pid,[int64]$lease.parent_created_filetime)
  }else{Assert-TraceRecovery (Read-TraceJson ($directory+'\start-intent.json')) $lease $ExpectedLeaseSha256 $ExpectedManifestSha256 {param($p,$c) [SflTraceParent]::GenerationAlive([uint32]$p,[int64]$c)}}
  $wpr=Get-TracePath ([IO.Path]::Combine([Environment]::SystemDirectory,'wpr.exe'))
  $stream=[IO.File]::Open($wpr,'Open','Read','Read');$held.Add($stream);$wprSha=Get-TraceHash $stream
  $prefix=if($Mode -ceq 'Recover'){'recovery-'+[Guid]::NewGuid().ToString('N').Substring(0,8)}else{'cmd'}
  $context=@{index=0}
  $command={param($Operation,$File)
   $argv=@(Get-TraceArguments $Operation $package $directory $lease.instance $File)
   $folder=$directory+'\'+$prefix+'-'+$context.index.ToString('00');$context.index++
   Invoke-TraceNative $wpr $argv $folder $directory $(if($Operation -ceq 'stop'){60}else{20})
  }
  $clock=[Diagnostics.Stopwatch]::StartNew();$traceName='trace.etl';$resultName='result.json'
  if($Mode -ceq 'Guard'){
   $record=Invoke-TraceLifecycle $lease $command {$traceParent.Alive()} {
    if(-not [IO.File]::Exists($directory+'\stop-request.json')){return $false}
    $request=Read-TraceJson ($directory+'\stop-request.json');Assert-Trace ($request.lease_sha256 -ceq $ExpectedLeaseSha256) 'health-trace-stop-binding';return $true
   } {Write-TraceJson ($directory+'\ready.json') @{instance=$lease.instance;lease_sha256=$ExpectedLeaseSha256}} {$clock.Elapsed.TotalSeconds} {Start-Sleep -Milliseconds 25} {
    Write-TraceJson ($directory+'\start-intent.json') @{schema='sfl-trace-start-intent-v1';instance=$lease.instance;lease_sha256=$ExpectedLeaseSha256;manifest_sha256=$ExpectedManifestSha256;observed_before_start='ABSENT';guard_pid=$PID;guard_created_filetime=[Diagnostics.Process]::GetCurrentProcess().StartTime.ToUniversalTime().ToFileTimeUtc().ToString()}
   }
  }else{
   $traceName=$prefix+'.etl';$resultName=$prefix+'.json';$record=Stop-TraceOwned $command $traceName
   $record.status=if($record.cleanup_confirmed){'OWNED_SESSION_CLEANUP_CONFIRMED'}else{'FAIL'}
   $record.instance=$lease.instance;$record.release_gate='HOLD';$record.promotion_allowed=$false
  }
  $record.lease_sha256=$ExpectedLeaseSha256;$record.wpr_sha256=$wprSha;$record.scope=$lease.scope;$record.run_id=$lease.run_id
  $record.field_gate='NOT_EVALUATED';$record.trace_quality='NOT_EVALUATED'
  if($record.trace_saved){$record.etl=Get-RunFact ($directory+'\'+$traceName);Assert-Trace ($record.etl.bytes -gt 0 -and $record.etl.bytes -le 256MB) 'health-trace-etl-budget'}
  Write-TraceJson ($directory+'\'+$resultName) $record
  Write-Host ('RESULT_PATH='+$directory+'\'+$resultName);Write-Host ('RESULT_SHA256='+(Get-RunFact ($directory+'\'+$resultName)).sha256)
 }
}catch{$record.errors+=$_.Exception.Message;$record.status='FAIL'}
finally{
 if($Mode -ceq 'Run' -and $guard){
  try{
   if(-not $guard.HasExited -and -not [IO.File]::Exists($directory+'\stop-request.json')){Write-TraceJson ($directory+'\stop-request.json') @{lease_sha256=$leaseSha}}
   Assert-Trace ($guard.WaitForExit(150000)) 'health-trace-guard-terminal-unconfirmed-do-not-rerun'
   $record.guard_exit=$guard.ExitCode;$record.guard_logs=Read-TraceProcessLogs $guard ($directory+'\guard.stdout.log') ($directory+'\guard.stderr.log')
   $trace=Read-TraceJson ($directory+'\result.json');$record.trace_result=Get-RunFact ($directory+'\result.json')
   Assert-Trace ($guard.ExitCode -eq 0 -and $trace.status -ceq 'CONTROL_FLOW_COMPLETE' -and $trace.lease_sha256 -ceq $leaseSha -and $trace.cleanup_confirmed -and $trace.trace_saved -and -not $trace.cancelled_without_trace -and $trace.errors.Count -eq 0) 'health-trace-guard-failed'
   $record.etl=Get-RunFact ($directory+'\trace.etl');Assert-Trace ($record.etl.bytes -eq $trace.etl.bytes -and $record.etl.sha256 -ceq $trace.etl.sha256) 'health-trace-etl-pin'
   if($record.errors.Count -eq 0 -and $windowSha -and $trace.reason -ceq 'controller-requested-stop'){
    $stopped=@{schema='sfl-health-trace-stopped-v1';window_sha256=$windowSha;guard_exit=$guard.ExitCode;trace_result=$record.trace_result;etl=$record.etl}
    foreach($key in $common.Keys){$stopped[$key]=$common[$key]};Write-HealthTraceMessage $channel 'capture-stopped.json' $stopped
    $record.status='CAPTURE_COMPLETE_REQUIRES_CORRELATION'
   }
  }catch{$record.errors+=$_.Exception.Message;$record.status='FAIL'}
 }
 if($Mode -ceq 'Run' -and $directory){
  try{Write-TraceJson ($directory+'\health-trace-summary.json') $record;Write-Host ('RESULT_PATH='+$directory+'\health-trace-summary.json');Write-Host ('RESULT_SHA256='+(Get-RunFact ($directory+'\health-trace-summary.json')).sha256)}catch{Write-Host ('RESULT_WRITE_FAILED='+$_.Exception.Message);$record.status='FAIL'}
 }
 if($Mode -ceq 'Run' -and $contract -and $channel -and $record.status -ceq 'FAIL'){
  try{Write-HealthTraceMessage $channel 'capture-failed.json' @{schema='sfl-health-trace-failed-v1';scope=$contract.scope;run_id=$contract.run_id;contract_sha256=$ExpectedContractSha256;status='FAIL';release_gate='HOLD';promotion_allowed=$false}}
  catch{Write-Host ('FAILURE_PUBLICATION_FAILED='+$_.Exception.Message)}
 }
 foreach($object in @($guard,$traceParent,$collector,$backend)){if($null -ne $object){$object.Dispose()}}
 foreach($stream in $held){$stream.Dispose()}
}
$record|ConvertTo-Json -Depth 14
if($record.status -cnotin @('CAPTURE_COMPLETE_REQUIRES_CORRELATION','CONTROL_FLOW_COMPLETE','OWNED_SESSION_CLEANUP_CONFIRMED')){exit 1};exit 0
