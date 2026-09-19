# Build input only. Reviewed utility functions are prepended by the builder.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$expectedCommit = 'd7a1b20f96711fb07fc7add0867e79ee36506fce'
$expectedUser = 'S-1-5-21-2762931165-1280404403-2847611662-1001'
$installRoot = 'C:\Users\user\AppData\Local\Programs\smart-factory-logger-v2'
$configPath = 'C:\Users\user\AppData\Roaming\SmartFactoryLogger\config.ini'
$configHash = '6841C848A443DF91966C991707C2B21CA57C575993DCA36FACFF2592D070147E'
$releaseRoot = 'C:\ProgramData\SFL26S-29aee83c36044389828d6d20eb645503\payload\release'
$manifestHash = 'D527AA7F8284AF6917FE1166F070871C07BCA379F03BD32740BDEF70CD48814F'
$identityHash = '7EB46147F55DAD515E507196A7E1FBACD7D1B075E870DB159F82580DA64E3493'
$expectedPayloadTree = '0C18CE2E9F810A8636DA007BE00F02ADD5AEB7869E693E4827774B0E3C53F908'
$expectedInstalledTree = '91340EDC9A684196683B0BA5B42AB9993B99510857345A4A669CE74537DCC760'
$expectedPayloadFiles = 1645
$expectedInstalledBytes = [long]561157115
$uninstaller = [pscustomobject]@{path='Uninstall smart-factory.exe';length=[long]234261;sha256='610F5540AA0C6C24EF7DBEFFC1B5EE749D1B9C8CDCFC2B6EF643F8EA6F0DE837'}
$opsRoot = 'C:\ProgramData\SFLOps'
$pins = [Collections.Generic.List[IDisposable]]::new()
$clock = [Diagnostics.Stopwatch]::StartNew()
$phase = 'host-check'
$runRoot = $null
$savedPath = $env:PATH
$savedModules = $env:PSModulePath

function Need {
    param([bool]$OK,[string]$Code)
    if (-not $OK) { throw ('V1026_TREE_READ:' + $Code) }
}

function HashRows {
    param([string[]]$Rows)
    $copy = [string[]]$Rows.Clone()
    [Array]::Sort($copy,[StringComparer]::Ordinal)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes([string]::Concat($copy)))).Replace('-','') }
    finally { $sha.Dispose() }
}

function RelativeName {
    param([string]$Name)
    Need (-not [string]::IsNullOrWhiteSpace($Name)) 'manifest-name-empty'
    Need ($Name.Length -le 200 -and -not [IO.Path]::IsPathRooted($Name)) 'manifest-name-root'
    Need ($Name -cnotmatch '[\\:\x00-\x1f<>"|?*]') 'manifest-name-character'
    foreach ($part in $Name.Split('/')) {
        Need ($part -ne '' -and $part -notin @('.','..') -and $part -notmatch '[ .]$') 'manifest-name-segment'
        Need ($part -notmatch '^(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)') 'manifest-name-device'
    }
}

function ManifestMap {
    param([object]$Manifest)
    Need ((Property $Manifest 'schema') -ceq 'sfl-extracted-payload-v1') 'manifest-schema'
    $files = @(Property $Manifest 'files')
    Need ($files.Count -eq $expectedPayloadFiles -and (Counter $Manifest 'file_count') -eq $expectedPayloadFiles) 'manifest-count'
    $map = @{}
    $rows = [Collections.Generic.List[string]]::new()
    foreach ($entry in $files) {
        $name = [string](Property $entry 'path')
        RelativeName $name
        Need (-not $map.ContainsKey($name) -and $name -ine $uninstaller.path) 'manifest-duplicate'
        $length = Counter $entry 'length'
        $hash = [string](Property $entry 'sha256')
        Need ($hash -cmatch '^[A-F0-9]{64}$') 'manifest-hash-format'
        $map[$name] = $entry
        $rows.Add("$name`0$length`0$hash`n")
    }
    Need ((Property $Manifest 'tree_sha256') -ceq $expectedPayloadTree -and (HashRows $rows.ToArray()) -ceq $expectedPayloadTree) 'manifest-tree'
    $map[$uninstaller.path] = $uninstaller
    return $map
}

