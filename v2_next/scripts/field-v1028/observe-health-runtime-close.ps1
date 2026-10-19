[CmdletBinding()]
param([string]$RequestPath='', [string]$ExpectedRequestSha256='', [switch]$LibraryOnly, [switch]$IdentityOnly)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'

function Require-Runtime([bool]$Value,[string]$Reason) { if(-not $Value){throw $Reason} }
function Plain-Runtime([string]$Path) {
    Require-Runtime ($Path -cmatch '^[A-Za-z]:[\\/]' -and $Path.Substring(2) -notmatch ':' -and $Path -notmatch '[\x00-\x1f]') 'absolute-local-path'
    $full=[IO.Path]::GetFullPath($Path).TrimEnd('\')
    Require-Runtime ($full.Length -gt 3 -and $full.Length -le 240) 'path-budget'
    $node=[IO.FileInfo]::new($full)
    while($null -ne $node){
        Require-Runtime ([int]$node.Attributes -eq -1 -or ($node.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'reparse-path'
        if($node -is [IO.FileInfo]){$node=$node.Directory}else{$node=$node.Parent}
    }
    return $full
}
function Hash-Runtime([byte[]]$Bytes) {
    $h=[Security.Cryptography.SHA256]::Create()
    try{return [BitConverter]::ToString($h.ComputeHash($Bytes)).Replace('-','').ToLowerInvariant()}finally{$h.Dispose()}
}
function Read-RuntimeBytes([string]$Path,[long]$Limit=4194304) {
    $s=[IO.File]::Open((Plain-Runtime $Path),'Open','Read','Read')
    try{
        Require-Runtime ($s.Length -gt 0 -and $s.Length -le $Limit) 'file-byte-budget'
        $m=[IO.MemoryStream]::new()
        try{$s.CopyTo($m);return ,$m.ToArray()}finally{$m.Dispose()}
    }finally{$s.Dispose()}
}
function Write-RuntimeBytes([string]$Path,[byte[]]$Bytes) {
    $s=[IO.File]::Open((Plain-Runtime $Path),'CreateNew','Write','None')
    try{$s.Write($Bytes,0,$Bytes.Length);$s.Flush($true)}finally{$s.Dispose()}
    return [ordered]@{bytes=$Bytes.Length;sha256=(Hash-Runtime $Bytes)}
}
function Copy-RuntimeFile([string]$Source,[string]$Destination,[long]$Limit) {
    Require-Runtime ($Limit -gt 0 -and $Limit -le 1073741824) 'copy-byte-budget'
    $sourcePath=Plain-Runtime $Source;$destinationPath=Plain-Runtime $Destination
    Require-Runtime ($sourcePath -ine $destinationPath) 'copy-paths-must-differ'
    $inputStream=[IO.File]::Open($sourcePath,'Open','Read','Read')
    $outputStream=$null;$hasher=$null
    try{
        $length=$inputStream.Length
        Require-Runtime ($length -gt 0 -and $length -le $Limit) 'file-byte-budget'
        $outputStream=[IO.File]::Open($destinationPath,'CreateNew','Write','None')
        $hasher=[Security.Cryptography.SHA256]::Create()
        $buffer=New-Object byte[] 1048576;$total=0L;$watch=[Diagnostics.Stopwatch]::StartNew()
        while(($count=$inputStream.Read($buffer,0,$buffer.Length)) -gt 0){
            Require-Runtime ($watch.ElapsedMilliseconds -le 300000) 'copy-time-budget'
            $total+=$count;Require-Runtime ($total -le $length) 'copy-length-changed'
            $outputStream.Write($buffer,0,$count)
            $null=$hasher.TransformBlock($buffer,0,$count,$null,0)
        }
        Require-Runtime ($total -eq $length -and $inputStream.Length -eq $length) 'copy-length-changed'
        $null=$hasher.TransformFinalBlock([byte[]]@(),0,0)
        $outputStream.Flush($true)
        Require-Runtime ($watch.ElapsedMilliseconds -le 300000) 'copy-time-budget'
        return [ordered]@{bytes=$total;sha256=[BitConverter]::ToString($hasher.Hash).Replace('-','').ToLowerInvariant()}
    }finally{if($hasher){$hasher.Dispose()};if($outputStream){$outputStream.Dispose()};$inputStream.Dispose()}
}
function Write-RuntimeJson([string]$Path,$Value) {
    return Write-RuntimeBytes $Path ([Text.UTF8Encoding]::new($false).GetBytes(($Value|ConvertTo-Json -Depth 35)))
}
function Read-RuntimeJson([byte[]]$Bytes) { return ([Text.UTF8Encoding]::new($false,$true).GetString($Bytes)|ConvertFrom-Json) }
function Observe-Runtime {
    return [ordered]@{
        processes=@(Get-CimInstance Win32_Process -Filter "Name='smart-factory.exe' OR Name='SmartFactoryBackend.exe'" | Sort-Object ProcessId | Select-Object ProcessId,ParentProcessId,Name,ExecutablePath,CreationDate)
        listeners=@(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object LocalPort -EQ 8000 | Sort-Object LocalAddress,OwningProcess | Select-Object LocalAddress,LocalPort,OwningProcess)
    }
}
function Assert-RuntimeCold($Snapshot) {
    Require-Runtime (@($Snapshot.processes).Count -eq 0 -and @($Snapshot.listeners).Count -eq 0) 'application-or-port-active'
}
function Hold-RuntimeProcess([int]$ProcessId,[string]$ExpectedExecutable) {
    $p=[Diagnostics.Process]::GetProcessById($ProcessId)
    try{
        $handle=$p.Handle
        Require-Runtime ($handle -ne [IntPtr]::Zero -and -not $p.HasExited) 'process-handle-or-exit'
        $created=$p.StartTime.ToUniversalTime()
        $exe=$p.MainModule.FileName
        Require-Runtime ($exe -ieq $ExpectedExecutable) 'process-executable-mismatch'
        return [pscustomobject]@{process=$p;identity=[ordered]@{pid=$ProcessId;created_at_utc=$created.ToString('o');created_filetime=$created.ToFileTimeUtc();created=([double]($created.Ticks-621355968000000000)/10000000);exe=$exe;native_handle_retained=$true}}
    }catch{$p.Dispose();throw}
}
function Read-RuntimeExit($Held) {
    Require-Runtime ($Held.process.WaitForExit(0)) 'held-process-still-running'
    Require-Runtime ($Held.process.StartTime.ToUniversalTime().ToFileTimeUtc() -eq $Held.identity.created_filetime) 'held-process-generation-mismatch'
    return [ordered]@{identity=$Held.identity;actual_exit_code=$Held.process.ExitCode;exit_at_utc=$Held.process.ExitTime.ToUniversalTime().ToString('o');forced_termination=$false}
}
function Wait-RuntimeProcesses($Held,[int]$TimeoutMilliseconds=450000) {
    Require-Runtime ($TimeoutMilliseconds -gt 0 -and $TimeoutMilliseconds -le 450000 -and @($Held).Count -gt 0) 'exit-wait-budget'
    $watch=[Diagnostics.Stopwatch]::StartNew()
    while($true){
        # HasExited can expose an exit code before the OS handle is signaled.
        # Only a signaled retained handle permits reading the final receipt.
        $pending=0
        foreach($one in $Held){if(-not $one.process.WaitForExit(0)){$pending++}}
        if($pending -eq 0){return}
        $remaining=$TimeoutMilliseconds-$watch.ElapsedMilliseconds
        Require-Runtime ($remaining -gt 0) 'normal-exit-timeout-no-force'
        Start-Sleep -Milliseconds ([int][Math]::Min(500,$remaining))
    }
}
function Read-RuntimeHealth($Request) {
    $q=[Net.HttpWebRequest]::Create('http://127.0.0.1:8000/health')
    $q.Method='GET';$q.Proxy=$null;$q.Timeout=5000;$q.ReadWriteTimeout=5000
    $r=$null;$s=$null;$m=[IO.MemoryStream]::new()
    try{
        $r=$q.GetResponse();Require-Runtime ([int]$r.StatusCode -eq 200) 'health-status'
        $s=$r.GetResponseStream();$buffer=New-Object byte[] 8192
        while(($n=$s.Read($buffer,0,$buffer.Length)) -gt 0){Require-Runtime ($m.Length+$n -le 2MB) 'health-byte-budget';$m.Write($buffer,0,$n)}
        $bytes=$m.ToArray();$h=Read-RuntimeJson $bytes
        Require-Runtime ($h.running -eq $true -and $h.mode -ceq 'REAL' -and $h.app_version -ceq (Get-RuntimeRequestVersion $Request)) 'health-runtime'
        Require-Runtime ($h.spot_temperature.build_git_commit -ceq $Request.candidate_commit -and $h.spot_temperature.v2_4_operational.logger_service_instance_id -ceq $Request.logger_service_instance_id) 'health-generation'
        Require-Runtime ($h.spot_temperature.v2_4_operational.current_v2_csv_file_name -ceq $Request.csv_name) 'health-csv'
        return ,$bytes
    }finally{if($s){$s.Dispose()};if($r){$r.Dispose()};$m.Dispose()}
}
function New-RuntimeResult([string]$Parent,[string]$Sid) {
    $parentPath=Plain-Runtime $Parent
    Require-Runtime ([IO.Directory]::Exists($parentPath)) 'result-parent-missing'
    $path=Plain-Runtime ($parentPath+'\R'+[Guid]::NewGuid().ToString('N').Substring(0,12))
    Require-Runtime (-not [IO.Directory]::Exists($path) -and -not [IO.File]::Exists($path)) 'fresh-result-required'
    $acl=[Security.AccessControl.DirectorySecurity]::new();$acl.SetAccessRuleProtection($true,$false)
    $acl.SetOwner([Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))
    foreach($reader in @('S-1-5-32-544','S-1-5-18',$Sid)){
        $rights=if($reader -ceq $Sid){'ReadAndExecute'}else{'FullControl'}
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($reader),$rights,'ContainerInherit,ObjectInherit','None','Allow'))
    }
    $null=[IO.Directory]::CreateDirectory($path,$acl)
    $actual=[IO.Directory]::GetAccessControl((Plain-Runtime $path))
    Require-Runtime ($actual.AreAccessRulesProtected -and $actual.GetOwner([Security.Principal.SecurityIdentifier]).Value -ceq 'S-1-5-32-544') 'result-owner-inheritance'
    $rules=@($actual.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    $expected=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]));$seen=@{}
    Require-Runtime ($rules.Count -eq 3) 'result-rule-count'
    foreach($rule in $rules){
        $id=$rule.IdentityReference.Value;$match=@($expected|Where-Object{$_.IdentityReference.Value -ceq $id})
        Require-Runtime ($match.Count -eq 1 -and -not $seen.ContainsKey($id)) 'result-rule-sid'
        Require-Runtime (-not $rule.IsInherited -and $rule.AccessControlType -eq 'Allow' -and $rule.FileSystemRights -eq $match[0].FileSystemRights -and $rule.InheritanceFlags -eq $match[0].InheritanceFlags -and $rule.PropagationFlags -eq 'None') 'result-rule-rights'
        $seen[$id]=$true
    }
    return $path
}
function Get-RuntimeRequestVersion($Request) {
    if($Request.schema -cin @('sfl-health-runtime-close-request-v1','sfl-health-runtime-close-request-v2') -and $Request.candidate_commit -ceq 'acaf77d95101a050f4d3ecd76125d3502036f5a7'){return '1.0.29'}
    if($Request.schema -ceq 'sfl-health-runtime-close-request-v3' -and $Request.candidate_commit -ceq '0732c8e810be3c46096b397812f53a9767354229'){return '1.0.30'}
    if($Request.schema -ceq 'sfl-health-runtime-close-request-v4' -and $Request.candidate_commit -ceq '685dde946e8ce2e34c65c6dde05be16e342f068e'){return '1.0.30'}
    if($Request.schema -ceq 'sfl-health-runtime-close-request-v5' -and $Request.candidate_commit -ceq '8de064317d6de42d321afb8395f7a30a1f31cd55'){return '1.0.30'}
    throw 'request-contract'
}
function Assert-RuntimeRequest($Request) {
    $null=Get-RuntimeRequestVersion $Request
    Require-Runtime ($Request.logger_service_instance_id -cmatch '^[a-f0-9-]{36}$' -and $Request.csv_name -cmatch '^Factory_Integrated_Log_v2_[0-9]{8}_[0-9]{6}\.csv$') 'request-generation'
    Require-Runtime ($Request.config_sha256 -cmatch '^[a-f0-9]{64}$') 'request-config-pin'
    if($Request.schema -cin @('sfl-health-runtime-close-request-v2','sfl-health-runtime-close-request-v3','sfl-health-runtime-close-request-v4','sfl-health-runtime-close-request-v5')){
        Require-Runtime ($null -ne $Request.PSObject.Properties['csv_first_sample_seq']) 'request-first-sequence'
        Require-Runtime (($Request.csv_first_sample_seq -is [int] -or $Request.csv_first_sample_seq -is [long]) -and $Request.csv_first_sample_seq -gt 0) 'request-first-sequence'
    }else{Require-Runtime ($null -eq $Request.PSObject.Properties['csv_first_sample_seq']) 'legacy-first-sequence-not-configurable'}
}
function Write-RuntimeIdentityResult([string]$Root,[string]$RequestSha256,$Files) {
    return Write-RuntimeJson ($Root+'\result.json') ([ordered]@{
        schema='sfl-health-runtime-identity-result-v1';status='RUNNING_IDENTITY_CAPTURED_REQUIRES_REVIEW'
        request_sha256=$RequestSha256;files=$Files;configuration_changed=$false
        application_started=$false;application_shutdown_performed=$false;actual_process_exit_observed=$false
        full_backup_created=$false;field_gate='NOT_EVALUATED';release_gate='HOLD';promotion_allowed=$false
    })
}
if($LibraryOnly){return}
$resultRoot=$null;$held=[Collections.Generic.List[object]]::new();$phase='preflight';$files=[ordered]@{}
try{
    $native=[Environment]::SystemDirectory+'\WindowsPowerShell\v1.0\powershell.exe'
    $sid='S-1-5-21-2762931165-1280404403-2847611662-1001'
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent();$principal=[Security.Principal.WindowsPrincipal]::new($identity)
    Require-Runtime ([Environment]::Is64BitProcess -and $PSVersionTable.PSEdition -ceq 'Desktop' -and $PSVersionTable.PSVersion.Major -eq 5 -and $PSVersionTable.PSVersion.Minor -eq 1 -and [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName -ieq $native) 'native-ps51-x64-required'
    Require-Runtime ($env:COMPUTERNAME -ceq 'DESKTOP-CIIT7LK' -and $identity.User.Value -ceq $sid -and $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) 'server-operator-admin-required'
    $env:PATH=[Environment]::SystemDirectory+';'+[IO.Path]::GetDirectoryName($native);$env:PSModulePath=[IO.Path]::GetDirectoryName($native)+'\Modules'
    $requestBytes=Read-RuntimeBytes $RequestPath
    Require-Runtime ($ExpectedRequestSha256 -cmatch '^[a-f0-9]{64}$' -and (Hash-Runtime $requestBytes) -ceq $ExpectedRequestSha256) 'request-pin'
    $request=Read-RuntimeJson $requestBytes;Assert-RuntimeRequest $request
    $factory=Plain-Runtime ([Environment]::GetFolderPath('Desktop')+'\SmartFactory')
    Require-Runtime ($factory -ieq 'C:\Users\user\Desktop\SmartFactory') 'desktop-root'
    $install='C:\Users\user\AppData\Local\Programs\smart-factory-logger-v2'
    $data='C:\Users\user\AppData\Roaming\SmartFactoryLogger'
    $config=Read-RuntimeBytes ($data+'\config.ini')
    Require-Runtime ((Hash-Runtime $config) -ceq $request.config_sha256) 'config-before-pin'
    $before=Observe-Runtime
    $backends=@($before.processes|Where-Object Name -ieq 'SmartFactoryBackend.exe')
    Require-Runtime ($backends.Count -eq 1 -and $before.processes.Count -le 16) 'single-backend-required'
    $backend=$backends[0];$mains=@($before.processes|Where-Object {$_.ProcessId -eq $backend.ParentProcessId -and $_.Name -ieq 'smart-factory.exe'})
    Require-Runtime ($mains.Count -eq 1) 'backend-parent'
    $owners=@($before.listeners|Select-Object -ExpandProperty OwningProcess -Unique)
    Require-Runtime ($owners.Count -eq 1 -and $owners[0] -eq $backend.ProcessId) 'listener-owner'
    foreach($p in $before.processes){
        $exe=if($p.Name -ieq 'SmartFactoryBackend.exe'){$install+'\resources\backend\SmartFactoryBackend.exe'}else{$install+'\smart-factory.exe'}
        $one=Hold-RuntimeProcess $p.ProcessId $exe;$held.Add($one)
        Require-Runtime ([Math]::Abs(([DateTime]::Parse($one.identity.created_at_utc).ToUniversalTime()-$p.CreationDate.ToUniversalTime()).TotalMilliseconds) -lt 1) 'cim-native-generation'
        Require-Runtime ($p.ProcessId -eq $mains[0].ProcessId -or $p.ParentProcessId -eq $mains[0].ProcessId) 'unexpected-process-tree'
    }
    $health=Read-RuntimeHealth $request
    $after=Observe-Runtime
    Require-Runtime (($before|ConvertTo-Json -Depth 6 -Compress) -ceq ($after|ConvertTo-Json -Depth 6 -Compress)) 'runtime-changed-during-read'
    foreach($one in $held){Require-Runtime (-not $one.process.HasExited) 'runtime-exited-during-read'}
    $resultRoot=New-RuntimeResult $factory $sid
    $files['request.json']=Write-RuntimeBytes ($resultRoot+'\request.json') $requestBytes
    $files['health-before.json']=Write-RuntimeBytes ($resultRoot+'\health-before.json') $health
    $files['runtime-before.json']=Write-RuntimeJson ($resultRoot+'\runtime-before.json') ([ordered]@{observed_at_utc=[DateTime]::UtcNow.ToString('o');main_pid=$mains[0].ProcessId;backend_pid=$backend.ProcessId;processes=@($held|ForEach-Object{$_.identity});observation=$before})
    if($IdentityOnly){
        $phase='running-identity-read'
        $configAfter=Read-RuntimeBytes ($data+'\config.ini')
        Require-Runtime ((Hash-Runtime $configAfter) -ceq $request.config_sha256) 'config-after-pin'
        foreach($one in $held){Require-Runtime (-not $one.process.HasExited) 'runtime-exited-during-read'}
        $files['config.ini']=Write-RuntimeBytes ($resultRoot+'\config.ini') $configAfter
        $receipt=Write-RuntimeIdentityResult $resultRoot $ExpectedRequestSha256 $files
        Write-Host ('RESULT_PATH='+$resultRoot);Write-Host ('RESULT_SHA256='+$receipt.sha256);exit 0
    }
    $phase='wait-normal-exit'
    Write-Host ('RESULT_PATH='+$resultRoot);Write-Host 'READY_FOR_NORMAL_APP_EXIT'
    Wait-RuntimeProcesses $held
    $phase='closed-read'
    $exits=@($held|ForEach-Object{Read-RuntimeExit $_})
    $files['process-exits.json']=Write-RuntimeJson ($resultRoot+'\process-exits.json') $exits
    Require-Runtime (@($exits|Where-Object{$_.actual_exit_code -ne 0}).Count -eq 0) 'nonzero-process-exit'
    $cold=Observe-Runtime;Assert-RuntimeCold $cold
    $files['runtime-after.json']=Write-RuntimeJson ($resultRoot+'\runtime-after.json') $cold
    $closedConfig=Read-RuntimeBytes ($data+'\config.ini')
    Require-Runtime ((Hash-Runtime $closedConfig) -ceq $request.config_sha256) 'config-after-pin'
    $files['config.ini']=Write-RuntimeBytes ($resultRoot+'\config.ini') $closedConfig
    $csvPath=$data+'\logs\test_data\'+$request.csv_name
    $metadataName=$request.csv_name.Replace('.csv','.metadata.json')
    $metadataBytes=Read-RuntimeBytes ($data+'\logs\test_data\'+$metadataName)
    $metadata=Read-RuntimeJson $metadataBytes
    Require-Runtime ($metadata.schema_metadata.git_commit -ceq $request.candidate_commit -and $metadata.schema_metadata.logger_service_instance_id -ceq $request.logger_service_instance_id) 'metadata-generation'
    Require-Runtime ($metadata.csv_closeout.finalized -eq $true -and $metadata.csv_closeout.closeout_reason -ceq 'shutdown' -and $metadata.csv_closeout.csv_file_name -ceq $request.csv_name -and $metadata.csv_closeout.logger_service_instance_id -ceq $request.logger_service_instance_id) 'metadata-not-finalized'
    $files[$metadataName]=Write-RuntimeBytes ($resultRoot+'\'+$metadataName) $metadataBytes
    $csvLimit=if($request.schema -cin @('sfl-health-runtime-close-request-v2','sfl-health-runtime-close-request-v3','sfl-health-runtime-close-request-v4','sfl-health-runtime-close-request-v5')){1073741824}else{134217728}
    $files[$request.csv_name]=Copy-RuntimeFile $csvPath ($resultRoot+'\'+$request.csv_name) $csvLimit
    Assert-RuntimeCold (Observe-Runtime)
    $receipt=Write-RuntimeJson ($resultRoot+'\result.json') ([ordered]@{schema='sfl-health-runtime-close-result-v1';status='CLOSED_RUNTIME_CAPTURED_REQUIRES_REVIEW';request_sha256=$ExpectedRequestSha256;files=$files;configuration_changed=$false;application_started=$false;forced_termination=$false;full_backup_created=$false;file_content_qa='NOT_EVALUATED';release_gate='HOLD';promotion_allowed=$false})
    Write-Host ('RESULT_PATH='+$resultRoot);Write-Host ('RESULT_SHA256='+$receipt.sha256);exit 0
}catch{
    if($resultRoot){$receipt=Write-RuntimeJson ($resultRoot+'\hold.json') ([ordered]@{status='HOLD';phase=$phase;error=$_.Exception.Message;files=$files;configuration_changed=$false;forced_termination=$false;release_gate='HOLD';promotion_allowed=$false});Write-Host ('RESULT_PATH='+$resultRoot);Write-Host ('HOLD_SHA256='+$receipt.sha256)}
    Write-Host ('RUNTIME_READ_HOLD='+$_.Exception.Message);exit 1
}finally{foreach($one in $held){$one.process.Dispose()}}
