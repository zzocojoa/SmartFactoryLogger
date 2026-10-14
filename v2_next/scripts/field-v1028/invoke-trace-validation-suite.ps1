[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$PackageRoot,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedManifestSha256
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$held=[Collections.Generic.List[IO.Stream]]::new();$suitePath=$null
$summary=[ordered]@{status='FAIL';scope='LOCAL_WPR_CONTROLLER_LIFECYCLE_ONLY';scenarios=@();errors=@();release_gate='HOLD';promotion_allowed=$false;field_gate='NOT_EVALUATED';trace_quality='NOT_EVALUATED'}
try{
    $nativePs=[IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
    $summary.runtime=[ordered]@{is_64_bit_process=[Environment]::Is64BitProcess;ps_edition=$PSVersionTable.PSEdition;ps_version=$PSVersionTable.PSVersion.ToString();expected_executable=$nativePs;actual_executable=[Diagnostics.Process]::GetCurrentProcess().MainModule.FileName}
    if(-not ($summary.runtime.is_64_bit_process -and $summary.runtime.ps_edition -ceq 'Desktop' -and $summary.runtime.ps_version.StartsWith('5.1.') -and $summary.runtime.actual_executable -ieq $nativePs)){throw 'native PS5.1 x64 required'}
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
    if(-not ([Security.Principal.WindowsPrincipal]::new($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'administrator PowerShell required'}
    # Bootstrap pins this suite. Lock and verify the package before importing
    # any function from it; no package top-level code is evaluated here.
    $package=[IO.Path]::GetFullPath($PackageRoot).TrimEnd('\')
    $manifestPath=$package+'\manifest.json'
    $manifestStream=[IO.File]::Open($manifestPath,'Open','Read','Read');$held.Add($manifestStream)
    if($manifestStream.Length -gt 64KB){throw 'manifest budget'}
    $sha=[Security.Cryptography.SHA256]::Create()
    try{$digest=[BitConverter]::ToString($sha.ComputeHash($manifestStream)).Replace('-','').ToLowerInvariant()}finally{$sha.Dispose()}
    if($digest -cne $ExpectedManifestSha256){throw 'manifest pin'}
    $manifestStream.Position=0
    $reader=[IO.StreamReader]::new($manifestStream,[Text.UTF8Encoding]::new($false,$true),$true,4096,$true)
    try{$manifest=$reader.ReadToEnd()|ConvertFrom-Json}finally{$reader.Dispose()}
    $required=@('invoke-trace-validation.ps1','invoke-field-run.template.ps1','SFLThreadScheduling.wprp')
    if($manifest.schema -cne 'sfl-trace-validation-package-v1' -or @($manifest.files.PSObject.Properties).Count -ne 3){throw 'manifest schema/members'}
    foreach($name in $required){
        $stream=[IO.File]::Open(($package+'\'+$name),'Open','Read','Read');$held.Add($stream)
        if($stream.Length -ne $manifest.files.$name.bytes -or $stream.Length -gt 1MB){throw ('package size: '+$name)}
        $sha=[Security.Cryptography.SHA256]::Create()
        try{$digest=[BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-','').ToLowerInvariant()}finally{$sha.Dispose()}
        if($digest -cne $manifest.files.$name.sha256 -or $stream.Length -ne $manifest.files.$name.bytes){throw ('package pin: '+$name)}
    }
    foreach($name in @('invoke-field-run.template.ps1','invoke-trace-validation.ps1')){
        $tokens=$null;$parseErrors=$null
        $ast=[Management.Automation.Language.Parser]::ParseFile(($package+'\'+$name),[ref]$tokens,[ref]$parseErrors)
        if($parseErrors.Count){throw 'package parse'}
        foreach($f in @($ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst]},$false))){. ([scriptblock]::Create($f.Extent.Text))}
    }
    [void](Get-TracePath $package)
    Initialize-TraceHandles;Initialize-RunNative
    Assert-Trace (-not [SflTraceParent]::CurrentInJob()) 'suite-must-be-outside-other-job'
    $parent=Get-TracePath ([IO.Path]::Combine([Environment]::GetFolderPath('Desktop'),'SmartFactory'))
    Assert-Trace ([IO.Directory]::Exists($parent)) 'desktop-parent-required'
    $suitePath=Get-TracePath ($parent+'\TS'+[Guid]::NewGuid().ToString('N').Substring(0,12))
    Assert-Trace (-not [IO.Directory]::Exists($suitePath) -and -not [IO.File]::Exists($suitePath)) 'suite-new-path'
    [void][IO.Directory]::CreateDirectory($suitePath,(New-RunAcl $identity.User.Value));Assert-RunAcl $suitePath $identity.User.Value
    Write-Host ('TRACE_SUITE_PATH='+$suitePath)
    foreach($scenario in @('Normal','ControllerExit','Deadline')){
        $arguments=@('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',($package+'\invoke-trace-validation.ps1'),'-Mode','Run','-Scenario',$scenario,'-PackageRoot',$package,'-ExpectedManifestSha256',$ExpectedManifestSha256)
        $line=(@($arguments|ForEach-Object{[SflOwnedRun]::Quote($_)}) -join ' ')
        $out=$suitePath+'\'+$scenario+'.stdout.log';$err=$suitePath+'\'+$scenario+'.stderr.log'
        $controller=Start-Process -FilePath $nativePs -ArgumentList $line -WindowStyle Hidden -PassThru -RedirectStandardOutput $out -RedirectStandardError $err
        Assert-Trace ($controller.WaitForExit(240000)) 'controller-terminal-not-observed-do-not-rerun'
        Assert-Trace (([IO.FileInfo]::new($out)).Length -le 64KB -and ([IO.FileInfo]::new($err)).Length -le 64KB) 'controller-log-budget'
        $output=[IO.File]::ReadAllText($out)
        $pathMatches=[regex]::Matches($output,'(?m)^TRACE_RUN_PATH=(.+)\r?$')
        Assert-Trace ($pathMatches.Count -eq 1) 'controller-run-path-missing'
        $run=Get-TracePath $pathMatches[0].Groups[1].Value.Trim()
        Assert-Trace ([IO.Path]::GetDirectoryName($run) -ieq $parent -and [IO.Path]::GetFileName($run) -cmatch '^T[0-9a-f]{12}$') 'controller-run-path-boundary'
        $item=[ordered]@{scenario=$scenario;run_path=$run;controller_exit=$controller.ExitCode}
        $summary.scenarios+=$item
        Assert-Trace ($controller.ExitCode -eq $(if($scenario -ceq 'ControllerExit'){23}else{0})) 'controller-exit-unexpected'
        $guard=Read-TraceJson ($run+'\guard-process.json')
        $clock=[Diagnostics.Stopwatch]::StartNew()
        while([SflTraceParent]::GenerationAlive([uint32]$guard.pid,[int64]$guard.created_filetime) -and $clock.Elapsed.TotalSeconds -lt 180){Start-Sleep -Milliseconds 100}
        Assert-Trace (-not [SflTraceParent]::GenerationAlive([uint32]$guard.pid,[int64]$guard.created_filetime)) 'guard-terminal-not-observed-do-not-rerun'
        $result=Read-TraceJson ($run+'\result.json')
        $item.result=Get-RunFact ($run+'\result.json')
        $item.reason=$result.reason;$item.cleanup_confirmed=$result.cleanup_confirmed
        $reason=switch($scenario){'Normal' {'controller-requested-stop'} 'ControllerExit' {'controller-exited'} 'Deadline' {'guard-deadline'}}
        Assert-Trace ($result.status -ceq 'CONTROL_FLOW_COMPLETE' -and $result.cleanup_confirmed -and $result.trace_saved -and -not $result.cancelled_without_trace -and $result.errors.Count -eq 0 -and $result.reason -ceq $reason -and $result.release_gate -ceq 'HOLD' -and -not $result.promotion_allowed) 'scenario-control-flow-failed'
        Assert-Trace ($result.etl.name -ceq 'trace.etl') 'trace-member-name'
        $etl=Get-RunFact ($run+'\trace.etl')
        Assert-Trace ($etl.bytes -eq $result.etl.bytes -and $etl.sha256 -ceq $result.etl.sha256) 'trace-bytes-changed'
        $item.etl=$etl
        Write-Host ($scenario+'=CONTROL_FLOW_COMPLETE')
    }
    $summary.status='CONTROL_FLOW_COMPLETE'
}catch{$summary.errors+=$_.Exception.Message}
finally{
    if($suitePath){
        try{
            Write-TraceJson ($suitePath+'\summary.json') $summary
            Write-Host ('RESULT_PATH='+$suitePath+'\summary.json')
            Write-Host ('RESULT_SHA256='+(Get-RunFact ($suitePath+'\summary.json')).sha256)
        }catch{Write-Host ('RESULT_WRITE_FAILED='+$_.Exception.Message)}
    }
    foreach($stream in $held){$stream.Dispose()}
}
$summary|ConvertTo-Json -Depth 12
if($summary.status -cne 'CONTROL_FLOW_COMPLETE'){exit 1};exit 0
