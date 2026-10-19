[CmdletBinding()]
param([string]$RequestPath='',[string]$ExpectedRequestSha256='',[switch]$LibraryOnly)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
# Reuse the already exercised path, ACL, JSON, cold-state and hash functions.
$library=[IO.File]::Open((Join-Path $PSScriptRoot 'observe-health-runtime-close.ps1'),'Open','Read','Read')
try{
    $hasher=[Security.Cryptography.SHA256]::Create()
    try{$pin=[BitConverter]::ToString($hasher.ComputeHash($library)).Replace('-','').ToLowerInvariant()}finally{$hasher.Dispose()}
    if($pin -cne 'bee27ed50771fe231b4f197ab4f1de9eb6a1d94c1daab688767669a3653f7b3d'){throw 'runtime-library-pin'}
    $library.Position=0;$reader=[IO.StreamReader]::new($library,[Text.UTF8Encoding]::new($false,$true),$true,4096,$true)
    try{$source=$reader.ReadToEnd()}finally{$reader.Dispose()}
    $tokens=$null;$errors=$null;$ast=[Management.Automation.Language.Parser]::ParseInput($source,[ref]$tokens,[ref]$errors)
    if($errors.Count){throw 'runtime-library-parse'}
    foreach($name in @('Require-Runtime','Plain-Runtime','Hash-Runtime','Read-RuntimeBytes','Write-RuntimeBytes','Write-RuntimeJson','Read-RuntimeJson','Observe-Runtime','Assert-RuntimeCold','New-RuntimeResult')){
        $functions=@($ast.FindAll({param($node)$node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq $name},$false))
        if($functions.Count -ne 1){throw 'runtime-library-function'}
        . ([scriptblock]::Create($functions[0].Extent.Text))
    }
}finally{$library.Dispose()}

