[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$PackageRoot,
 [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedManifestSha256,
 [Parameter(Mandatory=$true)][string]$RequestPath,
 [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedRequestSha256,
 [Parameter(Mandatory=$true)][ValidatePattern('^S-1-5-21-[0-9-]+$')][string]$OperatorSid
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'

# These bootstrap routines run before any package code has been authenticated.
function Assert-HealthEntry([bool]$Value,[string]$Reason){if(-not $Value){throw $Reason}}
function Get-HealthEntryPath([string]$Path){
 Assert-HealthEntry ($Path -cmatch '^[A-Za-z]:[\\/]' -and $Path -notmatch '[\x00-\x1f]') 'health-absolute-local-path'
 $full=[IO.Path]::GetFullPath($Path).TrimEnd('\')
 Assert-HealthEntry ($full.Length -gt 3 -and $full.Length -le 230 -and $full.Substring(2) -notmatch ':') 'health-path-budget-or-stream'
 $node=[IO.FileInfo]::new($full)
 while($null -ne $node){
  Assert-HealthEntry ([int]$node.Attributes -eq -1 -or ($node.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'health-reparse-path'
  if($node -is [IO.FileInfo]){$node=$node.Directory}else{$node=$node.Parent}
 }
 return $full
}
function Get-HealthEntryHash([IO.Stream]$Stream){
 $hash=[Security.Cryptography.SHA256]::Create()
 try{$Stream.Position=0;return [BitConverter]::ToString($hash.ComputeHash($Stream)).Replace('-','').ToLowerInvariant()}
 finally{$hash.Dispose()}
}
function Read-HealthEntryStream([IO.Stream]$Stream){
 $Stream.Position=0;$reader=[IO.StreamReader]::new($Stream,[Text.UTF8Encoding]::new($false,$true),$true,4096,$true)
 try{return ($reader.ReadToEnd()|ConvertFrom-Json)}finally{$reader.Dispose()}
}
function Copy-HealthEntryStream([IO.Stream]$Stream,[string]$Target){
 $Target=Get-HealthEntryPath $Target
 $writer=[IO.File]::Open($Target,'CreateNew','Write','None')
 try{$Stream.Position=0;$Stream.CopyTo($writer);$writer.Flush($true)}finally{$writer.Dispose()}
 $copy=[IO.File]::Open($Target,'Open','Read','Read')
 try{Assert-HealthEntry ($copy.Length -eq $Stream.Length -and (Get-HealthEntryHash $copy) -ceq (Get-HealthEntryHash $Stream)) 'health-archive-copy-pin'}finally{$copy.Dispose()}
}
function Get-HealthEntryFiles([string]$Root){
 $Root=Get-HealthEntryPath $Root;$files=[ordered]@{};$pending=[Collections.Generic.Queue[string]]::new();$pending.Enqueue($Root)
 $count=0;$total=[long]0
 while($pending.Count){
  foreach($path in [IO.Directory]::GetFileSystemEntries($pending.Dequeue())){
   $count++;Assert-HealthEntry ($count -le 10000) 'health-tree-count-budget';$path=Get-HealthEntryPath $path
   if([IO.Directory]::Exists($path)){$pending.Enqueue($path);continue}
   $name=$path.Substring($Root.Length+1).Replace('\','/')
   Assert-HealthEntry (-not $files.Contains($name)) 'health-tree-case-collision'
   $stream=[IO.File]::Open($path,'Open','Read','Read')
   try{
    $total+=$stream.Length;Assert-HealthEntry ($stream.Length -le 512MB -and $total -le 1GB) 'health-tree-byte-budget'
    $files[$name]=@{bytes=$stream.Length;sha256=Get-HealthEntryHash $stream}
   }finally{$stream.Dispose()}
  }
 }
 return $files
}
function Assert-HealthEntryPackage($Document){
 $required=@('health_diagnostic_runner.exe','invoke-health-diagnostic.ps1','candidate-payload.json','helper-source.zip','helper-build.json',
  'trace/manifest.json','trace/invoke-field-run.template.ps1','trace/invoke-trace-validation.ps1','trace/invoke-health-trace.ps1','trace/SFLThreadScheduling.wprp')
 Assert-HealthEntry ($Document.schema -ceq 'sfl-health-diagnostic-package-v1' -and $Document.signature_policy -ceq 'UNSIGNED_INTERNAL' -and
  $Document.candidate_commit -ceq 'acaf77d95101a050f4d3ecd76125d3502036f5a7') 'health-package-identity'
 Assert-HealthEntry (@($Document.files.PSObject.Properties).Count -eq $required.Count) 'health-package-members'
 foreach($name in $required){
  Assert-HealthEntry ($null -ne $Document.files.PSObject.Properties[$name]) 'health-package-missing-member'
  $fact=$Document.files.$name
  Assert-HealthEntry ($fact.bytes -is [int] -and $fact.bytes -gt 0 -and $fact.bytes -le 128MB -and $fact.sha256 -cmatch '^[0-9a-f]{64}$') 'health-package-fact'
 }
 Assert-HealthEntry ($Document.files.'candidate-payload.json'.sha256 -ceq '658b096408ddb82022c53f9802c1300e6da7ca7cfbd077a60db4efc07935fe69') 'health-package-payload-pin'
 Assert-HealthEntry ($Document.release_gate -ceq 'HOLD' -and $Document.promotion_allowed -is [bool] -and -not $Document.promotion_allowed) 'health-package-gates'
}
function Get-HealthEntryBudget($Request){
 Assert-HealthEntry ($Request.duration_seconds -is [int]) 'health-request-duration-type'
 if($Request.schema -ceq 'sfl-health-diagnostic-request-v1'){
  Assert-HealthEntry ($Request.duration_seconds -eq 6) 'health-request-identity-budget'
  return @{seconds=600;scope='SIX_SECOND_CAPTURE_NOT_FIELD_PERFORMANCE'}
 }
 Assert-HealthEntry ($Request.schema -ceq 'sfl-health-outlier-request-v1' -and $Request.duration_seconds -eq 900) 'health-request-identity-budget'
 return @{seconds=1500;scope='OUTLIER_CAPTURE_NOT_FIELD_PERFORMANCE'}
}
function Invoke-HealthEntryChild([string]$Executable,[string[]]$Arguments,[string]$Directory,[scriptblock]$OnTick,[ValidateRange(1,1500)][int]$TimeoutSeconds=600){
 # The callback starts the coordinator from this outside-job administrator.
 # Neither the application nor that coordinator joins the collection job.
 Initialize-RunNative
 $environment=[Collections.Generic.SortedDictionary[string,string]]::new([StringComparer]::OrdinalIgnoreCase)
 $environment['SYSTEMROOT']=[Environment]::GetFolderPath('Windows');$environment['WINDIR']=$environment['SYSTEMROOT']
 $environment['SYSTEMDRIVE']=[IO.Path]::GetPathRoot($environment['SYSTEMROOT']).TrimEnd('\')
 $environment['PATH']=[Environment]::SystemDirectory+';'+$environment['SYSTEMROOT']
 foreach($key in @('APPDATA','LOCALAPPDATA','TEMP','TMP')){
  $path=Get-HealthEntryPath ($Directory+'\'+$key)
  Assert-HealthEntry (-not [IO.Directory]::Exists($path) -and -not [IO.File]::Exists($path)) 'health-new-environment-directory'
  [void][IO.Directory]::CreateDirectory($path);$environment[$key]=$path
 }
 $block=(($environment.GetEnumerator()|ForEach-Object{$_.Key+'='+$_.Value+[char]0}) -join '')+[char]0
 $child=$null;$clock=[Diagnostics.Stopwatch]::StartNew()
 $record=[ordered]@{status='FAIL';created_suspended=$false;job_assigned_before_resume=$false;termination_requested=$false;errors=@()}
 try{
  $child=[SflOwnedRun]::new($Executable,$Arguments,$block,$Directory,($Directory+'\stdout.log'),($Directory+'\stderr.log'))
  $record.pid=$child.Pid;$record.created_suspended=$true;$record.job_assigned_before_resume=$true
  while(-not $child.Wait(50)){
   Assert-HealthEntry ($clock.Elapsed.TotalSeconds -lt $TimeoutSeconds) 'health-outer-deadline'
   foreach($name in @('stdout.log','stderr.log')){Assert-HealthEntry (([IO.FileInfo]::new($Directory+'\'+$name)).Length -le 16MB) 'health-child-log-budget'}
   & $OnTick $child
  }
  $record.actual_exit_code=$child.ExitCode();$record.job_at_root_exit=$child.Accounting()
  # Job accounting may lag the root's terminal signal. Preserve both observations;
  # bounded natural drainage never turns a live descendant into a passing result.
  $drain=[Diagnostics.Stopwatch]::StartNew()
  while($child.Accounting()[1] -ne 0 -and $drain.Elapsed.TotalSeconds -lt 2 -and $clock.Elapsed.TotalSeconds -lt $TimeoutSeconds){[Threading.Thread]::Sleep(25)}
  $record.natural_drain_ms=$drain.ElapsedMilliseconds;$record.job_before_cleanup=$child.Accounting()
  Assert-HealthEntry ($clock.Elapsed.TotalSeconds -lt $TimeoutSeconds) 'health-outer-deadline'
  Assert-HealthEntry ($record.job_before_cleanup[1] -eq 0) 'health-owned-descendants-remain'
  if($record.actual_exit_code -eq 0){$record.status='PASS'}
 }catch{$record.errors+=$_.Exception.Message}
 finally{
  if($child){
   try{$record.job_observation_before_cleanup=$child.ObserveJob()}catch{$record.job_observation_error=$_.Exception.Message}
   try{
    if($child.Accounting()[1] -ne 0){$record.termination_requested=$true;$record.status='FAIL';$child.Terminate()}
    $drain=[Diagnostics.Stopwatch]::StartNew()
    while($child.Accounting()[1] -ne 0 -and $drain.Elapsed.TotalSeconds -lt 10){[Threading.Thread]::Sleep(25)}
    $record.job_after_cleanup=$child.Accounting();$record.actual_exit_code=$child.ExitCode()
    Assert-HealthEntry ($record.job_after_cleanup[1] -eq 0) 'health-owned-job-still-active'
   }catch{$record.errors+=$_.Exception.Message;$record.status='FAIL'}finally{$child.Dispose()}
  }
  if($record.errors.Count -gt 0 -or $record.termination_requested){$record.status='FAIL'}
  $record.elapsed_seconds=$clock.Elapsed.TotalSeconds
 }
 return $record
}

$held=[Collections.Generic.List[IO.Stream]]::new();$sources=@{};$resultRoot=$null
$coordinator=@{process=$null;terminal=$false;logs=$null}
$record=[ordered]@{schema='sfl-health-diagnostic-launch-v1';status='FAIL';errors=@();request_sha256=$ExpectedRequestSha256;
 package_manifest_sha256=$ExpectedManifestSha256;signature_policy='UNSIGNED_INTERNAL';scope='SIX_SECOND_CAPTURE_NOT_FIELD_PERFORMANCE';
 field_gate='NOT_EVALUATED';trace_quality='NOT_EVALUATED';release_gate='HOLD';promotion_allowed=$false;
 installation_performed=$false;application_shutdown_performed=$false}
$entryState=@{record=$record}
try{
 $native=[IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
 Assert-HealthEntry ([Environment]::Is64BitProcess -and $PSVersionTable.PSEdition -ceq 'Desktop' -and $PSVersionTable.PSVersion.Major -eq 5 -and $PSVersionTable.PSVersion.Minor -eq 1 -and [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName -ieq $native) 'native-powershell-5.1-x64-required'
 $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
 Assert-HealthEntry (([Security.Principal.WindowsPrincipal]::new($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) 'administrator-required'
 $root=Get-HealthEntryPath $PackageRoot
 $manifest=[IO.File]::Open((Get-HealthEntryPath ($root+'\manifest.json')),'Open','Read','Read');$held.Add($manifest)
 Assert-HealthEntry ($manifest.Length -le 64KB -and (Get-HealthEntryHash $manifest) -ceq $ExpectedManifestSha256) 'health-package-manifest-pin'
 $document=Read-HealthEntryStream $manifest;Assert-HealthEntryPackage $document
 foreach($item in $document.files.PSObject.Properties){
  $stream=[IO.File]::Open((Get-HealthEntryPath ($root+'\'+$item.Name)),'Open','Read','Read');$held.Add($stream);$sources[$item.Name]=$stream
  Assert-HealthEntry ($stream.Length -eq $item.Value.bytes -and (Get-HealthEntryHash $stream) -ceq $item.Value.sha256) 'health-package-file-pin'
 }
 $tree=Get-HealthEntryFiles $root
 Assert-HealthEntry ($tree.Count -eq $sources.Count+1 -and $tree.Contains('manifest.json')) 'health-package-extra-file'
 foreach($name in $tree.Keys){Assert-HealthEntry ($name -ceq 'manifest.json' -or $sources.ContainsKey($name)) 'health-package-extra-file'}
 Assert-HealthEntry ($PSCommandPath -ieq $root+'\invoke-health-diagnostic.ps1') 'health-entry-path'
 foreach($name in @('trace/invoke-field-run.template.ps1','trace/invoke-trace-validation.ps1','trace/invoke-health-trace.ps1')){
  $tokens=$null;$errors=$null;$ast=[Management.Automation.Language.Parser]::ParseFile(($root+'\'+$name),[ref]$tokens,[ref]$errors)
  Assert-HealthEntry ($errors.Count -eq 0) 'health-helper-parse'
  foreach($function in @($ast.FindAll({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst]},$false))){. ([scriptblock]::Create($function.Extent.Text))}
 }
 Initialize-RunNative;Initialize-TraceHandles
 Assert-HealthEntry (-not [SflTraceParent]::CurrentInJob()) 'health-launcher-must-be-outside-other-job'
 $parent=Get-HealthEntryPath ([IO.Path]::Combine([Environment]::GetFolderPath('Desktop'),'SmartFactory'))
 Assert-HealthEntry ([IO.Directory]::Exists($parent) -and $root -ine $parent) 'health-desktop-parent-required'
 $request=[IO.File]::Open((Get-HealthEntryPath $RequestPath),'Open','Read','Read');$held.Add($request)
 Assert-HealthEntry ($request.Length -gt 0 -and $request.Length -le 64KB -and (Get-HealthEntryHash $request) -ceq $ExpectedRequestSha256) 'health-request-pin'
 $requestValue=Read-HealthEntryStream $request
 Assert-HealthEntry ($requestValue.candidate_commit -ceq $document.candidate_commit -and $requestValue.signature_policy -ceq 'UNSIGNED_INTERNAL') 'health-request-identity-budget'
 $budget=Get-HealthEntryBudget $requestValue;$record.scope=$budget.scope
 $configuration=[IO.File]::Open((Get-HealthEntryPath $requestValue.spec.configuration_reference),'Open','Read','Read');$held.Add($configuration)
 Assert-HealthEntry ($configuration.Length -gt 0 -and $configuration.Length -le 1MB -and (Get-HealthEntryHash $configuration) -ceq $requestValue.spec.configuration_reference_sha256) 'health-configuration-reference-pin'
 $payload=[IO.File]::Open((Get-HealthEntryPath $requestValue.spec.reference),'Open','Read','Read');$held.Add($payload)
 Assert-HealthEntry ($payload.Length -eq $document.files.'candidate-payload.json'.bytes -and (Get-HealthEntryHash $payload) -ceq $document.files.'candidate-payload.json'.sha256 -and $requestValue.spec.reference_sha256 -ceq $document.files.'candidate-payload.json'.sha256) 'health-request-payload-pin'
 $resultRoot=Get-HealthEntryPath ($parent+'\H'+[Guid]::NewGuid().ToString('N').Substring(0,12))
 Assert-HealthEntry (-not [IO.Directory]::Exists($resultRoot) -and -not [IO.File]::Exists($resultRoot)) 'health-new-result-root'
 [void][IO.Directory]::CreateDirectory($resultRoot,(New-RunAcl $OperatorSid));Assert-RunAcl $resultRoot $OperatorSid
 $archive=$resultRoot+'\inputs';[void][IO.Directory]::CreateDirectory($archive);[void][IO.Directory]::CreateDirectory($archive+'\trace')
 foreach($name in $sources.Keys){Copy-HealthEntryStream $sources[$name] ($archive+'\'+$name)}
 Copy-HealthEntryStream $manifest ($archive+'\manifest.json')
 Copy-HealthEntryStream $request ($archive+'\request.json');Copy-HealthEntryStream $configuration ($archive+'\configuration.json')
 $record.input_archive=Get-HealthEntryFiles $archive
 Write-RunJson ($resultRoot+'\input-archive.json') @{files=$record.input_archive;source_package=$root;source_request=$RequestPath;source_configuration=$requestValue.spec.configuration_reference;release_gate='HOLD';promotion_allowed=$false}
 $traceSha=$document.files.'trace/manifest.json'.sha256;$channel=$resultRoot+'\session\trace-channel'
 $tick={param($owned)
  if($coordinator.process -or -not [IO.File]::Exists($channel+'\collector-ready.json')){return}
  $ready=Read-HealthTraceJson ($channel+'\collector-ready.json')
  $observation=$owned.ObserveJob();$member=@($observation.members|Where-Object{$_.pid -eq $ready.worker.pid -and $_.owned -eq $true -and $_.signaled -eq $false -and $_.created_filetime -eq $ready.worker.created_filetime})
  Assert-HealthEntry ($member.Count -eq 1) 'health-ready-worker-not-owned'
  $contractSha=(Get-RunFact ($channel+'\contract.json')).sha256;$readySha=(Get-RunFact ($channel+'\collector-ready.json')).sha256
  $arguments=@('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',($archive+'\trace\invoke-health-trace.ps1'),'-PackageRoot',($archive+'\trace'),'-ExpectedManifestSha256',$traceSha,'-ContractPath',($channel+'\contract.json'),'-ExpectedContractSha256',$contractSha,'-ExpectedReadySha256',$readySha)
  $coordinator.process=Start-TraceProcess $native (@($arguments|ForEach-Object{[SflOwnedRun]::Quote($_)}) -join ' ') ($resultRoot+'\coordinator.stdout.log') ($resultRoot+'\coordinator.stderr.log')
  $entryState.record.coordinator_start=@{pid=$coordinator.process.Id;created_filetime=$coordinator.process.StartTime.ToUniversalTime().ToFileTimeUtc().ToString();contract_sha256=$contractSha;ready_sha256=$readySha;owned_worker=$member[0]}
  Write-RunJson ($resultRoot+'\coordinator-start.json') $entryState.record.coordinator_start
 }
 $record.child=Invoke-HealthEntryChild ($archive+'\health_diagnostic_runner.exe') @('--output-root',$resultRoot,'--request-sha256',$ExpectedRequestSha256,'--trace-package-sha256',$traceSha) $resultRoot $tick $budget.seconds
 Write-RunJson ($resultRoot+'\native-child.json') $record.child
}catch{$record.errors+=$_.Exception.Message}
finally{
 if($coordinator.process){
  try{
   Assert-HealthEntry ($coordinator.process.WaitForExit(210000)) 'health-coordinator-terminal-unconfirmed-do-not-rerun'
   $coordinator.logs=Read-TraceProcessLogs $coordinator.process ($resultRoot+'\coordinator.stdout.log') ($resultRoot+'\coordinator.stderr.log')
   $coordinator.terminal=$true;$record.coordinator_exit=$coordinator.process.ExitCode;$record.coordinator_logs=$coordinator.logs
  }catch{$record.errors+=$_.Exception.Message}
 }
 try{
  if($resultRoot){
   Assert-RunAcl $resultRoot $OperatorSid
   if($coordinator.terminal){
    $matches=@([regex]::Matches($coordinator.logs.stdout,'(?m)^RESULT_PATH=(.+\\health-trace-summary\.json)\r?$'))
    Assert-HealthEntry ($matches.Count -eq 1) 'health-coordinator-summary-path'
    $summaryPath=Get-HealthEntryPath $matches[0].Groups[1].Value.TrimEnd([char]13)
    $traceRoot=[IO.Path]::GetDirectoryName($summaryPath)
    Assert-HealthEntry ([IO.Path]::GetDirectoryName($traceRoot) -ieq $parent -and [IO.Path]::GetFileName($traceRoot) -cmatch '^T[0-9a-f]{12}$') 'health-trace-copy-boundary'
    $summary=Read-TraceJson $summaryPath
    Assert-HealthEntry ($summary.run_path -ieq $traceRoot -and $summary.contract_sha256 -ceq $record.coordinator_start.contract_sha256 -and $summary.collector_ready_sha256 -ceq $record.coordinator_start.ready_sha256) 'health-trace-summary-binding'
    Assert-HealthEntry ($null -ne $summary.PSObject.Properties['guard_exit'] -and $summary.guard_logs.writers_closed -eq $true) 'health-trace-guard-writer-unconfirmed'
    $record.trace_original_path=$traceRoot
    $traceFiles=Get-HealthEntryFiles $traceRoot;$destination=$resultRoot+'\trace';[void][IO.Directory]::CreateDirectory($destination)
    foreach($name in $traceFiles.Keys){
     $target=Get-HealthEntryPath ($destination+'\'+$name);[void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target))
     $stream=[IO.File]::Open((Get-HealthEntryPath ($traceRoot+'\'+$name)),'Open','Read','Read')
     try{Assert-HealthEntry ($stream.Length -eq $traceFiles[$name].bytes -and (Get-HealthEntryHash $stream) -ceq $traceFiles[$name].sha256) 'health-trace-copy-source-pin';Copy-HealthEntryStream $stream $target}finally{$stream.Dispose()}
    }
    $record.trace_archive=$traceFiles
   }
   Assert-HealthEntry ($record.Contains('child')) 'health-child-not-started'
   Assert-HealthEntry (-not $coordinator.process -or $coordinator.terminal) 'health-output-still-has-writer'
   $session=$resultRoot+'\session'
   if([IO.File]::Exists($session+'\result.json')){
    Write-RunJson ($session+'\manifest.json') @{schema='sfl-field-run-files-v1';files=(Get-HealthEntryFiles $session);release_gate='HOLD';promotion_allowed=$false}
    $record.output_verification=Test-RunOutput $resultRoot $ExpectedRequestSha256 ($record.child.status -ceq 'PASS')
   }
   Assert-HealthEntry ($record.child.status -ceq 'PASS' -and $coordinator.terminal -and $record.Contains('output_verification')) 'health-capture-not-complete'
   Assert-HealthEntry ($record.coordinator_exit -eq 0 -and $summary.status -ceq 'CAPTURE_COMPLETE_REQUIRES_CORRELATION') 'health-coordinator-failed'
   foreach($item in $document.files.PSObject.Properties){Assert-HealthEntry ($sources[$item.Name].Length -eq $item.Value.bytes -and (Get-HealthEntryHash $sources[$item.Name]) -ceq $item.Value.sha256) 'health-package-closeout'}
   Assert-HealthEntry ((Get-HealthEntryHash $manifest) -ceq $ExpectedManifestSha256 -and (Get-HealthEntryHash $request) -ceq $ExpectedRequestSha256 -and (Get-HealthEntryHash $configuration) -ceq $requestValue.spec.configuration_reference_sha256) 'health-input-closeout'
   $archivedNow=Get-HealthEntryFiles $archive
   Assert-HealthEntry ($archivedNow.Count -eq $record.input_archive.Count) 'health-archive-closeout-count'
   foreach($name in $archivedNow.Keys){Assert-HealthEntry ($record.input_archive.Contains($name) -and $archivedNow[$name].bytes -eq $record.input_archive[$name].bytes -and $archivedNow[$name].sha256 -ceq $record.input_archive[$name].sha256) 'health-archive-closeout-pin'}
   if($record.errors.Count -eq 0){$record.status='CAPTURE_COMPLETE_REQUIRES_CORRELATION'}
  }
 }catch{$record.errors+=$_.Exception.Message;$record.status='FAIL'}
 if($resultRoot){
  try{
   # A missing terminal signal must never be presented as a sealed result tree.
   if(($coordinator.process -and -not $coordinator.terminal) -or ($record.Contains('child') -and
     (-not $record.child.Contains('job_after_cleanup') -or $record.child.job_after_cleanup[1] -ne 0))){$record.files_status='NOT_SEALED_WRITER_UNCONFIRMED'}
   else{$record.files=Get-HealthEntryFiles $resultRoot;$record.files_status='CLOSED_FILES_HASHED'}
   Write-RunJson ($resultRoot+'\launcher.json') $record
   Write-Host ('RESULT_PATH='+$resultRoot);Write-Host ('LAUNCHER_SHA256='+(Get-RunFact ($resultRoot+'\launcher.json')).sha256)
  }catch{Write-Host ('RESULT_WRITE_FAILED='+$_.Exception.Message);$record.status='FAIL'}
 }
 if($coordinator.process){$coordinator.process.Dispose()}
 foreach($stream in $held){$stream.Dispose()}
}
$record|ConvertTo-Json -Depth 30
if($record.status -cne 'CAPTURE_COMPLETE_REQUIRES_CORRELATION'){exit 1};exit 0
