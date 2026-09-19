[CmdletBinding()]
param([switch]$Execute)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$opsRoot = 'C:\ProgramData\SFLOps'
$stageRoot = 'C:\ProgramData\SFL26S-29aee83c36044389828d6d20eb645503'
$stageReceipt = $stageRoot + '\preflight-result.json'
$stageReceiptHash = 'F4B2FA04536CCC8B3CF095E2D643E7CB6BE0766CF3BB98D5F7FAF301C5AA5C86'
$payloadRoot = $stageRoot + '\payload'
$releaseRoot = $payloadRoot + '\release'
$kitRoot = $payloadRoot + '\kit'
$transferManifest = $payloadRoot + '\transfer-manifest.json'
$transferManifestHash = 'A32E25C0901AC9CF438517E55DE2B85E03AE7243C9DC997410A1E5D04683286E'
$installer = $releaseRoot + '\smart-factory-logger-v2 Setup 1.0.26.exe'
$installerHash = '1096276CC7C82E765A7BD1F03597CC09FF285AE587AC6B666CC86A04A3BFC25F'
$installerLength = [long]164003067
$payloadManifest = $releaseRoot + '\extracted-payload-manifest.json'
$payloadManifestHash = 'D527AA7F8284AF6917FE1166F070871C07BCA379F03BD32740BDEF70CD48814F'
$releaseIdentity = $releaseRoot + '\release_identity.json'
$releaseIdentityHash = '7EB46147F55DAD515E507196A7E1FBACD7D1B075E870DB159F82580DA64E3493'
$backupWorkRoot = 'C:\ProgramData\SFLOps\backups\v1025-min-20260916-090230-5ea532c9'
$backupResult = $backupWorkRoot + '\result.json'
$backupResultHash = '88FE4660AC294E1484FC9C2C4AA9400E77BC5EB6506FAD28A0E76ECD59F89FD0'
$backupManifestHash = '85B0B7D46AD4519E7149A3F0F8FAF7DA6F009BE362C169B11C9B529FD147B628'
$configPath = 'C:\Users\user\AppData\Roaming\SmartFactoryLogger\config.ini'
$configHash = '6841C848A443DF91966C991707C2B21CA57C575993DCA36FACFF2592D070147E'
$installRoot = 'C:\Users\user\AppData\Local\Programs\smart-factory-logger-v2'
$recoveryInstaller = 'C:\ProgramData\SFL-76B317D0A2901C6EFC649404211C8109\SmartFactoryLogger_v1.0.25_a203baf_unsigned_internal_20260909T012500Z\smart-factory-logger-v2 Setup 1.0.25.exe'
$recoveryHash = '9EE81CD9B809275B7E49E1441CBBF11C2B7BBC1E2A372A7D7163E4DCFFE6ADA1'
$uninstallerName = 'Uninstall smart-factory.exe'
$uninstallerLength = [long]234261
$uninstallerHash = '610F5540AA0C6C24EF7DBEFFC1B5EE749D1B9C8CDCFC2B6EF643F8EA6F0DE837'
$expectedInstalledFiles = 1646
$expectedInstalledBytes = [long]561157115
$expectedInstalledTree = '91340EDC9A684196683B0BA5B42AB9993B99510857345A4A669CE74537DCC760'
$expectedPayloadFiles = 1645
$expectedPayloadTree = '0C18CE2E9F810A8636DA007BE00F02ADD5AEB7869E693E4827774B0E3C53F908'

$clock = [Diagnostics.Stopwatch]::StartNew()
$phase = 'preparation-only'
$runRoot = $null
$launchRoot = $null
$installerProcess = $null
$pins = [Collections.Generic.List[IDisposable]]::new()
$savedPath = $env:PATH
$savedModules = $env:PSModulePath

function Need {
    param([bool]$OK,[string]$Code)
    if (-not $OK) { throw ('V1026_INSTALL:' + $Code) }
}