function Get-CaptureHash([IO.Stream]$Stream){
    $h=[Security.Cryptography.SHA256]::Create()
    try{$Stream.Position=0;return [BitConverter]::ToString($h.ComputeHash($Stream)).Replace('-','').ToLowerInvariant()}finally{$h.Dispose()}
}
function Read-CaptureJson([IO.Stream]$Stream){
    Require-Runtime ($Stream.Length -gt 0 -and $Stream.Length -le 4MB) 'capture-json-budget'
    $Stream.Position=0;$reader=[IO.StreamReader]::new($Stream,[Text.UTF8Encoding]::new($false,$true),$true,4096,$true)
    try{return ($reader.ReadToEnd()|ConvertFrom-Json)}finally{$reader.Dispose()}
}
function Assert-CaptureRequest($Request){
    Require-Runtime (($Request.schema -ceq 'sfl-closed-fact-capture-request-v1' -and $Request.candidate_commit -ceq '0732c8e810be3c46096b397812f53a9767354229') -or
        ($Request.schema -ceq 'sfl-closed-fact-capture-request-v2' -and $Request.candidate_commit -ceq '685dde946e8ce2e34c65c6dde05be16e342f068e') -or
        ($Request.schema -ceq 'sfl-closed-fact-capture-request-v3' -and $Request.candidate_commit -ceq '8de064317d6de42d321afb8395f7a30a1f31cd55')) 'capture-request-contract'
    Require-Runtime ($Request.csv_name -cmatch '^Factory_Integrated_Log_v2_[0-9]{8}_[0-9]{6}\.csv$' -and $Request.logger_service_instance_id -cmatch '^[a-f0-9-]{36}$') 'capture-request-generation'
    Require-Runtime (($Request.minimum_sample_seq -is [int] -or $Request.minimum_sample_seq -is [long]) -and $Request.minimum_sample_seq -gt 0) 'capture-minimum-sequence'
    foreach($name in @('config_sha256','close_result_sha256')){Require-Runtime ($Request.$name -cmatch '^[a-f0-9]{64}$') 'capture-request-pin'}
    Require-Runtime ($Request.close_result_path -cmatch '^C:\\Users\\user\\Desktop\\SmartFactory\\R[0-9a-f]{12}\\result\.json$') 'capture-close-result-path'
}
function Get-CaptureSelection($Metadata,$Request,[string]$DataRoot){
    Require-Runtime ($Metadata.schema_metadata.git_commit -ceq $Request.candidate_commit -and $Metadata.schema_metadata.logger_service_instance_id -ceq $Request.logger_service_instance_id) 'capture-metadata-generation'
    $close=$Metadata.csv_closeout
    Require-Runtime ($close.finalized -is [bool] -and $close.finalized -and $close.closeout_reason -ceq 'shutdown' -and $close.csv_file_name -ceq $Request.csv_name -and $close.logger_service_instance_id -ceq $Request.logger_service_instance_id) 'capture-metadata-not-finalized'
    Require-Runtime (($close.final_persisted_sample_seq -is [int] -or $close.final_persisted_sample_seq -is [long]) -and $close.final_persisted_sample_seq -ge $Request.minimum_sample_seq) 'capture-closeout-sequence'
    Require-Runtime ($Metadata.schema_metadata.v1_csv_enabled -is [bool] -and -not $Metadata.schema_metadata.v1_csv_enabled) 'capture-v1-not-disabled'
    Require-Runtime (-not [IO.File]::Exists((Join-Path $DataRoot $Request.csv_name.Replace('_v2_','_')))) 'capture-unbound-v1'
    $specs=[Collections.Generic.List[object]]::new()
    $specs.Add([ordered]@{role='v2';name=$Request.csv_name;limit=1073741824L;expected_sha256=$null})
    $specs.Add([ordered]@{role='metadata';name=$Request.csv_name.Replace('.csv','.metadata.json');limit=4194304L;expected_sha256=$null})
    $specs.Add([ordered]@{role='observation';name='spot_observation_fact.csv';limit=2147483648L;expected_sha256=$Metadata.spot_observation_fact_manifest.sha256})
    $specs.Add([ordered]@{role='image';name='spot_image_fact.csv';limit=4294967296L;expected_sha256=$null})
    $specs.Add([ordered]@{role='image_final';name='spot_image_fact_manifest.final.json';limit=4194304L;expected_sha256=$null})
    Require-Runtime ($specs[2].expected_sha256 -cmatch '^[a-f0-9]{64}$') 'capture-observation-manifest-pin'
    $absent=[Collections.Generic.List[string]]::new()
    $sections=@(
        @('changeover','changeover_candidate_resolution_fact_manifest','fact_path','sha256'),
        @('phase','process_phase_event_fact_manifest','fact_path','sha256'),
        @('linkage','spot_image_linkage_fact_manifest','fact_path','sha256'),
        @('linkage_report','spot_image_linkage_fact_manifest','report_path','report_sha256'))
    foreach($entry in $sections){
        $property=$Metadata.PSObject.Properties[$entry[1]]
        if($null -eq $property){continue}
        $manifest=$property.Value;$path=Plain-Runtime ([string]$manifest.($entry[2]))
        Require-Runtime ([IO.Path]::GetDirectoryName($path) -ieq (Plain-Runtime $DataRoot)) 'capture-optional-path'
        $name=[IO.Path]::GetFileName($path)
        Require-Runtime ($name -cmatch '^[A-Za-z0-9_.-]+\.(csv|json)$' -and $name -notmatch '\.\.') 'capture-optional-name'
        if($entry[0] -cin @('changeover','phase') -and $manifest.row_count -eq 0 -and $null -eq $manifest.sha256){
            Require-Runtime (-not [IO.File]::Exists($path) -and -not [IO.Directory]::Exists($path)) 'capture-optional-absence'
            $absent.Add($name);continue
        }
        $expected=[string]$manifest.($entry[3]);Require-Runtime ($expected -cmatch '^[a-f0-9]{64}$') 'capture-optional-pin'
        $specs.Add([ordered]@{role=$entry[0];name=$name;limit=2147483648L;expected_sha256=$expected})
    }
    Require-Runtime (@($specs|ForEach-Object{[string]$_['name']}|Group-Object|Where-Object Count -gt 1).Count -eq 0) 'capture-role-alias'
    return [pscustomobject]@{specs=@($specs);absent=@($absent)}
}
function Open-CaptureInput([string]$Path,[long]$Limit){
    Require-Runtime ($Limit -gt 0 -and $Limit -le 4294967296L) 'capture-input-limit'
    $pathValue=Plain-Runtime $Path
    $streams=@(Get-Item -LiteralPath $pathValue -Stream * -ErrorAction Stop)
    Require-Runtime ($streams.Count -eq 1 -and $streams[0].Stream -ceq ':$DATA') 'capture-named-stream-unhandled'
    $stream=[IO.File]::Open($pathValue,'Open','Read','Read')
    try{Require-Runtime ($stream.Length -gt 0 -and $stream.Length -le $Limit) 'capture-input-budget';return $stream}
    catch{$stream.Dispose();throw}
}
function Copy-CaptureStream([IO.Stream]$InputStream,[string]$Destination,[long]$Limit){
    Require-Runtime ($Limit -gt 0 -and $Limit -le 4294967296L -and $InputStream.Length -gt 0 -and $InputStream.Length -le $Limit) 'capture-copy-budget'
    $destinationPath=Plain-Runtime $Destination;$outputStream=$null;$h=$null
    try{
        $outputStream=[IO.File]::Open($destinationPath,'CreateNew','Write','None')
        $h=[Security.Cryptography.SHA256]::Create();$InputStream.Position=0
        $length=$InputStream.Length;$count=0L;$buffer=New-Object byte[] 1048576;$clock=[Diagnostics.Stopwatch]::StartNew()
        while(($read=$InputStream.Read($buffer,0,$buffer.Length)) -gt 0){
            Require-Runtime ($clock.ElapsedMilliseconds -le 900000) 'capture-copy-time-budget'
            $count+=$read;Require-Runtime ($count -le $length) 'capture-copy-length'
            $outputStream.Write($buffer,0,$read);$null=$h.TransformBlock($buffer,0,$read,$null,0)
        }
        $null=$h.TransformFinalBlock([byte[]]@(),0,0);$outputStream.Flush($true)
        Require-Runtime ($count -eq $length -and $InputStream.Length -eq $length) 'capture-copy-length'
        $sha=[BitConverter]::ToString($h.Hash).Replace('-','').ToLowerInvariant()
        $outputStream.Dispose();$outputStream=$null
        $verify=[IO.File]::Open($destinationPath,'Open','Read','Read')
        try{Require-Runtime ($verify.Length -eq $length -and (Get-CaptureHash $verify) -ceq $sha) 'capture-destination-verification'}finally{$verify.Dispose()}
        Require-Runtime ($clock.ElapsedMilliseconds -le 900000) 'capture-copy-time-budget'
        return [ordered]@{bytes=$count;sha256=$sha}
    }finally{if($h){$h.Dispose()};if($outputStream){$outputStream.Dispose()}}
}
function Copy-CaptureInputs($Selection,$Opened,[IO.Stream]$Config,$CloseResult,$ImageFinal,[string]$OutputRoot){
    $copied=[ordered]@{}
    $copied['config.ini']=Copy-CaptureStream $Config (Join-Path $OutputRoot 'config.ini') 4MB
    Require-Runtime ($copied['config.ini'].sha256 -ceq $CloseResult.files.'config.ini'.sha256 -and $copied['config.ini'].bytes -eq $CloseResult.files.'config.ini'.bytes) 'capture-close-copy:config'
    foreach($spec in $Selection.specs){
        $entry=Copy-CaptureStream $Opened[$spec.role] (Join-Path $OutputRoot $spec.name) $spec.limit
        $copied[$spec.name]=$entry
        if($null -ne $spec.expected_sha256){Require-Runtime ($entry.sha256 -ceq $spec.expected_sha256) ('capture-ledger-hash:'+ $spec.role)}
        if($spec.role -ceq 'image'){Require-Runtime ($entry.sha256 -ceq $ImageFinal.sha256) 'capture-image-final-hash'}
        if($spec.role -cin @('v2','metadata')){Require-Runtime ($entry.sha256 -ceq $CloseResult.files.($spec.name).sha256 -and $entry.bytes -eq $CloseResult.files.($spec.name).bytes) ('capture-close-copy:'+ $spec.role)}
    }
    return $copied
}
if($LibraryOnly){return}
$held=[Collections.Generic.List[IDisposable]]::new();$resultRoot=$null;$files=[ordered]@{};$phase='preflight'
try{
    $native=[Environment]::SystemDirectory+'\WindowsPowerShell\v1.0\powershell.exe'
    $sid='S-1-5-21-2762931165-1280404403-2847611662-1001';$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
    Require-Runtime ($env:COMPUTERNAME -ceq 'DESKTOP-CIIT7LK' -and $identity.User.Value -ceq $sid -and ([Security.Principal.WindowsPrincipal]::new($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) 'capture-server-admin-required'
    Require-Runtime ([Environment]::Is64BitProcess -and $PSVersionTable.PSEdition -ceq 'Desktop' -and $PSVersionTable.PSVersion.ToString() -like '5.1.*' -and [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName -ieq $native) 'capture-native-ps51-required'
    $env:PSModulePath=[IO.Path]::GetDirectoryName($native)+'\Modules'
    $requestBytes=Read-RuntimeBytes $RequestPath
    Require-Runtime ($ExpectedRequestSha256 -cmatch '^[a-f0-9]{64}$' -and (Hash-Runtime $requestBytes) -ceq $ExpectedRequestSha256) 'capture-request-hash'
    $request=Read-RuntimeJson $requestBytes;Assert-CaptureRequest $request
    Assert-RuntimeCold (Observe-Runtime)
    $closeBytes=Read-RuntimeBytes $request.close_result_path
    Require-Runtime ((Hash-Runtime $closeBytes) -ceq $request.close_result_sha256) 'capture-close-result-pin'
    $closeResult=Read-RuntimeJson $closeBytes
    Require-Runtime ($closeResult.status -ceq 'CLOSED_RUNTIME_CAPTURED_REQUIRES_REVIEW' -and $closeResult.forced_termination -is [bool] -and -not $closeResult.forced_termination -and $closeResult.configuration_changed -is [bool] -and -not $closeResult.configuration_changed) 'capture-close-result-status'
    $data='C:\Users\user\AppData\Roaming\SmartFactoryLogger\logs\test_data';$configPath='C:\Users\user\AppData\Roaming\SmartFactoryLogger\config.ini'
    $config=Open-CaptureInput $configPath 4MB;$held.Add($config)
    Require-Runtime ((Get-CaptureHash $config) -ceq $request.config_sha256 -and $closeResult.files.'config.ini'.sha256 -ceq $request.config_sha256) 'capture-config-pin'
    $metadataName=$request.csv_name.Replace('.csv','.metadata.json');$metadataStream=Open-CaptureInput (Join-Path $data $metadataName) 4MB;$held.Add($metadataStream)
    Require-Runtime ((Get-CaptureHash $metadataStream) -ceq $closeResult.files.$metadataName.sha256 -and $metadataStream.Length -eq $closeResult.files.$metadataName.bytes) 'capture-metadata-pin'
    $selection=Get-CaptureSelection (Read-CaptureJson $metadataStream) $request $data
    $opened=@{};$total=$config.Length
    foreach($spec in $selection.specs){
        $s=if($spec.role -ceq 'metadata'){$metadataStream}else{Open-CaptureInput (Join-Path $data $spec.name) $spec.limit}
        if($spec.role -cne 'metadata'){$held.Add($s)}
        $opened[$spec.role]=$s;$total+=$s.Length
    }
    $imageFinal=Read-CaptureJson $opened['image_final']
    Require-Runtime ((Plain-Runtime $imageFinal.fact_path) -ieq (Plain-Runtime (Join-Path $data 'spot_image_fact.csv')) -and $imageFinal.sha256 -cmatch '^[a-f0-9]{64}$') 'capture-image-final-binding'
    $factory=Plain-Runtime ([Environment]::GetFolderPath('Desktop')+'\SmartFactory')
    Require-Runtime ($factory -ieq 'C:\Users\user\Desktop\SmartFactory') 'capture-desktop-root'
    Require-Runtime ([IO.DriveInfo]::new([IO.Path]::GetPathRoot($factory)).AvailableFreeSpace -ge $total+64MB) 'capture-space-budget'
    Assert-RuntimeCold (Observe-Runtime)
    $resultRoot=New-RuntimeResult $factory $sid;$phase='selected-copy'
    $files['request.json']=Write-RuntimeBytes ($resultRoot+'\request.json') $requestBytes
    $copied=Copy-CaptureInputs $selection $opened $config $closeResult $imageFinal $resultRoot
    foreach($name in $copied.Keys){$files[$name]=$copied[$name]}
    foreach($name in $selection.absent){Require-Runtime (-not [IO.File]::Exists((Join-Path $data $name))) 'capture-optional-appeared'}
    foreach($path in @($configPath)+@($selection.specs|ForEach-Object{Join-Path $data $_.name})){
        $streams=@(Get-Item -LiteralPath (Plain-Runtime $path) -Stream * -ErrorAction Stop)
        Require-Runtime ($streams.Count -eq 1 -and $streams[0].Stream -ceq ':$DATA') 'capture-named-stream-appeared'
    }
    Assert-RuntimeCold (Observe-Runtime)
    $receipt=Write-RuntimeJson ($resultRoot+'\result.json') ([ordered]@{schema='sfl-closed-fact-capture-result-v1';status='CLOSED_SELECTED_INPUTS_CAPTURED_REQUIRES_QA';captured_utc=[DateTimeOffset]::UtcNow.ToString('o');source_root=$data;configuration_source=$configPath;request_sha256=$ExpectedRequestSha256;close_result_sha256=$request.close_result_sha256;files=$files;roles=$selection.specs;absent_optional_inputs=$selection.absent;input_locks_held_through_copy=$true;default_streams_only=$true;selected_named_streams=0;source_content_changed=$false;full_backup_created=$false;actual_content_qa='NOT_EVALUATED';full_data_gate='NOT_EVALUATED';release_gate='HOLD';promotion_allowed=$false})
    Write-Host ('RESULT_PATH='+$resultRoot);Write-Host ('RESULT_SHA256='+$receipt.sha256);exit 0
}catch{
    if($resultRoot){$receipt=Write-RuntimeJson ($resultRoot+'\hold.json') ([ordered]@{status='HOLD';phase=$phase;error=$_.Exception.Message;files=$files;partial_files_may_exist=$true;source_content_changed=$false;full_backup_created=$false;release_gate='HOLD'});Write-Host ('RESULT_PATH='+$resultRoot);Write-Host ('HOLD_SHA256='+$receipt.sha256)}
    Write-Host ('CAPTURE_HOLD='+$_.Exception.Message);exit 1
}finally{foreach($s in $held){$s.Dispose()}}