function InstalledInventory {
    param([string]$Root,[hashtable]$Expected)
    $full = (Plain $Root).TrimEnd('\')
    Need ([IO.Directory]::Exists($full)) 'installed-root'
    $queue = [Collections.Generic.Queue[string]]::new()
    $queue.Enqueue($full)
    $items = @{}
    $directories = 0
    while ($queue.Count -gt 0) {
        Need ($clock.Elapsed.TotalSeconds -lt 300) 'time-budget'
        $directory = Plain $queue.Dequeue()
        $directories++
        Need ($directories -le 4096) 'directory-budget'
        foreach ($path in [IO.Directory]::EnumerateFileSystemEntries($directory)) {
            Need ($clock.Elapsed.TotalSeconds -lt 300) 'time-budget'
            Need ($path.StartsWith($full+'\',[StringComparison]::OrdinalIgnoreCase) -and $path.Length -le 240) 'installed-path-boundary'
            $attr = [IO.File]::GetAttributes($path)
            Need (($attr -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'installed-reparse'
            if (($attr -band [IO.FileAttributes]::Directory) -ne 0) {
                Need (($directories + $queue.Count) -lt 4096) 'directory-budget'
                $queue.Enqueue($path)
                continue
            }
            $relative = $path.Substring($full.Length+1).Replace('\','/')
            Need ($Expected.ContainsKey($relative) -and -not $items.ContainsKey($relative)) 'installed-unexpected-file'
            Need ($relative -ceq [string]$Expected[$relative].path) 'installed-path-case'
            $items[$relative] = $path
        }
    }
    Need ($items.Count -eq $Expected.Count) 'installed-missing-file'
    return $items
}

function VerifyInstalled {
    param([string]$Root,[hashtable]$Expected)
    $items = InstalledInventory $Root $Expected
    $records = [Collections.Generic.List[string]]::new()
    [long]$total = 0
    $count = 0
    foreach ($relative in @($items.Keys | Sort-Object)) {
        Need ($clock.Elapsed.TotalSeconds -lt 300) 'time-budget'
        $entry = $Expected[$relative]
        $path = Plain $items[$relative]
        # Short shared reads: do not lock an active application against writes/deletes.
        $stream = [IO.File]::Open($path,'Open','Read',([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
        try {
            $length = [long]$stream.Length
            Need ($length -eq [long]$entry.length) 'installed-file-length'
            $hash = HashStream $stream
            Need ($stream.Length -eq $length -and $hash -ceq [string]$entry.sha256) 'installed-file-content'
        }
        finally { $stream.Dispose() }
        $records.Add("$relative`0$length`0$hash`n")
        $total += $length
        $count++
        if (($count % 250) -eq 0) { Write-Host ('[FILES] '+$count+'/'+$Expected.Count) }
    }
    $tree = HashRows $records.ToArray()
    Need ($total -eq $expectedInstalledBytes -and $tree -ceq $expectedInstalledTree) 'installed-tree'
    $null = InstalledInventory $Root $Expected
    return [pscustomobject]@{file_count=$count;total_bytes=$total;tree_sha256=$tree;membership_rechecked=$true;atomic_snapshot=$false;alternate_streams_checked=$false}
}

function AssertSafeOpsRoot {
    $null = Plain $opsRoot
    $acl = [IO.Directory]::GetAccessControl($opsRoot)
    Need ($acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -cin @('S-1-5-18','S-1-5-32-544')) 'ops-owner'
    $writes = [Security.AccessControl.FileSystemRights]::Write -bor [Security.AccessControl.FileSystemRights]::Delete -bor [Security.AccessControl.FileSystemRights]::DeleteSubdirectoriesAndFiles -bor [Security.AccessControl.FileSystemRights]::ChangePermissions -bor [Security.AccessControl.FileSystemRights]::TakeOwnership
    foreach ($rule in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])) {
        if ($rule.AccessControlType -eq 'Allow' -and $rule.IdentityReference.Value -cnotin @('S-1-5-18','S-1-5-32-544')) {
            Need (($rule.FileSystemRights -band $writes) -eq 0) 'ops-untrusted-write'
        }
    }
}

function NewReportRoot {
    AssertSafeOpsRoot
    $parent = $opsRoot+'\runs'
    AssertPrivateAcl $parent
    $candidate = [IO.Path]::GetFullPath($parent+'\v1026-tree-read-'+[DateTimeOffset]::Now.ToString('yyyyMMdd-HHmmss')+'-'+[Guid]::NewGuid().ToString('N'))
    Need ([IO.Path]::GetDirectoryName($candidate) -ceq $parent -and ($candidate+'\result.json.sha256.txt').Length -le 240) 'report-path'
    $null=Plain $candidate $true
    Need (-not [IO.File]::Exists($candidate) -and -not [IO.Directory]::Exists($candidate)) 'report-already-exists'
    [void][IO.Directory]::CreateDirectory($candidate,(ReportAcl))
    AssertReportAcl $candidate
    return $candidate
}

function ReportAcl {
    $acl=PrivateAcl
    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
        [Security.Principal.SecurityIdentifier]::new($expectedUser),
        'ReadAndExecute','ContainerInherit,ObjectInherit','None','Allow'))
    return $acl
}

function AssertReportAcl {
    param([string]$Path)
    $full=Plain $Path
    $acl=[IO.Directory]::GetAccessControl($full)
    Need ($acl.AreAccessRulesProtected -and $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -ceq 'S-1-5-32-544') 'report-owner-inheritance'
    $rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    $expectedRules=@((ReportAcl).GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    Need ($rules.Count -eq 3) 'report-acl-count'
    $seen=@{}
    foreach($rule in $rules){
        $sid=$rule.IdentityReference.Value
        $matching=@($expectedRules|Where-Object{$_.IdentityReference.Value -ceq $sid})
        Need ($matching.Count -eq 1 -and -not $seen.ContainsKey($sid)) 'report-acl-sid'
        Need (-not $rule.IsInherited -and $rule.AccessControlType -eq 'Allow' -and $rule.FileSystemRights -eq $matching[0].FileSystemRights -and $rule.InheritanceFlags -eq $matching[0].InheritanceFlags -and $rule.PropagationFlags -eq 'None') 'report-acl-rights'
        $seen[$sid]=$true
    }
}

function Runtime {
    $apps = @(Get-Process -Name 'smart-factory' -ErrorAction SilentlyContinue)
    $backends = @(Get-Process -Name 'SmartFactoryBackend' -ErrorAction SilentlyContinue)
    $owners = @(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object { $_.LocalPort -eq 8000 } | Select-Object -ExpandProperty OwningProcess -Unique)
    Need ($apps.Count -ge 1 -and $backends.Count -eq 1 -and $owners.Count -eq 1 -and $owners[0] -eq $backends[0].Id) 'runtime-membership'
    $backend = $backends[0]
    $parent = Get-CimInstance Win32_Process -Filter ('ProcessId = '+$backend.Id) -ErrorAction Stop
    Need (@($apps | Where-Object { $_.Id -eq $parent.ParentProcessId }).Count -eq 1) 'runtime-parent'
    $facts = [Collections.Generic.List[object]]::new()
    foreach ($process in @($apps)+@($backend)) {
        $wanted = if ($process.Id -eq $backend.Id) { $installRoot+'\resources\backend\SmartFactoryBackend.exe' } else { $installRoot+'\smart-factory.exe' }
        Need ($process.Path -ieq $wanted) 'runtime-path'
        $ticks = $process.StartTime.ToUniversalTime().Ticks
        Need (-not [SflInstallToken]::IsElevated($process.Id)) 'runtime-elevated'
        Need ([SflInstallToken]::UserSid($process.Id) -ceq $expectedUser) 'runtime-user'
        Need ([SflInstallToken]::SessionId($process.Id) -eq [Diagnostics.Process]::GetCurrentProcess().SessionId) 'runtime-session'
        $fresh = Get-Process -Id $process.Id -ErrorAction Stop
        Need ($fresh.StartTime.ToUniversalTime().Ticks -eq $ticks -and $fresh.Path -ieq $wanted) 'runtime-query-race'
        $facts.Add([pscustomobject]@{pid=$process.Id;start_ticks=$ticks;role=$(if($process.Id -eq $backend.Id){'backend'}else{'app'});elevated=$false})
    }
    $installers = @(Get-CimInstance Win32_Process -Filter "Name LIKE '%Setup%'" -ErrorAction Stop | Where-Object { $_.Name -match '(?i)(smart.factory|sfl)' -or $_.ExecutablePath -like '*\SFLInstall\*' })
    Need ($installers.Count -eq 0) 'installer-active'
    return [pscustomobject]@{main_pid=$parent.ParentProcessId;backend_pid=$backend.Id;processes=@($facts.ToArray() | Sort-Object pid)}
}

function SameRuntime {
    param([object]$Before,[object]$After)
    Need (($Before|ConvertTo-Json -Depth 5 -Compress) -ceq ($After|ConvertTo-Json -Depth 5 -Compress)) 'runtime-changed'
}

function LocalJsonBounded {
    param([ValidateSet('health','api/spot/config','stats')][string]$Endpoint)
    $request = [Net.HttpWebRequest]::Create('http://127.0.0.1:8000/'+$Endpoint)
    $request.Method='GET';$request.Proxy=$null;$request.AllowAutoRedirect=$false
    $request.Timeout=10000;$request.ReadWriteTimeout=10000
    $response=$null;$reader=$null
    $watch=[Diagnostics.Stopwatch]::StartNew()
    try {
        $response=$request.GetResponse()
        Need ([int]$response.StatusCode -eq 200) 'local-http'
        $reader=[IO.StreamReader]::new($response.GetResponseStream(),[Text.UTF8Encoding]::new($false,$true),$true)
        $buffer=New-Object char[] 4096
        $text=[Text.StringBuilder]::new()
        while (($n=$reader.Read($buffer,0,$buffer.Length)) -gt 0) {
            Need (($text.Length+$n) -le 2097152 -and $watch.Elapsed.TotalSeconds -lt 20) 'local-response-budget'
            [void]$text.Append($buffer,0,$n)
        }
        return ConvertFrom-Json -InputObject $text.ToString()
    }
    finally { if($null-ne$reader){$reader.Dispose()};if($null-ne$response){$response.Dispose()} }
}

function HealthIdentity {
    param([object]$Health)
    Need ((Property $Health 'app_version') -ceq '1.0.26') 'health-version'
    Need ((Property (Property $Health 'spot_temperature') 'build_git_commit') -ceq $expectedCommit) 'health-commit'
    Need ((Property $Health 'runtime_kind') -ceq 'frozen' -and (Property $Health 'executable_path') -ieq ($installRoot+'\resources\backend\SmartFactoryBackend.exe')) 'health-path'
    Need ((Property $Health 'frontend_runtime_class') -ceq 'packaged-resources' -and (Bool $Health 'frontend_static_ready')) 'health-frontend'
}

function SelectedStatus {
    param([object]$Image,[object]$Errors)
    $status = [string](Property $Image 'config_attestation_status')
    Need ($status -cin @('verified','not_requested','invalid_metadata','fingerprint_mismatch','device_readback_blocked')) 'attestation-status'
    return [pscustomobject]@{
        config_attestation_status=$status
        config_operator_verified=Bool $Image 'config_operator_verified'
        config_drift_detected=Bool $Image 'config_drift_detected'
        fingerprint_only_drift=(@(Property $Image 'config_drift_fields').Count -eq 1 -and @(Property $Image 'config_drift_fields')[0] -ceq 'spot_config_fingerprint_sha256')
        low_signal_comparator_verified=Bool $Image 'low_signal_comparator_verified'
        historical_v1020_attestation_present=((Property $Image 'spot_config_verified_fingerprint_sha256') -ceq '74d2c05108eac93f7f3ef33b14f8b9018c3404b8996c0d6e7f94e5abc3da48ab')
        image_ok=((Property $Image 'image_status') -ceq 'ok')
        image_upstream=((Property $Image 'image_source') -ceq 'upstream')
        image_refresh_success_count=Counter $Image 'image_refresh_success_count'
        image_refresh_failure_count=Counter $Image 'image_refresh_failure_count'
        source_port_transport_failure_count=Counter $Image 'source_port_transport_failure_count'
        error_queue_size=Counter $Errors 'queue_size'
    }
}

try {
    $native=[IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
    $principal=[Security.Principal.WindowsPrincipal]::new($identity)
    Need ([Environment]::Is64BitProcess -and $PSVersionTable.PSEdition -ceq 'Desktop' -and $PSVersionTable.PSVersion.Major -eq 5 -and $PSVersionTable.PSVersion.Minor -eq 1 -and [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName -ieq $native -and $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) 'native-admin-ps51'
    Need ($identity.User.Value -ceq $expectedUser -and $env:APPDATA -ieq 'C:\Users\user\AppData\Roaming') 'server-operator-profile'
    $env:PATH=[Environment]::SystemDirectory+';'+[IO.Path]::GetDirectoryName($native)
    $env:PSModulePath=[IO.Path]::GetDirectoryName($native)+'\Modules'
    $runRoot=NewReportRoot

    $phase='release-binding';Write-Host '[STEP 1/4] Bind the exact release manifest. Product files are read only.'
    $manifestPath=$releaseRoot+'\extracted-payload-manifest.json'
    $null=FileFact $manifestPath $manifestHash
    $null=FileFact ($releaseRoot+'\release_identity.json') $identityHash
    $release=ReadJson ($releaseRoot+'\release_identity.json')
    Need ((Property $release 'product_version') -ceq '1.0.26' -and (Property $release 'product_commit') -ceq $expectedCommit) 'release-identity'
    $map=ManifestMap (ReadJson $manifestPath)

    $phase='runtime-before';Write-Host '[STEP 2/4] Check the current standard-user runtime and unchanged config.'
    InitializeTokenInspector
    $before=Runtime
    $null=MutableFileFact $configPath $configHash 2670
    HealthIdentity (LocalJsonBounded 'health')
    SameRuntime $before (Runtime)

    $phase='installed-tree';Write-Host '[STEP 3/4] Read and SHA256-check 1,646 installed files. No installer will run.'
    $tree=VerifyInstalled $installRoot $map

    $phase='final-binding';Write-Host '[STEP 4/4] Recheck runtime/config and save a short selected report.'
    $null=MutableFileFact $configPath $configHash 2670
    SameRuntime $before (Runtime)
    HealthIdentity (LocalJsonBounded 'health')
    $spot=LocalJsonBounded 'api/spot/config'
    $stats=LocalJsonBounded 'stats'
    $selected=SelectedStatus (Property $spot 'image') (Property $stats 'errors')
    SameRuntime $before (Runtime)
    $null=MutableFileFact $configPath $configHash 2670
    $null=InstalledInventory $installRoot $map
    $result=[ordered]@{
        schema_version='v1026-installed-read-result-v1'
        result='V1026_INSTALLED_TREE_VERIFIED_OPERATIONAL_REVIEW_PENDING'
        checked_at=[DateTimeOffset]::Now.ToString('o');elapsed_seconds=[Math]::Round($clock.Elapsed.TotalSeconds,2)
        product_version='1.0.26';product_commit=$expectedCommit
        manifest_sha256=$manifestHash;release_identity_sha256=$identityHash
        installed_tree=$tree;config_sha256=$configHash;runtime=$before;selected_status=$selected
        product_changes_made=$false;configuration_modified=$false;application_restart_performed=$false
        installer_started=$false;attestation_updated=$false;automatic_rollback_performed=$false
        added_spot_image_requests=$false;continuous_liveness_verified=$false;canary_started=$false
        original_installer_hold_overridden=$false;production_promotion_allowed=$false
        next_action='REVIEW_INSTALL_IDENTITY_THEN_PREPARE_OPERATOR_CONFIRMED_REATTESTATION'
        limitation='Selected local snapshots and sequential unnamed-file-stream hashes, not an atomic filesystem snapshot, process-memory verification, hostile-race defense, or operational approval. Empty directories and alternate streams are not validated. Local API calls may create normal app request logs. No new device/image request is issued by this helper. Minimal backup still excludes accumulated business logs.'
    }
    AssertReportAcl $runRoot
    $resultHash=WriteJsonNew ($runRoot+'\result.json') $result
    Write-Host '[COMPLETE] Installed file identity verified. Operational acceptance and re-attestation remain pending.' -ForegroundColor Green
    Write-Host ('[SEND FILE] '+$runRoot+'\result.json')
    Write-Host ('[SHA256] '+$resultHash)
    Write-Host '[NO ACTION] Keep the app running. Do not reinstall, edit config or start a Canary from this result.'
}
catch {
    $reason='details-withheld'
    $e=$_.Exception
    while($null-ne$e){if($e.Message -cmatch 'V1026_TREE_READ:([a-z0-9.-]+)'){$reason=$Matches[1];break};$e=$e.InnerException}
    Write-Host ('[HOLD] phase='+$phase+' reason='+$reason) -ForegroundColor Yellow
    if($null-ne$runRoot){
        try{
            AssertReportAcl $runRoot
            $null=WriteJsonNew ($runRoot+'\hold.json') ([ordered]@{schema_version='v1026-installed-read-hold-v1';result='HOLD';checked_at=[DateTimeOffset]::Now.ToString('o');phase=$phase;reason=$reason;product_changes_made=$false;partial_files_preserved=$true;automatic_rollback_performed=$false})
            Write-Host ('[SEND FILE] '+$runRoot+'\hold.json')
        }catch{Write-Host '[HOLD] Receipt unavailable; preserve the short console output.'}
    }
    throw 'V1026_TREE_READ_HOLD: Preserve output. No automatic retry, cleanup, restart, installation or rollback.'
}
finally {
    foreach($pin in $pins){$pin.Dispose()}
    $env:PATH=$savedPath;$env:PSModulePath=$savedModules
}