function Plain {
    param([string]$Path,[bool]$AllowMissing=$false)
    $full = [IO.Path]::GetFullPath($Path)
    if (-not $AllowMissing) {
        Need ([IO.File]::Exists($full) -or [IO.Directory]::Exists($full)) 'path-missing'
    }
    $node = if ([IO.File]::Exists($full)) { [IO.FileInfo]::new($full) } else { [IO.DirectoryInfo]::new($full) }
    while ($null -ne $node) {
        if ([int]$node.Attributes -ne -1) {
            Need (($node.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'reparse-path'
        }
        if ($node -is [IO.FileInfo]) { $node = $node.Directory } else { $node = $node.Parent }
    }
    return $full
}

function HashStream {
    param([IO.Stream]$Stream)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $Stream.Position = 0
        return [BitConverter]::ToString($sha.ComputeHash($Stream)).Replace('-','')
    }
    finally { $sha.Dispose() }
}

function FileFact {
    param([string]$Path,[string]$ExpectedHash='',[long]$ExpectedLength=-1)
    $full = Plain $Path
    Need ([IO.File]::Exists($full)) 'required-file'
    $stream = [IO.File]::Open($full,'Open','Read','Read')
    $pins.Add($stream)
    $length = [long]$stream.Length
    $hash = HashStream $stream
    if ($ExpectedLength -ge 0) { Need ($length -eq $ExpectedLength) 'file-length' }
    if ($ExpectedHash -ne '') { Need ($hash -ceq $ExpectedHash) 'file-hash' }
    return [pscustomobject]@{path=$full;length=$length;sha256=$hash}
}

function MutableFileFact {
    param([string]$Path,[string]$ExpectedHash,[long]$ExpectedLength)
    $full = Plain $Path
    $stream = [IO.File]::Open($full,'Open','Read',([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
    try {
        $length = [long]$stream.Length
        $hash = HashStream $stream
        Need ($stream.Length -eq $length) 'mutable-file-drift'
        Need ($length -eq $ExpectedLength -and $hash -ceq $ExpectedHash) 'mutable-file-fact'
        return [pscustomobject]@{path=$full;length=$length;sha256=$hash;sharing='ReadWrite,Delete'}
    }
    finally { $stream.Dispose() }
}

function ReadJson {
    param([string]$Path)
    $bytes = [IO.File]::ReadAllBytes((Plain $Path))
    $text = [Text.UTF8Encoding]::new($false,$true).GetString($bytes)
    if ($text.Length -gt 0 -and [int][char]$text[0] -eq 0xFEFF) { $text = $text.Substring(1) }
    return ConvertFrom-Json -InputObject $text
}

function Property {
    param([object]$Object,[string]$Name)
    Need ($null -ne $Object) ('missing-object-'+$Name)
    $property = $Object.PSObject.Properties[$Name]
    Need ($null -ne $property) ('missing-field-'+$Name)
    return $property.Value
}

function Bool {
    param([object]$Object,[string]$Name)
    $value = Property $Object $Name
    Need ($value -is [bool]) ('invalid-bool-'+$Name)
    return [bool]$value
}

function Counter {
    param([object]$Object,[string]$Name)
    $value = Property $Object $Name
    Need (($value -is [int] -or $value -is [long]) -and [long]$value -ge 0) ('invalid-counter-'+$Name)
    return [long]$value
}

function AssertSidecar {
    param([string]$Path,[string]$Expected)
    $lines = @([IO.File]::ReadAllLines((Plain $Path)))
    Need ($lines.Count -eq 1 -and $lines[0] -ceq $Expected) 'sidecar'
}

function PrivateAcl {
    $acl = [Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true,$false)
    $acl.SetOwner([Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))
    foreach ($sid in @('S-1-5-32-544','S-1-5-18')) {
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
            [Security.Principal.SecurityIdentifier]::new($sid),'FullControl','ContainerInherit,ObjectInherit','None','Allow'))
    }
    return $acl
}

function AssertPrivateAcl {
    param([string]$Path)
    $full = Plain $Path
    Need ([IO.Directory]::Exists($full)) 'private-directory-missing'
    $acl = [IO.Directory]::GetAccessControl($full)
    Need ($acl.AreAccessRulesProtected) 'private-acl-inheritance'
    Need ($acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -ceq 'S-1-5-32-544') 'private-owner'
    $rules = @($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    Need ($rules.Count -eq 2) 'private-acl-count'
    $seen = @{}
    foreach ($rule in $rules) {
        $sid = $rule.IdentityReference.Value
        Need ($sid -cin @('S-1-5-32-544','S-1-5-18') -and -not $seen.ContainsKey($sid)) 'private-acl-sid'
        Need (-not $rule.IsInherited -and $rule.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow) 'private-acl-rule'
        Need ($rule.FileSystemRights -eq [Security.AccessControl.FileSystemRights]::FullControl) 'private-acl-rights'
        Need ($rule.InheritanceFlags -eq ([Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [Security.AccessControl.InheritanceFlags]::ObjectInherit)) 'private-acl-flags'
        Need ($rule.PropagationFlags -eq [Security.AccessControl.PropagationFlags]::None) 'private-acl-propagation'
        $seen[$sid] = $true
    }
}

function AssertOpsRoot {
    param([string]$Path)
    $full=Plain $Path
    Need([IO.Directory]::Exists($full))'ops-root-missing'
    $acl=[IO.Directory]::GetAccessControl($full)
    Need($acl.GetOwner([Security.Principal.SecurityIdentifier]).Value-cin@('S-1-5-18','S-1-5-32-544'))'ops-root-owner'
    $mask=[Security.AccessControl.FileSystemRights]::Write -bor [Security.AccessControl.FileSystemRights]::Modify -bor [Security.AccessControl.FileSystemRights]::FullControl
    foreach($rule in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])){
        Need(-not($rule.AccessControlType-eq[Security.AccessControl.AccessControlType]::Allow-and$rule.IdentityReference.Value-cin@('S-1-1-0','S-1-5-11','S-1-5-32-545')-and($rule.FileSystemRights-band$mask)-ne0))'ops-root-broad-write'
    }
}

function NewPrivateDirectory {
    param([string]$Path)
    $full = Plain $Path $true
    Need (-not [IO.File]::Exists($full) -and -not [IO.Directory]::Exists($full)) 'new-private-exists'
    Need ([IO.Directory]::Exists([IO.Path]::GetDirectoryName($full))) 'new-private-parent'
    [void][IO.Directory]::CreateDirectory($full,(PrivateAcl))
    AssertPrivateAcl $full
}

function WriteJsonNew {
    param([string]$Path,[object]$Value)
    Need (-not [IO.File]::Exists($Path) -and -not [IO.File]::Exists($Path+'.sha256.txt')) 'evidence-exists'
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes(($Value|ConvertTo-Json -Depth 12))
    $stream = [IO.File]::Open($Path,'CreateNew','Write','None')
    try { $stream.Write($bytes,0,$bytes.Length);$stream.Flush($true) } finally { $stream.Dispose() }
    $read = [IO.File]::Open($Path,'Open','Read','Read')
    try { $hash = HashStream $read } finally { $read.Dispose() }
    $side = [IO.File]::Open($Path+'.sha256.txt','CreateNew','Write','None')
    try { $b=[Text.Encoding]::ASCII.GetBytes($hash+"`n");$side.Write($b,0,$b.Length);$side.Flush($true) } finally {$side.Dispose()}
    return $hash
}

function AssertStopped {
    Need (@(Get-Process -Name 'smart-factory' -ErrorAction SilentlyContinue).Count -eq 0) 'app-not-stopped'
    Need (@(Get-Process -Name 'SmartFactoryBackend' -ErrorAction SilentlyContinue).Count -eq 0) 'backend-not-stopped'
    Need (@(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue).Count -eq 0) 'port-not-stopped'
}

function AssertStage {
    AssertPrivateAcl $stageRoot
    $null = FileFact $stageReceipt $stageReceiptHash
    AssertSidecar ($stageReceipt+'.sha256.txt') $stageReceiptHash
    $receipt = ReadJson $stageReceipt
    Need ((Property $receipt 'schema_version') -ceq 'v1026-static-stage-result-v1') 'stage-schema'
    Need ((Property $receipt 'result') -ceq 'V1026_TRANSFER_STAGED_RUNTIME_RECORDED_NOT_INSTALL_READY') 'stage-result'
    Need ((Property $receipt 'protected_stage_root') -ceq $stageRoot) 'stage-root'
    Need ((Property $receipt 'release_root') -ceq $releaseRoot -and (Property $receipt 'canary_root') -ceq $kitRoot) 'stage-paths'
    Need (-not (Bool $receipt 'installation_started') -and -not (Bool $receipt 'product_changes_made')) 'stage-mutated'
    $null = FileFact $transferManifest $transferManifestHash
    $manifest = ReadJson $transferManifest
    Need ((Property $manifest 'schema_version') -ceq 'v1026-static-stage-transfer-v1') 'transfer-schema'
    Need ((Property $manifest 'product_commit') -ceq 'd7a1b20f96711fb07fc7add0867e79ee36506fce') 'transfer-commit'
    $files = @(Property $manifest 'files')
    Need ($files.Count -eq 31) 'transfer-count'
    $seen = @{}
    foreach ($entry in $files) {
        $name = [string](Property $entry 'name')
        Need (-not $seen.ContainsKey($name) -and $name -cnotmatch '(^|/)\.\.(/|$)' -and -not [IO.Path]::IsPathRooted($name)) 'transfer-name'
        $seen[$name] = $true
        $path = Join-Path $payloadRoot $name.Replace('/','\')
        $null = FileFact $path ([string](Property $entry 'sha256')) ([long](Property $entry 'length'))
    }
    $null = FileFact $installer $installerHash $installerLength
    $null = FileFact $payloadManifest $payloadManifestHash
    $null = FileFact $releaseIdentity $releaseIdentityHash
    $identity = ReadJson $releaseIdentity
    Need ((Property $identity 'product_version') -ceq '1.0.26' -and (Property $identity 'product_commit') -ceq 'd7a1b20f96711fb07fc7add0867e79ee36506fce') 'release-identity'
    Need ((Property $identity 'classification') -ceq 'UNSIGNED_INTERNAL_DEVELOPMENT_CANDIDATE') 'release-classification'
    return $manifest
}

function AssertBackup {
    AssertPrivateAcl $backupWorkRoot
    $null = FileFact $backupResult $backupResultHash
    AssertSidecar ($backupResult+'.sha256.txt') $backupResultHash
    $result = ReadJson $backupResult
    Need ((Property $result 'schema_version') -ceq 'v1025-minimal-cold-backup-result-v1') 'backup-schema'
    Need ((Property $result 'result') -ceq 'V1025_MINIMAL_COLD_BACKUP_AND_FILE_RESTORE_VERIFIED') 'backup-result'
    Need ((Property $result 'product_version') -ceq '1.0.25' -and (Property $result 'product_commit') -ceq 'a203baf62b544d38072a32d71ef411c7cf8b6490') 'backup-product'
    Need ((Property $result 'manifest_sha256') -ceq $backupManifestHash) 'backup-manifest-claim'
    Need ((Property $result 'backup_root') -ceq ($backupWorkRoot+'\backup')) 'backup-root-claim'
    Need ((Property $result 'restore_rehearsal_root') -ceq ($backupWorkRoot+'\restore')) 'restore-root-claim'
    foreach ($name in @('app_still_stopped','backup_readback_verified','restored_file_hashes_verified','source_hashes_rechecked','exact_membership_verified','original_state_hashes_rechecked')) {
        Need (Bool $result $name) ('backup-gate-'+$name)
    }
    Need (-not (Bool $result 'installation_started') -and -not (Bool $result 'automatic_restart_performed')) 'backup-install-flag'
    Need ([long](Property $result 'source_file_count') -gt 0 -and [long](Property $result 'source_bytes') -gt 0) 'backup-empty'
    Need (-not (Bool $result 'installed_program_directory_backed_up')) 'backup-scope-claim'
    $null = FileFact ($backupWorkRoot+'\files.manifest.tsv') $backupManifestHash
    foreach ($pair in @(@('intent.json','intent_sha256'),@('state-map.json','state_map_sha256'))) {
        $claim = [string](Property $result $pair[1])
        $null = FileFact ($backupWorkRoot+'\'+$pair[0]) $claim
        AssertSidecar ($backupWorkRoot+'\'+$pair[0]+'.sha256.txt') $claim
    }
    Need ([IO.Directory]::Exists((Plain ($backupWorkRoot+'\backup'))) -and [IO.Directory]::Exists((Plain ($backupWorkRoot+'\restore')))) 'backup-directories'
    return $result
}

function GetInstalledTree {
    param([string]$Root,[object]$Manifest)
    $rootFull = (Plain $Root).TrimEnd('\')
    $expected = @{}
    foreach ($entry in @(Property $Manifest 'files')) {
        $name = [string](Property $entry 'path')
        Need (-not $expected.ContainsKey($name) -and $name -cnotmatch '(^|/)\.\.(/|$)' -and -not [IO.Path]::IsPathRooted($name)) 'payload-name'
        $expected[$name] = $entry
    }
    Need ($expected.Count -eq $expectedPayloadFiles -and [string](Property $Manifest 'tree_sha256') -ceq $expectedPayloadTree) 'payload-contract'
    $expected[$uninstallerName] = [pscustomobject]@{path=$uninstallerName;length=$uninstallerLength;sha256=$uninstallerHash}
    $records = [Collections.Generic.List[string]]::new()
    $queue = [Collections.Generic.Queue[string]]::new();$queue.Enqueue($rootFull)
    [long]$bytes=0;[int]$count=0
    while ($queue.Count -gt 0) {
        $directory = Plain $queue.Dequeue()
        foreach ($item in @(Get-ChildItem -LiteralPath $directory -Force -ErrorAction Stop)) {
            Need (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'installed-reparse'
            if ($item.PSIsContainer) { $queue.Enqueue($item.FullName);continue }
            $relative = $item.FullName.Substring($rootFull.Length+1).Replace('\','/')
            Need ($expected.ContainsKey($relative)) 'installed-unexpected-file'
            $entry = $expected[$relative]
            $stream = [IO.File]::Open($item.FullName,'Open','Read','Read')
            try { $hash=HashStream $stream;$length=[long]$stream.Length } finally {$stream.Dispose()}
            Need ($length -eq [long](Property $entry 'length') -and $hash -ceq [string](Property $entry 'sha256')) 'installed-file-mismatch'
            $records.Add("$relative`0$length`0$hash`n");$bytes += $length;$count++
            if (($count%250)-eq 0) { Write-Host ('[INSTALLED TREE] verified='+$count+'/'+$expectedInstalledFiles) }
        }
    }
    Need ($count -eq $expected.Count -and $count -eq $expectedInstalledFiles -and $bytes -eq $expectedInstalledBytes) 'installed-membership'
    $rows=$records.ToArray();[Array]::Sort($rows,[StringComparer]::Ordinal)
    $sha=[Security.Cryptography.SHA256]::Create()
    try{$tree=[BitConverter]::ToString($sha.ComputeHash([Text.UTF8Encoding]::new($false).GetBytes([string]::Concat($rows)))).Replace('-','')}finally{$sha.Dispose()}
    Need ($tree -ceq $expectedInstalledTree) 'installed-tree'
    return [pscustomobject]@{file_count=$count;total_bytes=$bytes;tree_sha256=$tree}
}

function InitializeTokenInspector {
    if ('SflInstallToken' -as [type]) { return }
    Add-Type -Language CSharp -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Security.Principal;
public static class SflInstallToken {
  const uint PROCESS_QUERY_LIMITED_INFORMATION=0x1000,TOKEN_QUERY=0x0008;
  const int TokenUser=1,TokenSessionId=12,TokenElevation=20;
  [DllImport("kernel32.dll",SetLastError=true)] static extern IntPtr OpenProcess(uint a,bool i,int p);
  [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
  [DllImport("advapi32.dll",SetLastError=true)] static extern bool OpenProcessToken(IntPtr p,uint a,out IntPtr t);
  [DllImport("advapi32.dll",SetLastError=true)] static extern bool GetTokenInformation(IntPtr t,int c,IntPtr b,int l,out int r);
  static IntPtr Token(int pid,out IntPtr process){process=OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,false,pid);if(process==IntPtr.Zero)throw new Win32Exception(Marshal.GetLastWin32Error());IntPtr token;if(!OpenProcessToken(process,TOKEN_QUERY,out token)){CloseHandle(process);throw new Win32Exception(Marshal.GetLastWin32Error());}return token;}
  static int IntValue(int pid,int kind){IntPtr p=IntPtr.Zero,t=IntPtr.Zero,b=IntPtr.Zero;try{t=Token(pid,out p);b=Marshal.AllocHGlobal(4);int r;if(!GetTokenInformation(t,kind,b,4,out r))throw new Win32Exception(Marshal.GetLastWin32Error());return Marshal.ReadInt32(b);}finally{if(b!=IntPtr.Zero)Marshal.FreeHGlobal(b);if(t!=IntPtr.Zero)CloseHandle(t);if(p!=IntPtr.Zero)CloseHandle(p);}}
  public static bool IsElevated(int pid){return IntValue(pid,TokenElevation)!=0;}
  public static int SessionId(int pid){return IntValue(pid,TokenSessionId);}
  public static string UserSid(int pid){IntPtr p=IntPtr.Zero,t=IntPtr.Zero,b=IntPtr.Zero;try{t=Token(pid,out p);int n=0;GetTokenInformation(t,TokenUser,IntPtr.Zero,0,out n);if(n<=0&&Marshal.GetLastWin32Error()!=122)throw new Win32Exception(Marshal.GetLastWin32Error());b=Marshal.AllocHGlobal(n);int r;if(!GetTokenInformation(t,TokenUser,b,n,out r))throw new Win32Exception(Marshal.GetLastWin32Error());return new SecurityIdentifier(Marshal.ReadIntPtr(b)).Value;}finally{if(b!=IntPtr.Zero)Marshal.FreeHGlobal(b);if(t!=IntPtr.Zero)CloseHandle(t);if(p!=IntPtr.Zero)CloseHandle(p);}}
}
'@
}

function NewLaunchDirectory {
    param([string]$Path,[Security.Principal.SecurityIdentifier]$UserSid)
    $full = Plain $Path $true
    Need (-not [IO.File]::Exists($full) -and -not [IO.Directory]::Exists($full)) 'launch-exists'
    $acl=PrivateAcl
    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($UserSid,'ReadAndExecute','ContainerInherit,ObjectInherit','None','Allow'))
    [void][IO.Directory]::CreateDirectory($full,$acl)
    $actual=[IO.Directory]::GetAccessControl($full)
    Need ($actual.AreAccessRulesProtected -and $actual.GetOwner([Security.Principal.SecurityIdentifier]).Value -ceq 'S-1-5-32-544') 'launch-acl'
}

function LaunchInstallerStandard {
    param([string]$Source)
    $user=[Security.Principal.WindowsIdentity]::GetCurrent().User
    $local='C:\Users\user\AppData\Local'
    Need ($env:LOCALAPPDATA -ieq $local) 'localappdata'
    $parent=$local+'\SFLInstall'
    if (-not [IO.Directory]::Exists($parent)) { [void][IO.Directory]::CreateDirectory($parent) }
    Plain $parent|Out-Null
    $script:launchRoot=$parent+'\v1026-'+[Guid]::NewGuid().ToString('N')
    NewLaunchDirectory $script:launchRoot $user
    $copy=$script:launchRoot+'\smart-factory-logger-v2 Setup 1.0.26.exe'
    [IO.File]::Copy($Source,$copy,$false)
    $stream=[IO.File]::Open($copy,'Open','Read','Read');$pins.Add($stream)
    Need ($stream.Length -eq $installerLength -and (HashStream $stream) -ceq $installerHash) 'launch-copy'
    InitializeTokenInspector
    $before=@(Get-Process -ErrorAction SilentlyContinue|Select-Object -ExpandProperty Id)
    $started=[DateTimeOffset]::Now
    $shell=New-Object -ComObject Shell.Application
    try{$shell.ShellExecute($copy,'',$script:launchRoot,'open',1)}finally{if($null-ne$shell){[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($shell)}}
    $wait=[Diagnostics.Stopwatch]::StartNew();$found=$null
    while($wait.Elapsed.TotalSeconds-lt 30 -and $null-eq$found){
        Start-Sleep -Milliseconds 200
        $matches=@(Get-Process -ErrorAction SilentlyContinue|Where-Object{$_.Id-notin$before-and$null-ne$_.Path-and$_.Path-ieq$copy})
        Need ($matches.Count -le 1) 'installer-process-ambiguous'
        if($matches.Count-eq 1){$found=$matches[0]}
    }
    Need ($null-ne$found) 'installer-process-not-captured'
    Need (-not [SflInstallToken]::IsElevated($found.Id)) 'installer-elevated'
    Need ([SflInstallToken]::UserSid($found.Id)-ceq$user.Value) 'installer-user'
    Need ([SflInstallToken]::SessionId($found.Id)-eq[Diagnostics.Process]::GetCurrentProcess().SessionId) 'installer-session'
    return [pscustomobject]@{process=$found;started_at=$started;path=$copy;user_sid=$user.Value;session_id=$found.SessionId}
}

function WaitRuntime {
    param([int]$Seconds)
    $watch=[Diagnostics.Stopwatch]::StartNew();$last=-1
    while($watch.Elapsed.TotalSeconds-lt$Seconds){
        $apps=@(Get-Process -Name 'smart-factory' -ErrorAction SilentlyContinue)
        $backends=@(Get-Process -Name 'SmartFactoryBackend' -ErrorAction SilentlyContinue)
        $owners=@(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue|Select-Object -ExpandProperty OwningProcess -Unique)
        if($apps.Count-ge 1-and$backends.Count-eq 1-and$owners.Count-eq 1-and$owners[0]-eq$backends[0].Id){
            $parent=Get-CimInstance Win32_Process -Filter ('ProcessId = '+$backends[0].Id)
            $main=@($apps|Where-Object Id -eq $parent.ParentProcessId)
            if($main.Count-eq 1){
                foreach($app in $apps){Need($app.Path-ieq($installRoot+'\smart-factory.exe'))'runtime-app-path';Need(-not[SflInstallToken]::IsElevated($app.Id))'runtime-app-elevated';Need([SflInstallToken]::UserSid($app.Id)-ceq[Security.Principal.WindowsIdentity]::GetCurrent().User.Value)'runtime-app-user'}
                Need($backends[0].Path-ieq($installRoot+'\resources\backend\SmartFactoryBackend.exe'))'runtime-backend-path'
                Need(-not[SflInstallToken]::IsElevated($backends[0].Id))'runtime-backend-elevated'
                Need([SflInstallToken]::UserSid($backends[0].Id)-ceq[Security.Principal.WindowsIdentity]::GetCurrent().User.Value)'runtime-backend-user'
                return [pscustomobject]@{main_pid=$main[0].Id;main_start_ticks=$main[0].StartTime.ToUniversalTime().Ticks;backend_pid=$backends[0].Id;backend_start_ticks=$backends[0].StartTime.ToUniversalTime().Ticks;app_process_count=$apps.Count}
            }
        }
        $seconds=[int]$watch.Elapsed.TotalSeconds
        if($seconds-ne$last-and($seconds%10)-eq 0){Write-Host('[STARTUP WAIT] elapsed='+$seconds+'s / '+$Seconds+'s apps='+$apps.Count+' backend='+$backends.Count);$last=$seconds}
        Start-Sleep -Seconds 1
    }
    throw 'V1026_INSTALL:startup-timeout'
}

function LocalJson {
    param([ValidateSet('health','api/spot/config','stats')][string]$Endpoint)
    $request=[Net.HttpWebRequest]::Create('http://127.0.0.1:8000/'+$Endpoint)
    $request.Method='GET';$request.Proxy=$null;$request.AllowAutoRedirect=$false;$request.Timeout=10000;$request.ReadWriteTimeout=10000
    $response=$null;$reader=$null
    try{$response=$request.GetResponse();Need([int]$response.StatusCode-eq200)'local-http';$reader=[IO.StreamReader]::new($response.GetResponseStream(),[Text.UTF8Encoding]::new($false,$true),$true);return ConvertFrom-Json -InputObject $reader.ReadToEnd()}
    finally{if($null-ne$reader){$reader.Dispose()};if($null-ne$response){$response.Dispose()}}
}

function AssertRuntimeSame {param([object]$A,[object]$B)foreach($n in @('main_pid','main_start_ticks','backend_pid','backend_start_ticks')){Need($A.$n-eq$B.$n)'runtime-changed'}}

function ImageSnapshot {
    param([object]$Runtime)
    $config=LocalJson 'api/spot/config';$image=Property $config 'image';$capture=Property $config 'image_capture'
    $stats=LocalJson 'stats';$errors=Property $stats 'errors'
    $values=[ordered]@{checked_at=[DateTimeOffset]::Now.ToString('o');runtime=$Runtime;image_status=Property $image 'image_status';image_source=Property $image 'image_source';last_success_at=Property $image 'last_success_at'}
    foreach($name in @('image_downstream_request_count','image_upstream_request_count','source_port_image_started_count','source_port_image_success_count','image_refresh_success_count','source_port_transport_failure_count','source_port_image_failure_count','image_refresh_failure_count','source_port_reuse_violation_count','source_port_bind_retry_exhaustion_count')){$values[$name]=Counter $image $name}
    $values.capture_enabled=Bool $capture 'enabled'
    foreach($name in @('enqueued_count','written_count','fact_row_count','dropped_count','failure_count')){$values['capture_'+$name]=Counter $capture $name}
    $values.http_5xx_count=Counter $stats 'total_http_5xx_count'
    $values.error_queue_size=Counter $errors 'queue_size'
    $values.error_repeat_total=Counter $errors 'repeat_total'
    $values.error_last_at=Property $errors 'last_error_at'
    return [pscustomobject]$values
}

function CompareLiveness {
    param([object]$Before,[object]$After)
    AssertRuntimeSame $Before.runtime $After.runtime
    $progress=@('image_downstream_request_count','image_upstream_request_count','source_port_image_started_count','source_port_image_success_count','image_refresh_success_count')
    if($Before.capture_enabled-and$After.capture_enabled){$progress+=@('capture_enqueued_count','capture_written_count','capture_fact_row_count')}
    $failure=@('source_port_transport_failure_count','source_port_image_failure_count','image_refresh_failure_count','source_port_reuse_violation_count','source_port_bind_retry_exhaustion_count','capture_dropped_count','capture_failure_count','http_5xx_count')
    $deltas=[ordered]@{}
    foreach($name in ($progress+$failure)){$delta=[long]$After.$name-[long]$Before.$name;Need($delta-ge0)('counter-decreased-'+$name);$deltas[$name]=$delta;if($name-cin$progress){Need($delta-gt0)('no-progress-'+$name)}else{Need($delta-eq0)('new-failure-'+$name)}}
    Need($Before.image_status-ceq'ok'-and$After.image_status-ceq'ok'-and$Before.image_source-ceq'upstream'-and$After.image_source-ceq'upstream')'image-state'
    Need($Before.error_queue_size-eq0-and$After.error_queue_size-eq0)'app-error-queue'
    Need($After.error_repeat_total-eq$Before.error_repeat_total-and$After.error_last_at-ceq$Before.error_last_at)'app-error-summary-changed'
    $b=[double]$Before.last_success_at;$a=[double]$After.last_success_at;Need(-not[double]::IsNaN($b)-and-not[double]::IsNaN($a)-and$a-gt$b)'last-success'
    return [pscustomobject]$deltas
}

if (-not $Execute) {
    [pscustomobject]@{result='V1026_INSTALL_PREPARED_NOT_EXECUTED';installation_started=$false;product_changes_made=$false;automatic_rollback_performed=$false}|ConvertTo-Json
    exit 0
}

try {
    $native=[IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
    $principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
    Need([Environment]::Is64BitProcess-and$PSVersionTable.PSEdition-ceq'Desktop'-and$PSVersionTable.PSVersion.Major-eq5-and$PSVersionTable.PSVersion.Minor-eq1-and[Diagnostics.Process]::GetCurrentProcess().MainModule.FileName-ieq$native-and$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))'native-admin-ps51'
    Need($env:APPDATA-ieq'C:\Users\user\AppData\Roaming')'operator-profile'
    $env:PATH=[Environment]::SystemDirectory+';'+[IO.Path]::GetDirectoryName($native);$env:PSModulePath=[IO.Path]::GetDirectoryName($native)+'\Modules'

    Write-Host '[STEP 1/8] Verify stopped boundary, exact stage, minimal backup and recovery installer.' -ForegroundColor Cyan
    AssertStopped
    AssertOpsRoot $opsRoot
    $null=AssertStage
    $backup=AssertBackup
    $null=MutableFileFact $configPath $configHash 2670
    $null=FileFact $recoveryInstaller $recoveryHash 150709821
    AssertStopped

    Write-Host '[STEP 2/8] Require the separate install token. No installer has started yet.' -ForegroundColor Cyan
    Write-Host '[LIMITATION] Minimal backup excludes accumulated CSV/image/fact logs, snapshots and the installed program directory.' -ForegroundColor Yellow
    $answer=Read-Host 'Type INSTALL V1.0.26 to start the exact unsigned internal installer'
    Need($answer-ceq'INSTALL V1.0.26')'operator-not-approved'

    $runs=$opsRoot+'\runs'
    if(-not[IO.Directory]::Exists($runs)){NewPrivateDirectory $runs}else{AssertPrivateAcl $runs}
    $runRoot=$runs+'\v1026-install-'+[DateTimeOffset]::Now.ToString('yyyyMMdd-HHmmss')+'-'+[Guid]::NewGuid().ToString('N').Substring(0,8)
    NewPrivateDirectory $runRoot
    $intentHash=WriteJsonNew ($runRoot+'\intent.json') ([ordered]@{schema_version='v1026-install-intent-v1';recorded_at=[DateTimeOffset]::Now.ToString('o');product_version='1.0.26';product_commit='d7a1b20f96711fb07fc7add0867e79ee36506fce';stage_receipt_sha256=$stageReceiptHash;backup_result_sha256=$backupResultHash;backup_manifest_sha256=$backupManifestHash;config_sha256=$configHash;installer_sha256=$installerHash;rollback_installer_sha256=$recoveryHash;operator_token_accepted=$true;automatic_rollback_authorized=$false;canary_observation_authorized=$false})

    $phase='interactive-installer';Write-Host '[STEP 3/8] Create an RX-only launch copy and start the installer with the same-session standard user token.' -ForegroundColor Cyan
    $launch=LaunchInstallerStandard $installer;$installerProcess=$launch.process
    Write-Host('[INSTALLER] pid='+$installerProcess.Id+' elevated=False session='+$launch.session_id)
    $wait=[Diagnostics.Stopwatch]::StartNew();$last=-1
    while(-not$installerProcess.HasExited){Need($wait.Elapsed.TotalSeconds-lt900)'installer-timeout';$s=[int]$wait.Elapsed.TotalSeconds;if($s-ne$last-and($s%10)-eq0){Write-Host('[INSTALLER WAIT] elapsed='+$s+'s / 900s pid='+$installerProcess.Id);$last=$s};Start-Sleep -Seconds 1}
    Need($installerProcess.ExitCode-eq0)'installer-exit'

    $phase='postinstall-startup';Write-Host '[STEP 4/8] Wait for exact v1.0.26 app/backend startup and verify local health identity.' -ForegroundColor Cyan
    $runtime=WaitRuntime 300
    $health=LocalJson 'health'
    Need((Property $health 'app_version')-ceq'1.0.26')'health-version'
    Need((Property (Property $health 'spot_temperature') 'build_git_commit')-ceq'd7a1b20f96711fb07fc7add0867e79ee36506fce')'health-commit'
    $null=MutableFileFact $configPath $configHash 2670

    $phase='installed-tree';Write-Host '[STEP 5/8] Verify every installed payload file and the generated uninstaller.' -ForegroundColor Cyan
    $payload=ReadJson $payloadManifest
    $tree=GetInstalledTree $installRoot $payload
    AssertRuntimeSame $runtime (WaitRuntime 5)

    $phase='image-liveness';Write-Host '[STEP 6/8] Require visible SPOT image activity, then measure local counters for 30 seconds.' -ForegroundColor Cyan
    $ready=Read-Host 'Open/keep the normal SPOT camera visible. Type READY only when the image is visibly updating'
    Need($ready-ceq'READY')'image-not-confirmed'
    $before=ImageSnapshot $runtime
    for($i=1;$i-le3;$i++){Start-Sleep -Seconds 10;Write-Host('[LIVENESS WAIT] '+($i*10)+'/30 seconds; local config counters only; no added image request')}
    $afterRuntime=WaitRuntime 5;AssertRuntimeSame $runtime $afterRuntime
    $after=ImageSnapshot $afterRuntime;$deltas=CompareLiveness $before $after

    $phase='final-binding';Write-Host '[STEP 7/8] Reverify config, installed tree and recovery candidate before publishing PASS.' -ForegroundColor Cyan
    $null=MutableFileFact $configPath $configHash 2670
    $null=FileFact $recoveryInstaller $recoveryHash 150709821
    $treeFinal=GetInstalledTree $installRoot $payload
    Need($treeFinal.tree_sha256-ceq$tree.tree_sha256)'tree-changed'
    $finalRuntime=WaitRuntime 5;AssertRuntimeSame $runtime $finalRuntime

    $phase='completion';Write-Host '[STEP 8/8] Publish installation/postinstall receipt. No Canary observation or rollback starts.' -ForegroundColor Cyan
    $result=[ordered]@{schema_version='v1026-install-postflight-result-v1';result='V1026_INSTALL_AND_30S_POSTFLIGHT_PASS';recorded_at=[DateTimeOffset]::Now.ToString('o');elapsed_seconds=$clock.Elapsed.TotalSeconds;product_version='1.0.26';product_commit='d7a1b20f96711fb07fc7add0867e79ee36506fce';release_class='UNSIGNED_INTERNAL_DEVELOPMENT';stage_receipt_sha256=$stageReceiptHash;minimal_backup_result_sha256=$backupResultHash;minimal_backup_manifest_sha256=$backupManifestHash;minimal_backup_excludes_business_logs=$true;intent_sha256=$intentHash;installer_sha256=$installerHash;installer_pid=$installerProcess.Id;installer_standard_user=$true;runtime=$finalRuntime;installed_tree=$treeFinal;config_sha256=$configHash;image_liveness_seconds=30;image_liveness_deltas=$deltas;image_visible_operator_confirmation=$true;recovery_installer_sha256=$recoveryHash;automatic_rollback_performed=$false;rollback_required=$false;fifteen_minute_observation_started=$false;full_120m_allowed=$false;production_promotion_allowed=$false;next_action='PREPARE_FRESH_V1026_15M_SERVER_BINDING_AND_UI_RESPONSIVENESS_VALIDATION';limitation='Install and 30-second local image liveness only. Minimal backup excludes CSV/image/fact logs and installed program files. Canary kit remains server-disabled pending a fresh binding helper.'}
    $resultHash=WriteJsonNew ($runRoot+'\result.json') $result
    Write-Host('[RESULT] '+$runRoot+'\result.json');Write-Host('[SHA256] '+$resultHash)
    Write-Host '[COMPLETE] v1.0.26 installed and 30-second postflight passed. Do not start a 15-minute or 120-minute Canary yet.' -ForegroundColor Green
}
catch {
    $reason='details-withheld';$exception=$_.Exception
    while($null-ne$exception){if($exception.Message-cmatch'V1026_INSTALL:([a-z0-9.-]+)'){$reason=$Matches[1];break};$exception=$exception.InnerException}
    Write-Host('[HOLD] phase='+$phase+' reason='+$reason+' elapsed='+$clock.Elapsed.ToString('hh\:mm\:ss')) -ForegroundColor Yellow
    if($null-ne$runRoot){Write-Host('[PRESERVE] '+$runRoot);try{[void](WriteJsonNew ($runRoot+'\hold.json') ([ordered]@{schema_version='v1026-install-hold-v1';result='HOLD';recorded_at=[DateTimeOffset]::Now.ToString('o');phase=$phase;reason=$reason;installer_pid=$(if($null-ne$installerProcess){$installerProcess.Id}else{$null});launch_root=$launchRoot;automatic_rollback_performed=$false;partial_files_preserved=$true}))}catch{Write-Host '[HOLD] Could not publish hold receipt; preserve console output.'}}
    Write-Host '[HOLD] No automatic retry, cleanup, rollback, app stop/start or observation. Preserve all output and current state.' -ForegroundColor Yellow
    throw 'V1026_INSTALL_HOLD: See sanitized phase and reason above.'
}
finally {
    if($null-ne$installerProcess){$installerProcess.Dispose()}
    foreach($pin in $pins){$pin.Dispose()}
    $env:PATH=$savedPath;$env:PSModulePath=$savedModules
}
