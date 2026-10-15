param([Parameter(Mandatory=$true)][string]$OutputParent)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$source=Join-Path $PSScriptRoot 'observe-health-runtime-close.ps1'
. $source -LibraryOnly
$root=Join-Path $OutputParent ('runtime-close-tests-'+[Guid]::NewGuid().ToString('N'))
$null=New-Item -ItemType Directory -Path $root
$checks=[Collections.Generic.List[object]]::new()
function Check([string]$Name,[scriptblock]$Action){& $Action;$checks.Add([ordered]@{name=$Name;status='PASS'})}
function Reject([scriptblock]$Action,[string]$Expected){
    try{& $Action;throw 'expected-rejection-missing'}catch{if($_.Exception.Message -cne $Expected){throw}}
}
Check 'powershell-parser' {
    $tokens=$null;$errors=$null;$null=[Management.Automation.Language.Parser]::ParseFile($source,[ref]$tokens,[ref]$errors)
    Require-Runtime ($errors.Count -eq 0) 'parse-errors'
}
Check 'actual-held-native-process-exit-23' {
    $native=[Environment]::SystemDirectory+'\WindowsPowerShell\v1.0\powershell.exe'
    $info=[Diagnostics.ProcessStartInfo]::new($native,'-NoProfile -NonInteractive -Command "Start-Sleep -Seconds 2; exit 23"')
    $info.UseShellExecute=$false;$info.CreateNoWindow=$true;$info.WindowStyle='Hidden'
    $child=[Diagnostics.Process]::Start($info);$bound=$null
    try{
        $bound=Hold-RuntimeProcess $child.Id $native
        Require-Runtime ($bound.identity.created_filetime -eq $child.StartTime.ToUniversalTime().ToFileTimeUtc()) 'native-creation-pin'
        Reject {Read-RuntimeExit $bound} 'held-process-still-running'
        Wait-RuntimeProcesses @($bound) 10000
        $receipt=Read-RuntimeExit $bound
        Require-Runtime ($receipt.actual_exit_code -eq 23 -and -not $receipt.forced_termination) 'native-exit-code'
        $null=Write-RuntimeJson ($root+'\native-exit.json') $receipt
    }finally{if($bound){$bound.process.Dispose()};$child.Dispose()}
}
Check 'early-hasexited-does-not-bypass-native-signal' {
    $fake=[pscustomobject]@{HasExited=$true;wait_calls=0}
    $fake|Add-Member ScriptMethod WaitForExit {param($milliseconds);$this.wait_calls++;return $this.wait_calls -ge 2}
    Wait-RuntimeProcesses @([pscustomobject]@{process=$fake}) 3000
    Require-Runtime ($fake.wait_calls -eq 2) 'early-hasexited-not-waited'
}
Check 'all-native-signals-required-and-timeout-does-not-force' {
    $ready=[pscustomobject]@{HasExited=$true;wait_calls=0}
    $ready|Add-Member ScriptMethod WaitForExit {param($milliseconds);$this.wait_calls++;return $true}
    $pending=[pscustomobject]@{HasExited=$true;wait_calls=0}
    $pending|Add-Member ScriptMethod WaitForExit {param($milliseconds);$this.wait_calls++;return $false}
    $watch=[Diagnostics.Stopwatch]::StartNew()
    Reject {Wait-RuntimeProcesses @([pscustomobject]@{process=$ready},[pscustomobject]@{process=$pending}) 50} 'normal-exit-timeout-no-force'
    Require-Runtime ($ready.wait_calls -ge 2 -and $pending.wait_calls -ge 2 -and $watch.ElapsedMilliseconds -lt 2000) 'native-wait-timeout-contract'
    Reject {Wait-RuntimeProcesses @() 100} 'exit-wait-budget'
    Reject {Wait-RuntimeProcesses @([pscustomobject]@{process=$ready}) 450001} 'exit-wait-budget'
}
Check 'native-wrong-executable-rejected' {
    Reject {Hold-RuntimeProcess $PID 'C:\not-the-current-process.exe'} 'process-executable-mismatch'
}
Check 'no-overwrite-and-byte-budget' {
    $path=$root+'\source.dat';$bytes=[Text.Encoding]::UTF8.GetBytes('fixture-data')
    $pin=Write-RuntimeBytes $path $bytes
    Require-Runtime ((Hash-Runtime (Read-RuntimeBytes $path)) -ceq $pin.sha256) 'read-write-pin'
    Reject {Read-RuntimeBytes $path 2} 'file-byte-budget'
    $failed=$false;try{$null=Write-RuntimeBytes $path ([byte[]]@(1))}catch{$failed=$true}
    Require-Runtime ($failed -and (Hash-Runtime (Read-RuntimeBytes $path)) -ceq $pin.sha256) 'existing-file-modified'
}
Check 'path-and-stream-guards' {
    Reject {Plain-Runtime 'relative.txt'} 'absolute-local-path'
    Reject {Plain-Runtime 'C:\tmp\file:stream'} 'absolute-local-path'
    Reject {Plain-Runtime ('C:\'+('a'*240))} 'path-budget'
}
Check 'live-process-or-listener-not-cold' {
    Assert-RuntimeCold @{processes=@();listeners=@()}
    Reject {Assert-RuntimeCold @{processes=@(1);listeners=@()}} 'application-or-port-active'
    Reject {Assert-RuntimeCold @{processes=@();listeners=@(1)}} 'application-or-port-active'
}
Check 'request-build-and-csv-guards' {
    $r=[pscustomobject]@{schema='sfl-health-runtime-close-request-v1';candidate_commit='acaf77d95101a050f4d3ecd76125d3502036f5a7';logger_service_instance_id='c7bad677-3827-4da6-b4a0-920f9e5629e6';csv_name='Factory_Integrated_Log_v2_20261015_212251.csv';config_sha256=('a'*64)}
    Assert-RuntimeRequest $r
    $r.csv_name='..\outside.csv';Reject {Assert-RuntimeRequest $r} 'request-generation'
    $r.candidate_commit='wrong';Reject {Assert-RuntimeRequest $r} 'request-contract'
}
Check 'real-controller-development-host-denied' {
    Require-Runtime ($env:COMPUTERNAME -cne 'DESKTOP-CIIT7LK') 'test-must-run-on-development-host'
    $native=[Environment]::SystemDirectory+'\WindowsPowerShell\v1.0\powershell.exe'
    $output=& $native -NoProfile -NonInteractive -File $source -RequestPath ($root+'\missing.json') -ExpectedRequestSha256 ('a'*64)
    Require-Runtime ($LASTEXITCODE -eq 1 -and ($output -join "`n") -match 'server-operator-admin-required') 'controller-host-guard'
}
$null=Write-RuntimeJson ($root+'\summary.json') ([ordered]@{status='PASS';scope='LOCAL_NATIVE_AND_CONTRACT_CHECKS_NOT_SERVER_LIFECYCLE';checks=$checks;server_execution=$false;release_gate='HOLD'})
Write-Output ('TEST_RESULT_PATH='+$root)
Write-Output ('CHECKS='+$checks.Count)
