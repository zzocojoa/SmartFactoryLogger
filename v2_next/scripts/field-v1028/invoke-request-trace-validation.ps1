[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$PackageRoot,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedManifestSha256,
    [Parameter(Mandatory=$true)][string]$JoinRequestPath,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedJoinRequestSha256
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'

function Assert-RequestTraceInput($Request,$Armed,[string]$Fixture,[string]$ArmedSha){
    Assert-Trace ($Request.schema -ceq 'sfl-request-trace-request-v1' -and $Armed.schema -ceq 'sfl-request-trace-armed-v1') 'request-trace-schema'
    Assert-Trace ($Request.run_id -cmatch '^[0-9a-f]{32}$' -and $Request.run_id -ceq $Armed.run_id) 'request-trace-run-id'
    Assert-Trace ($Request.fixture_directory -ieq $Fixture -and $Armed.output_directory -ieq $Fixture -and [IO.Path]::GetFileName($Fixture) -ceq 'fixture') 'request-trace-fixture-path'
    Assert-Trace ($Request.armed_sha256 -ceq $ArmedSha -and $Request.armed_sha256 -cmatch '^[0-9a-f]{64}$') 'request-trace-armed-pin'
    Assert-Trace ($Request.fixture_pid -is [int] -and $Request.fixture_pid -gt 0 -and $Request.fixture_pid -eq $Armed.identity.pid) 'request-trace-fixture-pid'
    Assert-Trace ($Request.fixture_created_filetime -cmatch '^[0-9]{17,20}$' -and $Request.fixture_created_filetime -ceq $Armed.identity.process_created_filetime.ToString()) 'request-trace-fixture-generation'
    Assert-Trace ($Armed.elevated -is [bool] -and -not $Armed.elevated -and $Armed.wait_seconds -eq 600) 'request-trace-fixture-scope'
    Assert-Trace ($Request.release_gate -ceq 'HOLD' -and $Armed.release_gate -ceq 'HOLD' -and $Request.promotion_allowed -is [bool] -and -not $Request.promotion_allowed -and $Armed.promotion_allowed -is [bool] -and -not $Armed.promotion_allowed) 'request-trace-gates'
    $names=@('field_trace_request_fixture.py','field_http_sampling.py','field_native_timing.py')
    Assert-Trace (@($Request.fixture_sources.PSObject.Properties).Count -eq 3 -and @($Armed.source_files.PSObject.Properties).Count -eq 3) 'request-trace-source-count'
    foreach($name in $names){Assert-Trace ($Request.fixture_sources.$name -cmatch '^[0-9a-f]{64}$' -and $Request.fixture_sources.$name -ceq $Armed.source_files.$name) 'request-trace-source-pin'}
    $armedAt=[DateTimeOffset]::Parse($Armed.armed_at_utc,[Globalization.CultureInfo]::InvariantCulture)
    $expires=[DateTimeOffset]::Parse($Request.expires_utc,[Globalization.CultureInfo]::InvariantCulture)
    $now=[DateTimeOffset]::UtcNow
    Assert-Trace ($armedAt -le $now -and $expires -gt $now -and $expires -le $armedAt.AddSeconds(600)) 'request-trace-arming-expired'
}
function Read-RequestTraceClosedJson([string]$Path){
    $clock=[Diagnostics.Stopwatch]::StartNew()
    while($true){
        try{return (Read-TraceJson $Path)}
        catch [IO.IOException]{
            $code=$_.Exception.HResult -band 0xffff
            if($code -ne 32 -and $code -ne 33){throw}
            Assert-Trace ($clock.ElapsedMilliseconds -lt 2000) 'request-trace-json-writer-not-closed'
        }
        [Threading.Thread]::Sleep(25)
    }
}
function Write-RequestTraceBinding([string]$Fixture,$Value){
    $temporary=Get-TracePath ($Fixture+'\trace-binding.json.writing')
    $target=Get-TracePath ($Fixture+'\trace-binding.json')
    Write-TraceJson $temporary $Value
    [IO.File]::Move($temporary,$target)
}
function Assert-RequestTraceCompletion($Complete,$Request,[string]$Fixture){
    Assert-Trace ($Complete.schema -ceq 'sfl-request-trace-fixture-complete-v1' -and $Complete.run_id -ceq $Request.run_id -and $Complete.status -ceq 'WORKLOAD_COMPLETE_REQUIRES_TRACE_CORRELATION') 'request-trace-fixture-result'
    Assert-Trace ($Complete.identity.pid -eq $Request.fixture_pid -and $Complete.identity.process_created_filetime.ToString() -ceq $Request.fixture_created_filetime) 'request-trace-completion-generation'
    Assert-Trace ($Complete.release_gate -ceq 'HOLD' -and $Complete.promotion_allowed -is [bool] -and -not $Complete.promotion_allowed) 'request-trace-completion-gates'
    $actual=Get-RunFact ($Fixture+'\workload.json')
    Assert-Trace ($actual.bytes -gt 0 -and $actual.bytes -le 1MB -and $actual.bytes -eq $Complete.workload.bytes -and $actual.sha256 -ceq $Complete.workload.sha256) 'request-trace-workload-pin'
    return $actual
}

$held=[Collections.Generic.List[IO.Stream]]::new();$fixtureParent=$null;$guard=$null;$directory=$null;$leaseSha=$null
$record=[ordered]@{schema='sfl-request-trace-validation-v1';status='FAIL';scope='LOCAL_REQUEST_TRACE_CORRELATION_PREPARATION';errors=@();trace_quality='NOT_EVALUATED';field_gate='NOT_EVALUATED';release_gate='HOLD';promotion_allowed=$false}
try{
    $nativePs=[IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
    if(-not ([Environment]::Is64BitProcess -and $PSVersionTable.PSEdition -ceq 'Desktop' -and $PSVersionTable.PSVersion.Major -eq 5 -and $PSVersionTable.PSVersion.Minor -eq 1 -and [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName -ieq $nativePs)){throw 'native PS5.1 x64 required'}
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
    if(-not ([Security.Principal.WindowsPrincipal]::new($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'administrator PowerShell required'}
    $package=[IO.Path]::GetFullPath($PackageRoot).TrimEnd('\')
    $manifestStream=[IO.File]::Open(($package+'\manifest.json'),'Open','Read','Read');$held.Add($manifestStream)
    if($manifestStream.Length -gt 64KB){throw 'manifest budget'}
    $sha=[Security.Cryptography.SHA256]::Create()
    try{$digest=[BitConverter]::ToString($sha.ComputeHash($manifestStream)).Replace('-','').ToLowerInvariant()}finally{$sha.Dispose()}
    if($digest -cne $ExpectedManifestSha256){throw 'manifest pin'}
    $manifestStream.Position=0;$reader=[IO.StreamReader]::new($manifestStream,[Text.UTF8Encoding]::new($false,$true),$true,4096,$true)
    try{$manifest=$reader.ReadToEnd()|ConvertFrom-Json}finally{$reader.Dispose()}
    $required=@('invoke-trace-validation.ps1','invoke-field-run.template.ps1','SFLThreadScheduling.wprp')
    if($manifest.schema -cne 'sfl-trace-validation-package-v1' -or @($manifest.files.PSObject.Properties).Count -ne 3){throw 'manifest schema/members'}
    foreach($name in $required){
        $stream=[IO.File]::Open(($package+'\'+$name),'Open','Read','Read');$held.Add($stream)
        if($stream.Length -gt 1MB -or $stream.Length -ne $manifest.files.$name.bytes){throw 'package size'}
        $sha=[Security.Cryptography.SHA256]::Create()
        try{$digest=[BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-','').ToLowerInvariant()}finally{$sha.Dispose()}
        if($digest -cne $manifest.files.$name.sha256){throw 'package pin'}
    }
    foreach($name in @('invoke-field-run.template.ps1','invoke-trace-validation.ps1')){
        $tokens=$null;$parseErrors=$null
        $ast=[Management.Automation.Language.Parser]::ParseFile(($package+'\'+$name),[ref]$tokens,[ref]$parseErrors)
        if($parseErrors.Count){throw 'package parse'}
        foreach($f in @($ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst]},$false))){. ([scriptblock]::Create($f.Extent.Text))}
    }
    [void](Get-TracePath $package);Initialize-TraceHandles;Initialize-RunNative
    Assert-Trace (-not [SflTraceParent]::CurrentInJob()) 'request-trace-controller-must-be-outside-other-job'
    $parent=Get-TracePath ([IO.Path]::Combine([Environment]::GetFolderPath('Desktop'),'SmartFactory'))
    $requestPath=Get-TracePath $JoinRequestPath
    $fixture=Get-TracePath ([IO.Path]::GetDirectoryName($requestPath))
    Assert-Trace ($fixture.StartsWith($parent+'\',[StringComparison]::OrdinalIgnoreCase)) 'request-trace-desktop-boundary'
    $requestStream=[IO.File]::Open($requestPath,'Open','Read','Read');$held.Add($requestStream)
    Assert-Trace ($requestStream.Length -le 64KB -and (Get-TraceHash $requestStream) -ceq $ExpectedJoinRequestSha256) 'request-trace-request-pin'
    $request=Read-TraceJson $requestPath
    $armedPath=$fixture+'\armed.json';$armedStream=[IO.File]::Open($armedPath,'Open','Read','Read');$held.Add($armedStream)
    $armed=Read-TraceJson $armedPath
    Assert-RequestTraceInput $request $armed $fixture (Get-TraceHash $armedStream)
    foreach($name in @('trace-binding.json','trace-binding.json.writing','complete.json','failure.json','workload.json')){
        Assert-Trace (-not [IO.File]::Exists($fixture+'\'+$name)) 'request-trace-already-used-or-terminal'
    }
    $fixtureParent=[SflTraceParent]::new([uint32]$request.fixture_pid,[int64]$request.fixture_created_filetime)
    Assert-Trace ($fixtureParent.Alive()) 'request-trace-fixture-not-alive'
    $directory=Get-TracePath ($parent+'\T'+[Guid]::NewGuid().ToString('N').Substring(0,12))
    Assert-Trace (-not [IO.Directory]::Exists($directory) -and -not [IO.File]::Exists($directory)) 'request-trace-new-run'
    [void][IO.Directory]::CreateDirectory($directory,(New-RunAcl $identity.User.Value));Assert-RunAcl $directory $identity.User.Value
    foreach($name in @('APPDATA','LOCALAPPDATA','TEMP','TMP')){[void][IO.Directory]::CreateDirectory(($directory+'\'+$name))}
    $lease=[ordered]@{schema='sfl-local-trace-lease-v1';scope='LOCAL_CONTROLLER_VALIDATION_ONLY';instance='SFLTrace_'+[Guid]::NewGuid().ToString('N');run_path=$directory;parent_pid=$PID;parent_created_filetime=([Diagnostics.Process]::GetCurrentProcess().StartTime.ToUniversalTime().ToFileTimeUtc()).ToString();guard_seconds=8;stop_timeout_seconds=60;profile_sha256=$manifest.files.'SFLThreadScheduling.wprp'.sha256;release_gate='HOLD';promotion_allowed=$false}
    Assert-TraceLease ([pscustomobject]$lease) $directory;Write-TraceJson ($directory+'\lease.json') $lease
    $leaseStream=[IO.File]::Open(($directory+'\lease.json'),'Open','Read','Read');$held.Add($leaseStream);$leaseSha=Get-TraceHash $leaseStream
    $record.run_path=$directory;$record.run_id=$request.run_id;$record.request_sha256=$ExpectedJoinRequestSha256;$record.fixture_pid=$request.fixture_pid;$record.lease_sha256=$leaseSha
    $arguments=@('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',($package+'\invoke-trace-validation.ps1'),'-Mode','Guard','-PackageRoot',$package,'-ExpectedManifestSha256',$ExpectedManifestSha256,'-RunPath',$directory,'-ExpectedLeaseSha256',$leaseSha)
    $line=(@($arguments|ForEach-Object{[SflOwnedRun]::Quote($_)}) -join ' ')
    $guard=Start-TraceProcess $nativePs $line ($directory+'\guard.stdout.log') ($directory+'\guard.stderr.log')
    $guardIdentity=@{pid=$guard.Id;created_filetime=$guard.StartTime.ToUniversalTime().ToFileTimeUtc().ToString()}
    Write-TraceJson ($directory+'\guard-process.json') $guardIdentity
    $readyClock=[Diagnostics.Stopwatch]::StartNew()
    while(-not [IO.File]::Exists($directory+'\ready.json') -and -not $guard.HasExited -and $readyClock.Elapsed.TotalSeconds -lt 45){[Threading.Thread]::Sleep(25)}
    Assert-Trace ([IO.File]::Exists($directory+'\ready.json') -and -not $guard.HasExited) 'request-trace-guard-not-ready'
    $ready=Read-RequestTraceClosedJson ($directory+'\ready.json')
    Assert-Trace ($ready.instance -ceq $lease.instance -and $ready.lease_sha256 -ceq $leaseSha) 'request-trace-ready-binding'
    Assert-Trace ($fixtureParent.Alive()) 'request-trace-fixture-exited-before-go'
    Write-RequestTraceBinding $fixture @{schema='sfl-request-trace-binding-v1';run_id=$request.run_id;fixture_pid=$request.fixture_pid;fixture_created_filetime=$request.fixture_created_filetime;trace_run_path=$directory;lease_sha256=$leaseSha;ready_sha256=(Get-RunFact ($directory+'\ready.json')).sha256;instance=$lease.instance;guard_pid=$guardIdentity.pid;guard_created_filetime=$guardIdentity.created_filetime;release_gate='HOLD';promotion_allowed=$false}
    $workClock=[Diagnostics.Stopwatch]::StartNew()
    while(-not [IO.File]::Exists($fixture+'\complete.json') -and -not [IO.File]::Exists($fixture+'\failure.json') -and $fixtureParent.Alive() -and -not $guard.HasExited -and $workClock.Elapsed.TotalSeconds -lt 5){[Threading.Thread]::Sleep(25)}
    Assert-Trace ([IO.File]::Exists($fixture+'\complete.json') -and -not [IO.File]::Exists($fixture+'\failure.json') -and -not $guard.HasExited) 'request-trace-fixture-incomplete-before-stop'
    $complete=Read-RequestTraceClosedJson ($fixture+'\complete.json')
    $record.workload=Assert-RequestTraceCompletion $complete $request $fixture
    $record.fixture_elapsed_seconds=$workClock.Elapsed.TotalSeconds
}catch{$record.errors+=$_.Exception.Message}
finally{
    if($null -ne $guard){
        try{
            if(-not $guard.HasExited -and -not [IO.File]::Exists($directory+'\stop-request.json')){Write-TraceJson ($directory+'\stop-request.json') @{lease_sha256=$leaseSha}}
            Assert-Trace ($guard.WaitForExit(150000)) 'request-trace-guard-terminal-not-observed-do-not-rerun'
            $record.guard_exit=$guard.ExitCode
            $record.guard_log_completion=Read-TraceProcessLogs $guard ($directory+'\guard.stdout.log') ($directory+'\guard.stderr.log')
            $trace=Read-TraceJson ($directory+'\result.json');$record.trace_result=Get-RunFact ($directory+'\result.json')
            Assert-Trace ($guard.ExitCode -eq 0 -and $trace.status -ceq 'CONTROL_FLOW_COMPLETE' -and $trace.lease_sha256 -ceq $leaseSha -and $trace.cleanup_confirmed -and $trace.trace_saved -and -not $trace.cancelled_without_trace -and $trace.errors.Count -eq 0) 'request-trace-control-flow'
            $record.etl=Get-RunFact ($directory+'\trace.etl')
            Assert-Trace ($record.etl.bytes -eq $trace.etl.bytes -and $record.etl.sha256 -ceq $trace.etl.sha256) 'request-trace-etl-pin'
            if($record.errors.Count -eq 0){$record.status='CAPTURE_COMPLETE_REQUIRES_CORRELATION'}
        }catch{$record.errors+=$_.Exception.Message;$record.status='FAIL'}
    }
    if($directory){
        try{
            Write-TraceJson ($directory+'\request-trace-summary.json') $record
            Write-Host ('RESULT_PATH='+$directory+'\request-trace-summary.json')
            Write-Host ('RESULT_SHA256='+(Get-RunFact ($directory+'\request-trace-summary.json')).sha256)
        }catch{Write-Host ('RESULT_WRITE_FAILED='+$_.Exception.Message)}
    }
    if($null -ne $guard){$guard.Dispose()}
    if($null -ne $fixtureParent){$fixtureParent.Dispose()}
    foreach($stream in $held){$stream.Dispose()}
}
$record|ConvertTo-Json -Depth 12
if($record.status -cne 'CAPTURE_COMPLETE_REQUIRES_CORRELATION'){exit 1};exit 0
