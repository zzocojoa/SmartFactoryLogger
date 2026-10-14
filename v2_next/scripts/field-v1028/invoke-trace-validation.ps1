[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidateSet('Run','Guard','Recover')][string]$Mode,
    [Parameter(Mandatory=$true)][string]$PackageRoot,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedManifestSha256,
    [string]$RunPath,
    [ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedLeaseSha256,
    [ValidateSet('Normal','ControllerExit','Deadline')][string]$Scenario='Normal'
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'

function Assert-Trace([bool]$Condition,[string]$Reason){if(-not $Condition){throw $Reason}}
function Get-TraceHash([IO.Stream]$Stream){
    $hash=[Security.Cryptography.SHA256]::Create()
    try{$Stream.Position=0;return [BitConverter]::ToString($hash.ComputeHash($Stream)).Replace('-','').ToLowerInvariant()}
    finally{$hash.Dispose()}
}
function Get-TracePath([string]$Path){
    Assert-Trace ($Path -cmatch '^[A-Za-z]:[\\/]' -and $Path -notmatch '[\x00-\x1f]') 'trace-absolute-path'
    $full=[IO.Path]::GetFullPath($Path).TrimEnd('\')
    Assert-Trace ($full.Length -gt 3 -and $full.Length -le 230 -and $full.Substring(2) -notmatch ':') 'trace-path-budget'
    $node=[IO.FileInfo]::new($full)
    while($null -ne $node){
        Assert-Trace ([int]$node.Attributes -eq -1 -or ($node.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'trace-reparse-path'
        if($node -is [IO.FileInfo]){$node=$node.Directory}else{$node=$node.Parent}
    }
    return $full
}
function Write-TraceJson([string]$Path,$Value){
    $bytes=[Text.UTF8Encoding]::new($false).GetBytes(($Value|ConvertTo-Json -Depth 30))
    $stream=[IO.File]::Open((Get-TracePath $Path),'CreateNew','Write','None')
    try{$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
}
function Read-TraceJson([string]$Path){
    $stream=[IO.File]::Open((Get-TracePath $Path),'Open','Read','Read')
    try{
        Assert-Trace ($stream.Length -le 64KB) 'trace-json-budget'
        $reader=[IO.StreamReader]::new($stream,[Text.UTF8Encoding]::new($false,$true),$true,4096,$true)
        try{return ($reader.ReadToEnd()|ConvertFrom-Json)}finally{$reader.Dispose()}
    }finally{$stream.Dispose()}
}
function Initialize-TraceHandles {
    if('SflTraceParent' -as [type]){return}
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
public sealed class SflTraceParent : IDisposable {
    [DllImport("kernel32.dll",SetLastError=true)] static extern IntPtr OpenProcess(uint a,bool i,uint p);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool GetProcessTimes(IntPtr h,out long c,out long e,out long k,out long u);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool IsProcessInJob(IntPtr p,IntPtr j,out bool member);
    [DllImport("kernel32.dll")] static extern IntPtr GetCurrentProcess();
    [DllImport("kernel32.dll",SetLastError=true)] static extern uint WaitForSingleObject(IntPtr h,uint ms);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool CloseHandle(IntPtr h);
    IntPtr handle;
    static void Check(bool ok){if(!ok)throw new Win32Exception(Marshal.GetLastWin32Error());}
    public static bool CurrentInJob(){bool member;Check(IsProcessInJob(GetCurrentProcess(),IntPtr.Zero,out member));return member;}
    public static bool GenerationAlive(uint pid,long created){
        IntPtr h=OpenProcess(0x101000,false,pid);
        if(h==IntPtr.Zero){int error=Marshal.GetLastWin32Error();if(error==87)return false;throw new Win32Exception(error);}
        try{long c,e,k,u;Check(GetProcessTimes(h,out c,out e,out k,out u));if(c!=created)return false;
            uint r=WaitForSingleObject(h,0);if(r==258)return true;if(r==0)return false;throw new Win32Exception(Marshal.GetLastWin32Error());}
        finally{CloseHandle(h);}
    }
    public SflTraceParent(uint pid,long created){
        handle=OpenProcess(0x101000,false,pid);Check(handle!=IntPtr.Zero);
        try{long c,e,k,u;Check(GetProcessTimes(handle,out c,out e,out k,out u));if(c!=created)throw new InvalidOperationException("parent-generation-mismatch");}
        catch{Dispose();throw;}
    }
    public bool Alive(){uint r=WaitForSingleObject(handle,0);if(r==258)return true;if(r==0)return false;throw new Win32Exception(Marshal.GetLastWin32Error());}
    public void Dispose(){if(handle!=IntPtr.Zero){CloseHandle(handle);handle=IntPtr.Zero;}}
}
'@
}
function Read-TraceState($Command){
    if($Command.status -cne 'PASS' -or $Command.actual_exit_code -ne 0){return 'UNKNOWN'}
    $text=$Command.stdout
    $absent=$text -cmatch '(?m)^WPR is not recording\s*$'
    $active=$text -cmatch '(?m)^WPR recording is in progress\.\.\.\s*$'
    if($absent -and -not $active){return 'ABSENT'}
    if($active -and -not $absent){return 'ACTIVE'}
    return 'UNKNOWN'
}
function Assert-TraceLease($Lease,[string]$Directory){
    Assert-Trace ($Lease.schema -ceq 'sfl-local-trace-lease-v1' -and $Lease.scope -ceq 'LOCAL_CONTROLLER_VALIDATION_ONLY') 'trace-lease-schema'
    Assert-Trace ($Lease.instance -cmatch '^SFLTrace_[0-9a-f]{32}$') 'trace-instance'
    Assert-Trace ($Lease.run_path -ieq $Directory -and $Lease.parent_pid -is [int] -and $Lease.parent_pid -gt 0) 'trace-parent-binding'
    Assert-Trace ($Lease.parent_created_filetime -cmatch '^[0-9]{17,20}$') 'trace-parent-creation'
    Assert-Trace ($Lease.guard_seconds -eq 8 -and $Lease.stop_timeout_seconds -eq 60) 'trace-fixed-budget'
    Assert-Trace ($Lease.profile_sha256 -ceq '603c872d5bb638661eb6e133f2b23b4f778e8bab5f440dbda3017c09ea0ff486') 'trace-profile-pin'
    Assert-Trace ($Lease.release_gate -ceq 'HOLD' -and $Lease.promotion_allowed -is [bool] -and -not $Lease.promotion_allowed) 'trace-lease-gate'
}
function Invoke-TraceNative([string]$Executable,[string[]]$Arguments,[string]$Directory,[string]$EnvironmentRoot,[int]$TimeoutSeconds){
    Assert-Trace ($TimeoutSeconds -gt 0 -and $TimeoutSeconds -le 60) 'trace-command-budget'
    Assert-Trace (-not [IO.Directory]::Exists($Directory) -and -not [IO.File]::Exists($Directory)) 'trace-command-directory-new'
    [void][IO.Directory]::CreateDirectory((Get-TracePath $Directory))
    $environment=[Collections.Generic.SortedDictionary[string,string]]::new([StringComparer]::OrdinalIgnoreCase)
    $environment['SYSTEMROOT']=[Environment]::GetFolderPath('Windows');$environment['WINDIR']=$environment['SYSTEMROOT']
    $environment['SYSTEMDRIVE']=[IO.Path]::GetPathRoot($environment['SYSTEMROOT']).TrimEnd('\')
    $environment['PATH']=[Environment]::SystemDirectory+';'+$environment['SYSTEMROOT']
    foreach($key in @('APPDATA','LOCALAPPDATA','TEMP','TMP')){$environment[$key]=Get-TracePath ($EnvironmentRoot+'\'+$key)}
    $block=(($environment.GetEnumerator()|ForEach-Object{$_.Key+'='+$_.Value+[char]0}) -join '')+[char]0
    $child=$null;$clock=[Diagnostics.Stopwatch]::StartNew()
    $record=[ordered]@{status='FAIL';actual_exit_code=$null;termination_requested=$false;errors=@();arguments=$Arguments}
    try{
        $child=[SflOwnedRun]::new($Executable,$Arguments,$block,$Directory,($Directory+'\stdout.log'),($Directory+'\stderr.log'))
        $record.pid=$child.Pid
        # This command contract waits for the complete command tree within the
        # original deadline. It does not alter the field runner's existing gate.
        do{
            $rootExited=$child.Wait(25);$accounting=$child.Accounting()
            Assert-Trace ($clock.Elapsed.TotalSeconds -lt $TimeoutSeconds) 'trace-command-deadline'
            foreach($name in @('stdout.log','stderr.log')){Assert-Trace (([IO.FileInfo]::new($Directory+'\'+$name)).Length -le 2MB) 'trace-command-output-budget'}
            if($rootExited -and $accounting[1] -eq 0){break}
            if($rootExited){[Threading.Thread]::Sleep(10)}
        }while($true)
        $record.actual_exit_code=$child.ExitCode();$record.job_terminal=$accounting
        if($record.actual_exit_code -eq 0){$record.status='PASS'}
    }catch{$record.errors+=$_.Exception.Message}
    finally{
        if($null -ne $child){
            try{
                if($child.Accounting()[1] -ne 0){$record.termination_requested=$true;$record.status='FAIL';$child.Terminate()}
                $drain=[Diagnostics.Stopwatch]::StartNew()
                while($child.Accounting()[1] -ne 0 -and $drain.Elapsed.TotalSeconds -lt 10){[Threading.Thread]::Sleep(25)}
                $record.job_after_cleanup=$child.Accounting();Assert-Trace ($record.job_after_cleanup[1] -eq 0) 'trace-command-cleanup-unconfirmed'
                if($child.Wait(0)){$record.actual_exit_code=$child.ExitCode()}
            }catch{$record.errors+=$_.Exception.Message;$record.status='FAIL'}
            finally{$child.Dispose()}
        }
        if($record.errors.Count -gt 0 -or $record.termination_requested){$record.status='FAIL'}
        $record.elapsed_seconds=$clock.Elapsed.TotalSeconds
    }
    foreach($name in @('stdout','stderr')){
        $record[$name]=''
        try{
            $file=[IO.FileInfo]::new($Directory+'\'+$name+'.log')
            Assert-Trace ($file.Exists -and $file.Length -le 2MB) 'trace-command-log-unavailable-or-oversize'
            $record[$name]=[IO.File]::ReadAllText($file.FullName)
        }catch{$record.errors+=$_.Exception.Message;$record.status='FAIL'}
    }
    try{Write-TraceJson ($Directory+'\command.json') $record}
    catch{$record.errors+=$_.Exception.Message;$record.status='FAIL'}
    return $record
}
function Stop-TraceOwned([scriptblock]$Command,[string]$OutputName){
    $record=[ordered]@{cleanup_confirmed=$false;trace_saved=$false;cancelled_without_trace=$false;commands=@();errors=@()}
    # Each cleanup step is independent: a failed stop/log write must not skip
    # querying and cancelling this owned instance. Never cancel the default one.
    try{
        $stop=& $Command 'stop' $OutputName;$record.commands+=@{operation='stop';result=$stop}
        $record.trace_saved=$stop.status -ceq 'PASS'
    }catch{$record.errors+=$_.Exception.Message}
    $state='UNKNOWN'
    try{$after=& $Command 'status' $null;$record.commands+=@{operation='status-after-stop';result=$after};$state=Read-TraceState $after}
    catch{$record.errors+=$_.Exception.Message}
    if($state -cne 'ABSENT'){
        $record.cancelled_without_trace=$true
        try{$cancel=& $Command 'cancel' $null;$record.commands+=@{operation='cancel-owned-failed-session';result=$cancel}}
        catch{$record.errors+=$_.Exception.Message}
        try{$after=& $Command 'status' $null;$record.commands+=@{operation='status-after-cancel';result=$after};$state=Read-TraceState $after}
        catch{$record.errors+=$_.Exception.Message}
    }
    $record.cleanup_confirmed=$state -ceq 'ABSENT'
    if(-not $record.cleanup_confirmed){$record.errors+='trace-cleanup-unconfirmed'}
    return $record
}
function Invoke-TraceLifecycle($Lease,[scriptblock]$Command,[scriptblock]$ParentAlive,[scriptblock]$StopRequested,[scriptblock]$Ready,[scriptblock]$Elapsed,[scriptblock]$Pause,[scriptblock]$StartIntent){
    $record=[ordered]@{status='FAIL';instance=$Lease.instance;start_attempted=$false;start_confirmed=$false;cleanup_confirmed=$false;trace_saved=$false;cancelled_without_trace=$false;reason=$null;commands=@();errors=@();release_gate='HOLD';promotion_allowed=$false}
    try{
        $pre=& $Command 'status' $null;$record.commands+=@{operation='status-before';result=$pre}
        Assert-Trace ((Read-TraceState $pre) -ceq 'ABSENT') 'trace-instance-not-provably-unused'
        Assert-Trace (& $ParentAlive) 'trace-parent-not-alive-before-start'
        & $StartIntent
        $record.start_attempted=$true
        $start=& $Command 'start' $null;$record.commands+=@{operation='start';result=$start}
        Assert-Trace ($start.status -ceq 'PASS') 'trace-start-command-failed'
        $active=& $Command 'status' $null;$record.commands+=@{operation='status-after-start';result=$active}
        Assert-Trace ((Read-TraceState $active) -ceq 'ACTIVE') 'trace-start-not-confirmed'
        $record.start_confirmed=$true;& $Ready
        do{
            if(-not (& $ParentAlive)){$record.reason='controller-exited';break}
            if(& $StopRequested){$record.reason='controller-requested-stop';break}
            if((& $Elapsed) -ge $Lease.guard_seconds){$record.reason='guard-deadline';break}
            & $Pause
        }while($true)
    }catch{$record.errors+=$_.Exception.Message}
    finally{
        if($record.start_attempted){
            $cleanup=Stop-TraceOwned $Command 'trace.etl'
            foreach($key in @('cleanup_confirmed','trace_saved','cancelled_without_trace')){$record[$key]=$cleanup[$key]}
            $record.commands+=$cleanup.commands;$record.errors+=$cleanup.errors
        }
    }
    if($record.start_confirmed -and $record.cleanup_confirmed -and $record.trace_saved -and -not $record.cancelled_without_trace -and $record.errors.Count -eq 0){$record.status='CONTROL_FLOW_COMPLETE'}
    return $record
}
function Assert-TraceRecovery($Intent,$Lease,[string]$LeaseSha,[string]$ManifestSha,[scriptblock]$GenerationAlive){
    Assert-Trace ($Intent.schema -ceq 'sfl-trace-start-intent-v1' -and $Intent.instance -ceq $Lease.instance -and $Intent.lease_sha256 -ceq $LeaseSha -and $Intent.manifest_sha256 -ceq $ManifestSha -and $Intent.observed_before_start -ceq 'ABSENT') 'trace-recovery-ownership'
    Assert-Trace ($Intent.guard_pid -is [int] -and $Intent.guard_pid -gt 0 -and $Intent.guard_created_filetime -cmatch '^[0-9]{17,20}$') 'trace-recovery-guard-identity'
    Assert-Trace (-not (& $GenerationAlive $Intent.guard_pid $Intent.guard_created_filetime)) 'trace-recovery-guard-still-alive'
}

$held=[Collections.Generic.List[IO.Stream]]::new();$traceParent=$null;$directory=$null
try{
    $nativePs=[IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
    Assert-Trace ([Environment]::Is64BitProcess -and $PSVersionTable.PSEdition -ceq 'Desktop' -and $PSVersionTable.PSVersion.Major -eq 5 -and $PSVersionTable.PSVersion.Minor -eq 1 -and [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName -ieq $nativePs) 'trace-native-ps51-required'
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
    Assert-Trace (([Security.Principal.WindowsPrincipal]::new($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) 'trace-elevated-context-required'
    Initialize-TraceHandles
    Assert-Trace (-not [SflTraceParent]::CurrentInJob()) 'trace-controller-must-be-outside-other-job'
    Assert-Trace ([Environment]::ProcessorCount -le 128) 'trace-nominal-buffer-cpu-budget'
    $package=Get-TracePath $PackageRoot
    $manifestStream=[IO.File]::Open((Get-TracePath ($package+'\manifest.json')),'Open','Read','Read');$held.Add($manifestStream)
    Assert-Trace ($manifestStream.Length -le 64KB -and (Get-TraceHash $manifestStream) -ceq $ExpectedManifestSha256) 'trace-manifest-pin'
    $manifestStream.Position=0;$reader=[IO.StreamReader]::new($manifestStream,[Text.UTF8Encoding]::new($false,$true),$true,4096,$true)
    try{$manifest=$reader.ReadToEnd()|ConvertFrom-Json}finally{$reader.Dispose()}
    Assert-Trace ($manifest.schema -ceq 'sfl-trace-validation-package-v1') 'trace-package-schema'
    $required=@('invoke-trace-validation.ps1','invoke-field-run.template.ps1','SFLThreadScheduling.wprp')
    Assert-Trace (@($manifest.files.PSObject.Properties).Count -eq $required.Count) 'trace-package-members'
    foreach($name in $required){
        $stream=[IO.File]::Open((Get-TracePath ($package+'\'+$name)),'Open','Read','Read');$held.Add($stream)
        Assert-Trace ($stream.Length -eq $manifest.files.$name.bytes -and (Get-TraceHash $stream) -ceq $manifest.files.$name.sha256) 'trace-package-file-pin'
    }
    Assert-Trace ($PSCommandPath -ieq ($package+'\invoke-trace-validation.ps1')) 'trace-entry-source-path'
    $tokens=$null;$parseErrors=$null
    $ast=[Management.Automation.Language.Parser]::ParseFile(($package+'\invoke-field-run.template.ps1'),[ref]$tokens,[ref]$parseErrors)
    Assert-Trace ($parseErrors.Count -eq 0) 'trace-native-helper-parse'
    foreach($function in @($ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst]},$false))){. ([scriptblock]::Create($function.Extent.Text))}
    Initialize-RunNative
    $operatorSid=$identity.User.Value
    if($Mode -ceq 'Run'){
        $parent=Get-TracePath ([IO.Path]::Combine([Environment]::GetFolderPath('Desktop'),'SmartFactory'))
        Assert-Trace ([IO.Directory]::Exists($parent)) 'trace-desktop-parent-required'
        $directory=Get-TracePath ($parent+'\T'+[Guid]::NewGuid().ToString('N').Substring(0,12))
        Assert-Trace (-not [IO.Directory]::Exists($directory) -and -not [IO.File]::Exists($directory)) 'trace-new-run-required'
        [void][IO.Directory]::CreateDirectory($directory,(New-RunAcl $operatorSid));Assert-RunAcl $directory $operatorSid
        foreach($name in @('APPDATA','LOCALAPPDATA','TEMP','TMP')){[void][IO.Directory]::CreateDirectory(($directory+'\'+$name))}
        $lease=[ordered]@{schema='sfl-local-trace-lease-v1';scope='LOCAL_CONTROLLER_VALIDATION_ONLY';instance='SFLTrace_'+[Guid]::NewGuid().ToString('N');run_path=$directory;parent_pid=$PID;parent_created_filetime=([Diagnostics.Process]::GetCurrentProcess().StartTime.ToUniversalTime().ToFileTimeUtc()).ToString();guard_seconds=8;stop_timeout_seconds=60;profile_sha256=$manifest.files.'SFLThreadScheduling.wprp'.sha256;release_gate='HOLD';promotion_allowed=$false}
        Assert-TraceLease ([pscustomobject]$lease) $directory
        Write-TraceJson ($directory+'\lease.json') $lease
        $leaseDigest=[IO.File]::Open(($directory+'\lease.json'),'Open','Read','Read');$held.Add($leaseDigest);$leaseSha=Get-TraceHash $leaseDigest
        Write-Host ('TRACE_RUN_PATH='+$directory);Write-Host ('LEASE_SHA256='+$leaseSha)
        $guardArgs=@('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',($package+'\invoke-trace-validation.ps1'),'-Mode','Guard','-PackageRoot',$package,'-ExpectedManifestSha256',$ExpectedManifestSha256,'-RunPath',$directory,'-ExpectedLeaseSha256',$leaseSha)
        $argumentLine=(@($guardArgs|ForEach-Object{[SflOwnedRun]::Quote($_)}) -join ' ')
        # A separate hidden console and no inherited job ensure closing this
        # controller's window does not also close the sole trace owner.
        $guard=Start-Process -FilePath $nativePs -ArgumentList $argumentLine -WindowStyle Hidden -PassThru -RedirectStandardOutput ($directory+'\guard.stdout.log') -RedirectStandardError ($directory+'\guard.stderr.log')
        Write-TraceJson ($directory+'\guard-process.json') @{pid=$guard.Id;created_filetime=$guard.StartTime.ToUniversalTime().ToFileTimeUtc().ToString()}
        $readyClock=[Diagnostics.Stopwatch]::StartNew()
        while(-not [IO.File]::Exists($directory+'\ready.json') -and -not $guard.HasExited -and $readyClock.Elapsed.TotalSeconds -lt 45){Start-Sleep -Milliseconds 100}
        Assert-Trace ([IO.File]::Exists($directory+'\ready.json')) 'trace-guard-not-ready'
        if($Scenario -ceq 'ControllerExit'){Write-Host 'CONTROLLED_PARENT_EXIT_FOR_GUARD_VALIDATION';exit 23}
        if($Scenario -ceq 'Normal'){Start-Sleep -Seconds 2;Write-TraceJson ($directory+'\stop-request.json') @{lease_sha256=$leaseSha}}
        Assert-Trace ($guard.WaitForExit(150000)) 'trace-guard-terminal-not-observed'
        Assert-Trace ([IO.File]::Exists($directory+'\result.json')) 'trace-guard-result-missing'
        Write-Host ('GUARD_EXIT='+$guard.ExitCode)
        if($guard.ExitCode -ne 0){exit 1};exit 0
    }
    $directory=Get-TracePath $RunPath;Assert-RunAcl $directory $operatorSid
    $leaseStream=[IO.File]::Open((Get-TracePath ($directory+'\lease.json')),'Open','Read','Read');$held.Add($leaseStream)
    Assert-Trace ($leaseStream.Length -le 64KB -and (Get-TraceHash $leaseStream) -ceq $ExpectedLeaseSha256) 'trace-lease-pin'
    $leaseStream.Position=0;$reader=[IO.StreamReader]::new($leaseStream,[Text.UTF8Encoding]::new($false,$true),$true,4096,$true)
    try{$lease=$reader.ReadToEnd()|ConvertFrom-Json}finally{$reader.Dispose()}
    Assert-TraceLease $lease $directory
    Assert-Trace ($lease.profile_sha256 -ceq $manifest.files.'SFLThreadScheduling.wprp'.sha256) 'trace-profile-lease-binding'
    # One guardian/recovery owner at a time. An abandoned file is harmless:
    # exclusivity is provided by the held handle, not by file existence.
    $ownerLock=[IO.File]::Open((Get-TracePath ($directory+'\owner.lock')),'OpenOrCreate','ReadWrite','None');$held.Add($ownerLock)
    if($Mode -ceq 'Guard'){
        Assert-Trace (-not [IO.File]::Exists($directory+'\start-intent.json')) 'trace-start-intent-already-exists'
        $traceParent=[SflTraceParent]::new([uint32]$lease.parent_pid,[int64]$lease.parent_created_filetime)
    }else{
        $intent=Read-TraceJson ($directory+'\start-intent.json')
        Assert-TraceRecovery $intent $lease $ExpectedLeaseSha256 $ExpectedManifestSha256 {param($p,$c) [SflTraceParent]::GenerationAlive([uint32]$p,[int64]$c)}
    }
    $wpr=Get-TracePath ([IO.Path]::Combine([Environment]::SystemDirectory,'wpr.exe'))
    $wprStream=[IO.File]::Open($wpr,'Open','Read','Read');$held.Add($wprStream)
    $wprSha=Get-TraceHash $wprStream
    $prefix=if($Mode -ceq 'Recover'){'recovery-'+[Guid]::NewGuid().ToString('N').Substring(0,8)}else{'cmd'}
    $context=@{index=0}
    $command={param($Operation,$File)
        $argv=switch($Operation){
            'status' {@('-status')}
            'start' {@('-start',($package+'\SFLThreadScheduling.wprp!SFLThreadScheduling.light'))}
            'stop' {Assert-Trace ($File -cmatch '^(trace|recovery-[0-9a-f]{8})\.etl$' -and -not [IO.File]::Exists($directory+'\'+$File)) 'trace-output-already-exists-or-unsafe';@('-stop',($directory+'\'+$File),'-skipPdbGen')}
            'cancel' {@('-cancel')}
            default {throw 'trace-operation-not-allowed'}
        }
        $argv+=@('-instancename',$lease.instance)
        $folder=$directory+'\'+$prefix+'-'+$context.index.ToString('00');$context.index++
        Invoke-TraceNative $wpr $argv $folder $directory $(if($Operation -ceq 'stop'){60}else{20})
    }
    $clock=[Diagnostics.Stopwatch]::StartNew();$traceName='trace.etl';$resultName='result.json'
    if($Mode -ceq 'Guard'){
        $record=Invoke-TraceLifecycle $lease $command {$traceParent.Alive()} {
            if(-not [IO.File]::Exists($directory+'\stop-request.json')){return $false}
            $request=Read-TraceJson ($directory+'\stop-request.json')
            Assert-Trace ($request.lease_sha256 -ceq $ExpectedLeaseSha256) 'trace-stop-request-binding';return $true
        } {Write-TraceJson ($directory+'\ready.json') @{instance=$lease.instance;lease_sha256=$ExpectedLeaseSha256}} {$clock.Elapsed.TotalSeconds} {Start-Sleep -Milliseconds 100} {
            Write-TraceJson ($directory+'\start-intent.json') @{schema='sfl-trace-start-intent-v1';instance=$lease.instance;lease_sha256=$ExpectedLeaseSha256;manifest_sha256=$ExpectedManifestSha256;observed_before_start='ABSENT';guard_pid=$PID;guard_created_filetime=[Diagnostics.Process]::GetCurrentProcess().StartTime.ToUniversalTime().ToFileTimeUtc().ToString()}
        }
    }else{
        $traceName=$prefix+'.etl';$resultName=$prefix+'.json'
        $record=Stop-TraceOwned $command $traceName
        $record.status=if($record.cleanup_confirmed){'OWNED_SESSION_CLEANUP_CONFIRMED'}else{'FAIL'}
        $record.instance=$lease.instance;$record.release_gate='HOLD';$record.promotion_allowed=$false
        $record.validation_passed=$false
    }
    $record.wpr_sha256=$wprSha;$record.lease_sha256=$ExpectedLeaseSha256;$record.actual_trace_duration_quality='NOT_EVALUATED'
    $record.field_gate='NOT_EVALUATED';$record.trace_analysis='NOT_EVALUATED'
    if($record.trace_saved){
        $traceFile=$null
        try{
            $traceFile=[IO.File]::Open((Get-TracePath ($directory+'\'+$traceName)),'Open','Read','Read')
            Assert-Trace ($traceFile.Length -gt 0 -and $traceFile.Length -le 256MB) 'trace-result-size-budget'
            $record.etl=@{name=$traceName;bytes=$traceFile.Length;sha256=(Get-TraceHash $traceFile)}
        }catch{$record.status='FAIL';$record.errors+=$_.Exception.Message;$record.trace_saved=$false}
        finally{if($null -ne $traceFile){$traceFile.Dispose()}}
    }
    Write-TraceJson ($directory+'\'+$resultName) $record
    $resultStream=[IO.File]::Open(($directory+'\'+$resultName),'Open','Read','Read');$held.Add($resultStream)
    Write-Host ('TRACE_RESULT='+$directory+'\'+$resultName);Write-Host ('RESULT_SHA256='+(Get-TraceHash $resultStream))
    if($record.status -cnotin @('CONTROL_FLOW_COMPLETE','OWNED_SESSION_CLEANUP_CONFIRMED')){exit 1};exit 0
}catch{
    $failure=@{status='FAIL';reason=$_.Exception.Message;release_gate='HOLD';promotion_allowed=$false}
    $failure|ConvertTo-Json -Compress
    if($directory -and [IO.Directory]::Exists($directory)){
        try{Write-TraceJson ($directory+'\failure-'+[Guid]::NewGuid().ToString('N').Substring(0,8)+'.json') $failure}catch{Write-Host 'FAILURE_RECORD_WRITE_FAILED'}
    }
    exit 1
}finally{
    if($null -ne $traceParent){$traceParent.Dispose()}
    foreach($stream in $held){$stream.Dispose()}
}
