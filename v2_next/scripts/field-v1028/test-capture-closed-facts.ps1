param([Parameter(Mandatory=$true)][string]$OutputParent)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$testSource=Join-Path $PSScriptRoot 'capture-closed-facts.ps1'
. $testSource -LibraryOnly
$root=Join-Path $OutputParent ('closed-fact-tests-'+[Guid]::NewGuid().ToString('N'))
$null=New-Item -ItemType Directory -Path $root
$checks=[Collections.Generic.List[object]]::new()
function Check([string]$Name,[scriptblock]$Action){Write-Host ('CHECK='+$Name);& $Action;$checks.Add([ordered]@{name=$Name;status='PASS'})}
function Reject([scriptblock]$Action,[string]$Reason){
    try{& $Action;throw 'expected-rejection-missing'}catch{if($_.Exception.Message -cne $Reason){throw}}
}
function Clone($Value){return ($Value|ConvertTo-Json -Depth 15|ConvertFrom-Json)}
$request=[pscustomobject]@{schema='sfl-closed-fact-capture-request-v1';candidate_commit='0732c8e810be3c46096b397812f53a9767354229';csv_name='Factory_Integrated_Log_v2_20261016_195021.csv';logger_service_instance_id='ee648ff0-d3a9-4ab9-bb7e-015ff4457cb4';minimum_sample_seq=100;config_sha256=('a'*64);close_result_sha256=('b'*64);close_result_path='C:\Users\user\Desktop\SmartFactory\R0123456789ab\result.json'}
$metadata=[pscustomobject]@{schema_metadata=[pscustomobject]@{git_commit=$request.candidate_commit;logger_service_instance_id=$request.logger_service_instance_id;v1_csv_enabled=$false};csv_closeout=[pscustomobject]@{finalized=$true;closeout_reason='shutdown';csv_file_name=$request.csv_name;logger_service_instance_id=$request.logger_service_instance_id;final_persisted_sample_seq=110};spot_observation_fact_manifest=[pscustomobject]@{sha256=('c'*64)};changeover_candidate_resolution_fact_manifest=[pscustomobject]@{fact_path=($root+'\changeover.csv');row_count=0;sha256=$null}}
Check 'native-powershell-and-parser' {
    Require-Runtime ([Environment]::Is64BitProcess -and $PSVersionTable.PSVersion.Major -eq 5 -and $PSVersionTable.PSVersion.Minor -eq 1) 'test-native-ps51-required'
    $tokens=$null;$errors=$null;$null=[Management.Automation.Language.Parser]::ParseFile($testSource,[ref]$tokens,[ref]$errors)
    Require-Runtime ($errors.Count -eq 0) ('capture-parser:'+($errors|Out-String))
}
Check 'request-generation-and-source-boundary' {
    Assert-CaptureRequest $request
    foreach($change in @(@('candidate_commit',('0'*40),'capture-request-contract'),@('minimum_sample_seq',0,'capture-minimum-sequence'),@('minimum_sample_seq','100','capture-minimum-sequence'),@('close_result_path','C:\Users\user\Desktop\SmartFactory\R0123456789ab\..\result.json','capture-close-result-path'))){
        $copy=Clone $request;$copy.($change[0])=$change[1];Reject {Assert-CaptureRequest $copy} $change[2]
    }
}
Check 'selection-preserves-current-full-ledgers-and-role-budgets' {
    $s=Get-CaptureSelection $metadata $request $root
    Require-Runtime ($s.specs.Count -eq 5 -and $s.absent.Count -eq 1 -and $s.absent[0] -ceq 'changeover.csv') 'capture-selection-count'
    Require-Runtime ($s.specs[2].limit -eq 2147483648L -and $s.specs[3].limit -eq 4294967296L -and $s.specs[3].name -ceq 'spot_image_fact.csv') 'capture-role-byte-limits'
}
Check 'wrong-generation-finalization-sequence-and-v1-rejected' {
    foreach($change in @(@('schema_metadata','git_commit',('0'*40),'capture-metadata-generation'),@('csv_closeout','finalized','True','capture-metadata-not-finalized'),@('csv_closeout','finalized',$false,'capture-metadata-not-finalized'),@('csv_closeout','final_persisted_sample_seq',99,'capture-closeout-sequence'),@('schema_metadata','v1_csv_enabled','False','capture-v1-not-disabled'))){
        $copy=Clone $metadata;$copy.($change[0]).($change[1])=$change[2];Reject {Get-CaptureSelection $copy $request $root} $change[3]
    }
}
Check 'optional-required-input-included-and-escape-rejected' {
    $copy=Clone $metadata;$copy.changeover_candidate_resolution_fact_manifest.row_count=1;$copy.changeover_candidate_resolution_fact_manifest.sha256='d'*64
    $s=Get-CaptureSelection $copy $request $root
    Require-Runtime ($s.specs.Count -eq 6 -and $s.specs[5].role -ceq 'changeover' -and $s.specs[5].expected_sha256 -ceq ('d'*64)) 'capture-required-optional-not-selected'
    $copy.changeover_candidate_resolution_fact_manifest.fact_path=([IO.Path]::GetDirectoryName($root)+'\outside.csv')
    Reject {Get-CaptureSelection $copy $request $root} 'capture-optional-path'
}
Check 'optional-alias-and-unbound-file-rejected' {
    $copy=Clone $metadata;$copy.changeover_candidate_resolution_fact_manifest.row_count=1;$copy.changeover_candidate_resolution_fact_manifest.sha256='d'*64
    $copy.changeover_candidate_resolution_fact_manifest.fact_path=$root+'\spot_image_fact.csv'
    Reject {Get-CaptureSelection $copy $request $root} 'capture-role-alias'
    [IO.File]::WriteAllText(($root+'\changeover.csv'),'unbound-fixture')
    Reject {Get-CaptureSelection $metadata $request $root} 'capture-optional-absence'
}
Check 'actual-stream-copy-and-source-write-exclusion' {
    $inputPath=$root+'\input.csv';$bytes=New-Object byte[] 3145745
    for($i=0;$i -lt $bytes.Length;$i+=7919){$bytes[$i]=[byte]($i%251)}
    [IO.File]::WriteAllBytes($inputPath,$bytes);$expected=Hash-Runtime $bytes
    $s=Open-CaptureInput $inputPath 4GB
    try{
        $blocked=$false;try{$w=[IO.File]::Open($inputPath,'Open','Write','ReadWrite');$w.Dispose()}catch{$blocked=$true}
        Require-Runtime $blocked 'capture-source-write-not-blocked'
        $result=Copy-CaptureStream $s ($root+'\copy.csv') 4GB
        Require-Runtime ($result.bytes -eq $bytes.Length -and $result.sha256 -ceq $expected -and (Get-CaptureHash $s) -ceq $expected) 'capture-copy-content'
        $refused=$false;try{$null=Copy-CaptureStream $s ($root+'\copy.csv') 4GB}catch{$refused=$true}
        Require-Runtime ($refused -and (Hash-Runtime (Read-RuntimeBytes ($root+'\copy.csv'))) -ceq $expected) 'capture-copy-overwritten'
        Reject {Copy-CaptureStream $s ($root+'\too-small.csv') 2} 'capture-copy-budget'
        Require-Runtime (-not [IO.File]::Exists($root+'\too-small.csv')) 'capture-budget-created-output'
    }finally{$s.Dispose()}
}
Check 'open-writer-and-named-stream-rejected' {
    $path=$root+'\input.csv';$w=[IO.File]::Open($path,'Open','Write','ReadWrite')
    try{$blocked=$false;try{$s=Open-CaptureInput $path 4GB;$s.Dispose()}catch{$blocked=$true};Require-Runtime $blocked 'capture-open-writer-accepted'}finally{$w.Dispose()}
    Set-Content -LiteralPath $path -Stream 'fixture' -Value 'named-stream-fixture' -NoNewline
    Reject {Open-CaptureInput $path 4GB} 'capture-named-stream-unhandled'
}
Check 'complete-selected-copy-and-all-destination-pins' {
    $data=$root+'\complete-inputs';$null=New-Item -ItemType Directory -Path $data
    $meta=Clone $metadata;$meta.PSObject.Properties.Remove('changeover_candidate_resolution_fact_manifest')
    $obsBytes=[Text.Encoding]::UTF8.GetBytes("observation_id`n1`n");$meta.spot_observation_fact_manifest.sha256=Hash-Runtime $obsBytes
    $selection=Get-CaptureSelection $meta $request $data
    $opened=@{};$expected=[pscustomobject]@{files=[pscustomobject]@{}};$all=[Collections.Generic.List[IDisposable]]::new()
    try{
        foreach($spec in $selection.specs){
            $bytes=if($spec.role -ceq 'observation'){$obsBytes}else{[Text.Encoding]::UTF8.GetBytes('fixture-'+$spec.role)}
            $path=Join-Path $data $spec.name;[IO.File]::WriteAllBytes($path,$bytes)
            $s=Open-CaptureInput $path $spec.limit;$all.Add($s);$opened[$spec.role]=$s
            $expected.files|Add-Member NoteProperty $spec.name ([pscustomobject]@{bytes=$bytes.Length;sha256=(Hash-Runtime $bytes)})
        }
        $configPath=$data+'\config.ini';[IO.File]::WriteAllText($configPath,'fixture-config')
        $config=Open-CaptureInput $configPath 4MB;$all.Add($config)
        $expected.files|Add-Member NoteProperty 'config.ini' ([pscustomobject]@{bytes=$config.Length;sha256=(Get-CaptureHash $config)})
        $final=[pscustomobject]@{sha256=(Get-CaptureHash $opened['image'])}
        $out=$root+'\complete-output';$null=New-Item -ItemType Directory -Path $out
        $copied=Copy-CaptureInputs $selection $opened $config $expected $final $out
        Require-Runtime ($copied.Count -eq 6) 'complete-copy-count'
        foreach($name in $copied.Keys){
            $s=[IO.File]::OpenRead((Join-Path $out $name))
            try{Require-Runtime ($s.Length -eq $copied[$name].bytes -and (Get-CaptureHash $s) -ceq $expected.files.$name.sha256) 'complete-independent-destination'}finally{$s.Dispose()}
        }
        foreach($scenario in @('observation','image','v2','metadata','config')){
            $badExpected=Clone $expected;$badFinal=Clone $final;$badSelection=Clone $selection
            if($scenario -ceq 'observation'){$badSelection.specs[2].expected_sha256='0'*64;$reason='capture-ledger-hash:observation'}
            elseif($scenario -ceq 'image'){$badFinal.sha256='0'*64;$reason='capture-image-final-hash'}
            else{$name=if($scenario -ceq 'config'){'config.ini'}elseif($scenario -ceq 'v2'){$request.csv_name}else{$request.csv_name.Replace('.csv','.metadata.json')};$badExpected.files.$name.sha256='0'*64;$reason='capture-close-copy:'+$scenario}
            $out=$root+'\rejected-'+$scenario;$null=New-Item -ItemType Directory -Path $out
            Reject {Copy-CaptureInputs $badSelection $opened $config $badExpected $badFinal $out} $reason
        }
    }finally{foreach($s in $all){$s.Dispose()}}
}
Check 'real-entry-rejects-development-host-before-source-reads' {
    Require-Runtime ($env:COMPUTERNAME -cne 'DESKTOP-CIIT7LK') 'test-development-host-required'
    $native=[Environment]::SystemDirectory+'\WindowsPowerShell\v1.0\powershell.exe'
    $info=[Diagnostics.ProcessStartInfo]::new($native,('-NoProfile -NonInteractive -File "'+$testSource+'" -RequestPath "'+$root+'\does-not-exist.json" -ExpectedRequestSha256 '+('a'*64)))
    $info.UseShellExecute=$false;$info.CreateNoWindow=$true;$info.WindowStyle='Hidden';$info.RedirectStandardOutput=$true;$info.RedirectStandardError=$true
    $child=[Diagnostics.Process]::Start($info)
    try{
        $stdout=$child.StandardOutput.ReadToEnd();$stderr=$child.StandardError.ReadToEnd();$child.WaitForExit()
        Require-Runtime ($child.ExitCode -eq 1 -and $stdout.Trim() -ceq 'CAPTURE_HOLD=capture-server-admin-required' -and $stderr -ceq '') 'capture-real-entry-guard'
    }finally{$child.Dispose()}
}
$receipt=Write-RuntimeJson ($root+'\summary.json') ([ordered]@{status='PASS';scope='LOCAL_SYNTHETIC_SELECTION_AND_COPY_ONLY';checks=@($checks);server_executed=$false;release_gate='HOLD'})
Write-Host ('RESULT_PATH='+$root);Write-Host ('RESULT_SHA256='+$receipt.sha256);Write-Host ('CHECK_COUNT='+$checks.Count)
