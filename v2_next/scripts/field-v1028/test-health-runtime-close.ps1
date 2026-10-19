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
Check 'actual-stream-copy-above-legacy-limit-and-independent-hash' {
    $inputPath=$root+'\large-source.csv';$outputPath=$root+'\large-copy.csv'
    $file=[IO.File]::Open($inputPath,'CreateNew','Write','None')
    try{
        $file.SetLength(134217745);$file.WriteByte(17)
        $null=$file.Seek(67108864,'Begin');$file.WriteByte(41)
        $null=$file.Seek(-1,'End');$file.WriteByte(99);$file.Flush($true)
    }finally{$file.Dispose()}
    Reject {Copy-RuntimeFile $inputPath ($root+'\over-budget.csv') 134217728} 'file-byte-budget'
    Require-Runtime (-not [IO.File]::Exists($root+'\over-budget.csv')) 'budget-created-output'
    $fact=Copy-RuntimeFile $inputPath $outputPath 1073741824
    Require-Runtime ($fact.bytes -eq 134217745) 'copy-length'
    $h=[Security.Cryptography.SHA256]::Create()
    try{
        foreach($path in @($inputPath,$outputPath)){
            $file=[IO.File]::OpenRead($path)
            try{$pin=[BitConverter]::ToString($h.ComputeHash($file)).Replace('-','').ToLowerInvariant()}finally{$file.Dispose()}
            Require-Runtime ($pin -ceq $fact.sha256) 'independent-copy-hash'
        }
    }finally{$h.Dispose()}
    $null=Write-RuntimeJson ($root+'\large-copy-fact.json') $fact
}
Check 'stream-copy-writer-lock-existing-target-and-budgets' {
    $path=$root+'\source.dat';$target=$root+'\locked-copy.dat'
    $writer=[IO.File]::Open($path,'Open','Write','ReadWrite')
    try{
        $failed=$false;try{$null=Copy-RuntimeFile $path $target 20}catch{$failed=$true}
        Require-Runtime ($failed -and -not [IO.File]::Exists($target)) 'writer-not-excluded'
    }finally{$writer.Dispose()}
    $before=Hash-Runtime (Read-RuntimeBytes $path)
    Reject {Copy-RuntimeFile $path $path 20} 'copy-paths-must-differ'
    Reject {Copy-RuntimeFile $path $target 0} 'copy-byte-budget'
    Reject {Copy-RuntimeFile $path $target 1073741825} 'copy-byte-budget'
    $null=Copy-RuntimeFile $path $target 20
    $failed=$false;try{$null=Copy-RuntimeFile $path $target 20}catch{$failed=$true}
    Require-Runtime ($failed -and (Hash-Runtime (Read-RuntimeBytes $path)) -ceq $before -and (Hash-Runtime (Read-RuntimeBytes $target)) -ceq $before) 'existing-stream-copy-modified'
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
Check 'v2-first-sequence-and-legacy-isolation' {
    $r=[pscustomobject]@{schema='sfl-health-runtime-close-request-v2';candidate_commit='acaf77d95101a050f4d3ecd76125d3502036f5a7';logger_service_instance_id='c7bad677-3827-4da6-b4a0-920f9e5629e6';csv_name='Factory_Integrated_Log_v2_20261016_000000.csv';config_sha256=('a'*64);csv_first_sample_seq=18573}
    Assert-RuntimeRequest $r
    foreach($bad in @($null,$true,0,-1,1.5,'18573')){
        $r.csv_first_sample_seq=$bad;Reject {Assert-RuntimeRequest $r} 'request-first-sequence'
    }
    $r.csv_first_sample_seq=18573;$r.schema='sfl-health-runtime-close-request-v1'
    Reject {Assert-RuntimeRequest $r} 'legacy-first-sequence-not-configurable'
    $r.schema='sfl-health-runtime-close-request-v2';$r.PSObject.Properties.Remove('csv_first_sample_seq')
    Reject {Assert-RuntimeRequest $r} 'request-first-sequence'
}
Check 'real-controller-development-host-denied' {
    Require-Runtime ($env:COMPUTERNAME -cne 'DESKTOP-CIIT7LK') 'test-must-run-on-development-host'
    $native=[Environment]::SystemDirectory+'\WindowsPowerShell\v1.0\powershell.exe'
    $output=& $native -NoProfile -NonInteractive -File $source -RequestPath ($root+'\missing.json') -ExpectedRequestSha256 ('a'*64)
    Require-Runtime ($LASTEXITCODE -eq 1 -and ($output -join "`n") -match 'server-operator-admin-required') 'controller-host-guard'
}
Check 'history-v3-exact-build-and-legacy-isolation' {
    $r=[pscustomobject]@{schema='sfl-health-runtime-close-request-v3';candidate_commit='0732c8e810be3c46096b397812f53a9767354229';logger_service_instance_id='c7bad677-3827-4da6-b4a0-920f9e5629e6';csv_name='Factory_Integrated_Log_v2_20261016_180000.csv';config_sha256=('a'*64);csv_first_sample_seq=1}
    Assert-RuntimeRequest $r
    Require-Runtime ((Get-RuntimeRequestVersion $r) -ceq '1.0.30') 'history-version'
    foreach($schema in @('sfl-health-runtime-close-request-v1','sfl-health-runtime-close-request-v2')){
        $r.schema=$schema;Reject {Assert-RuntimeRequest $r} 'request-contract'
    }
    $r.schema='sfl-health-runtime-close-request-v3'
    foreach($build in @('acaf77d95101a050f4d3ecd76125d3502036f5a7','4cc7393e1bafbf90a329726aed9470fe0daacb21','wrong')){
        $r.candidate_commit=$build;Reject {Assert-RuntimeRequest $r} 'request-contract'
    }
    $r.candidate_commit='0732c8e810be3c46096b397812f53a9767354229'
    foreach($bad in @($null,$true,0,-1,1.5,'1')){
        $r.csv_first_sample_seq=$bad;Reject {Assert-RuntimeRequest $r} 'request-first-sequence'
    }
}
Check 'final-v4-exact-build-and-same-version-isolation' {
    $r=[pscustomobject]@{schema='sfl-health-runtime-close-request-v4';candidate_commit='685dde946e8ce2e34c65c6dde05be16e342f068e';logger_service_instance_id='c7bad677-3827-4da6-b4a0-920f9e5629e6';csv_name='Factory_Integrated_Log_v2_20261019_120000.csv';config_sha256=('a'*64);csv_first_sample_seq=18573}
    Assert-RuntimeRequest $r
    Require-Runtime ((Get-RuntimeRequestVersion $r) -ceq '1.0.30') 'final-version'
    $r.candidate_commit='0732c8e810be3c46096b397812f53a9767354229';Reject {Assert-RuntimeRequest $r} 'request-contract'
    $r.candidate_commit='685dde946e8ce2e34c65c6dde05be16e342f068e'
    foreach($schema in @('sfl-health-runtime-close-request-v1','sfl-health-runtime-close-request-v2','sfl-health-runtime-close-request-v3')){
        $r.schema=$schema;Reject {Assert-RuntimeRequest $r} 'request-contract'
    }
    $r.schema='sfl-health-runtime-close-request-v4'
    foreach($bad in @($null,$true,0,-1,1.5,'18573')){
        $r.csv_first_sample_seq=$bad;Reject {Assert-RuntimeRequest $r} 'request-first-sequence'
    }
}
Check 'renderer-fix-v5-exact-build-and-same-version-isolation' {
    $r=[pscustomobject]@{schema='sfl-health-runtime-close-request-v5';candidate_commit='8de064317d6de42d321afb8395f7a30a1f31cd55';logger_service_instance_id='c7bad677-3827-4da6-b4a0-920f9e5629e6';csv_name='Factory_Integrated_Log_v2_20261019_120000.csv';config_sha256=('a'*64);csv_first_sample_seq=18573}
    Assert-RuntimeRequest $r
    Require-Runtime ((Get-RuntimeRequestVersion $r) -ceq '1.0.30') 'renderer-fix-version'
    $r.candidate_commit='0732c8e810be3c46096b397812f53a9767354229';Reject {Assert-RuntimeRequest $r} 'request-contract'
    $r.candidate_commit='8de064317d6de42d321afb8395f7a30a1f31cd55'
    foreach($schema in @('sfl-health-runtime-close-request-v1','sfl-health-runtime-close-request-v2','sfl-health-runtime-close-request-v3','sfl-health-runtime-close-request-v4')){
        $r.schema=$schema;Reject {Assert-RuntimeRequest $r} 'request-contract'
    }
    $r.schema='sfl-health-runtime-close-request-v5'
    foreach($bad in @($null,$true,0,-1,1.5,'18573')){
        $r.csv_first_sample_seq=$bad;Reject {Assert-RuntimeRequest $r} 'request-first-sequence'
    }
}
Check 'identity-only-result-preserves-running-and-unverified-exit-scope' {
    $identityRoot=Join-Path $root 'identity-only';$null=New-Item -ItemType Directory -Path $identityRoot
    $files=[ordered]@{'config.ini'=@{bytes=7;sha256=('c'*64)}}
    $fact=Write-RuntimeIdentityResult $identityRoot ('b'*64) $files
    $bytes=Read-RuntimeBytes ($identityRoot+'\result.json');$value=Read-RuntimeJson $bytes
    Require-Runtime ((Hash-Runtime $bytes) -ceq $fact.sha256) 'identity-result-pin'
    Require-Runtime ($value.status -ceq 'RUNNING_IDENTITY_CAPTURED_REQUIRES_REVIEW' -and $value.request_sha256 -ceq ('b'*64) -and $value.files.'config.ini'.bytes -eq 7) 'identity-result-binding'
    Require-Runtime (-not $value.application_shutdown_performed -and -not $value.actual_process_exit_observed -and -not $value.configuration_changed -and -not $value.full_backup_created -and -not $value.promotion_allowed -and $value.release_gate -ceq 'HOLD') 'identity-scope-escalated'
}
$null=Write-RuntimeJson ($root+'\summary.json') ([ordered]@{status='PASS';scope='LOCAL_NATIVE_AND_CONTRACT_CHECKS_NOT_SERVER_LIFECYCLE';checks=$checks;server_execution=$false;release_gate='HOLD'})
Write-Output ('TEST_RESULT_PATH='+$root)
Write-Output ('CHECKS='+$checks.Count)
