[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$PackageRoot,
    [Parameter(Mandatory=$true)][string]$ResultParent,
    [Parameter(Mandatory=$true)][ValidatePattern('^S-1-5-21-[0-9-]+$')][string]$OperatorSid
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$fieldVerifierHash = '56144abd5439b15bdd8dda8c00840d1561fdb5370bc0fdb065187eb5e176fb5e'
$fieldManifestHash = '58012882bd9ae382c741e2b5e2fc045c8fa9a7959fe273083db8b1113c43fd6b'
$fieldVerifierLength = 10449

function Assert-FieldReadCondition {
    param([bool]$Condition,[string]$Reason)
    if (-not $Condition) { throw $Reason }
}
function Get-FieldReadPlainPath {
    param([string]$Path)
    Assert-FieldReadCondition ($Path -cmatch '^[A-Za-z]:[\\/]' -and $Path -notmatch '[\x00-\x1f]') 'local-absolute-path-required'
    $full = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    Assert-FieldReadCondition ($full.Length -gt 3 -and $full.Length -le 240 -and $full.Substring(2) -notmatch ':') 'path-budget-or-stream'
    $node = [IO.FileInfo]::new($full)
    while ($null -ne $node) {
        $attributes = $node.Attributes
        Assert-FieldReadCondition ([int]$attributes -eq -1 -or ($attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'reparse-path'
        if ($node -is [IO.FileInfo]) { $node = $node.Directory } else { $node = $node.Parent }
    }
    return $full
}
function Get-FieldReadHash {
    param([IO.Stream]$Stream)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { $Stream.Position = 0; return [BitConverter]::ToString($sha.ComputeHash($Stream)).Replace('-','').ToLowerInvariant() }
    finally { $sha.Dispose() }
}
function New-FieldReadAcl {
    param([string]$ReaderSid)
    $acl = [Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true,$false)
    $acl.SetOwner([Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))
    foreach ($sid in @('S-1-5-32-544','S-1-5-18',$ReaderSid)) {
        $rights = if ($sid -ceq $ReaderSid) { 'ReadAndExecute' } else { 'FullControl' }
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
            [Security.Principal.SecurityIdentifier]::new($sid),$rights,'ContainerInherit,ObjectInherit','None','Allow'))
    }
    return $acl
}
function Assert-FieldReadAcl {
    param([string]$Path,[string]$ReaderSid)
    $null = Get-FieldReadPlainPath $Path
    $actual = [IO.Directory]::GetAccessControl($Path)
    $expected = New-FieldReadAcl $ReaderSid
    Assert-FieldReadCondition ($actual.AreAccessRulesProtected -and $actual.GetOwner([Security.Principal.SecurityIdentifier]).Value -ceq 'S-1-5-32-544') 'result-owner-inheritance'
    $rules = @($actual.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    $expectedRules = @($expected.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    Assert-FieldReadCondition ($rules.Count -eq 3) 'result-rule-count'
    $seen = @{}
    foreach ($rule in $rules) {
        $sid = $rule.IdentityReference.Value
        $matches = @($expectedRules | Where-Object { $_.IdentityReference.Value -ceq $sid })
        Assert-FieldReadCondition ($matches.Count -eq 1 -and -not $seen.ContainsKey($sid)) 'result-rule-sid'
        Assert-FieldReadCondition (-not $rule.IsInherited -and $rule.AccessControlType -eq 'Allow' -and $rule.FileSystemRights -eq $matches[0].FileSystemRights -and $rule.InheritanceFlags -eq $matches[0].InheritanceFlags -and $rule.PropagationFlags -eq 'None') 'result-rule-rights'
        $seen[$sid] = $true
    }
}
function New-FieldReadResult {
    param([string]$Parent,[string]$ReaderSid)
    $parentPath = Get-FieldReadPlainPath $Parent
    Assert-FieldReadCondition ([IO.Directory]::Exists($parentPath)) 'result-parent-missing'
    $path = Join-Path $parentPath ('r-'+[DateTimeOffset]::Now.ToString('yyyyMMdd-HHmmss')+'-'+[Guid]::NewGuid().ToString('N'))
    $null = Get-FieldReadPlainPath ($path+'\verifier.stderr.txt')
    Assert-FieldReadCondition (-not [IO.Directory]::Exists($path) -and -not [IO.File]::Exists($path)) 'result-already-exists'
    [void][IO.Directory]::CreateDirectory($path,(New-FieldReadAcl $ReaderSid))
    Assert-FieldReadAcl $path $ReaderSid
    return $path
}
function Write-FieldReadNew {
    param([string]$Path,[string]$Text)
    $null = Get-FieldReadPlainPath $Path
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes($Text)
    $stream = [IO.File]::Open($Path,'CreateNew','Write','None')
    try { $stream.Write($bytes,0,$bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
    $stream = [IO.File]::Open($Path,'Open','Read','Read')
    try { return [ordered]@{bytes=$stream.Length;sha256=(Get-FieldReadHash $stream)} } finally { $stream.Dispose() }
}
function Get-FieldReadChildCode {
    param([string]$Root,[string]$VerifierHash,[long]$VerifierLength,[string]$ManifestHash)
    $template = @'
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$stream=$null;$sha=$null;$reader=$null
try {
    $root='@@ROOT@@';$path=$root+'\verify-field-package.ps1'
    $node=[IO.FileInfo]::new($path)
    while($null -ne $node){
        if([int]$node.Attributes -eq -1 -or ($node.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){throw 'child-missing-or-reparse'}
        if($node -is [IO.FileInfo]){$node=$node.Directory}else{$node=$node.Parent}
    }
    $stream=[IO.File]::Open($path,'Open','Read','Read')
    if($stream.Length -ne @@LENGTH@@){throw 'child-verifier-length'}
    $sha=[Security.Cryptography.SHA256]::Create()
    $hash=[BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-','').ToLowerInvariant()
    if($hash -cne '@@HASH@@'){throw 'child-verifier-hash'}
    $stream.Position=0
    $reader=[IO.StreamReader]::new($stream,[Text.UTF8Encoding]::new($false,$true),$false,4096,$true)
    $block=[scriptblock]::Create($reader.ReadToEnd())
    & $block -PackageRoot $root -ExpectedManifestSha256 '@@MANIFEST@@'
    throw 'verifier-returned-without-exit'
} catch {
    [ordered]@{result='FIELD_PACKAGE_READ_CHILD_HOLD';reason=$_.Exception.Message;installation_performed=$false;canary_started=$false}|ConvertTo-Json -Compress
    exit 1
} finally {
    if($null -ne $reader){$reader.Dispose()};if($null -ne $sha){$sha.Dispose()};if($null -ne $stream){$stream.Dispose()}
}
'@
    return $template.Replace('@@ROOT@@',$Root.Replace("'","''")).Replace('@@HASH@@',$VerifierHash).Replace('@@LENGTH@@',[string]$VerifierLength).Replace('@@MANIFEST@@',$ManifestHash)
}
function Invoke-FieldReadChild {
    param([string]$Code,[int]$TimeoutMilliseconds=120000)
    $native = [IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
    $start = [Diagnostics.ProcessStartInfo]::new($native)
    $start.Arguments = '-NoLogo -NoProfile -NonInteractive -OutputFormat Text -EncodedCommand '+[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($Code))
    $start.UseShellExecute = $false; $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true; $start.RedirectStandardError = $true
    $start.StandardOutputEncoding = [Text.UTF8Encoding]::new($false); $start.StandardErrorEncoding = [Text.UTF8Encoding]::new($false)
    $start.EnvironmentVariables['PSModulePath'] = [IO.Path]::GetDirectoryName($native)+'\Modules'
    $start.EnvironmentVariables['PATH'] = [Environment]::SystemDirectory+';'+[IO.Path]::GetDirectoryName($native)
    $process = [Diagnostics.Process]::new(); $process.StartInfo = $start
    try {
        Assert-FieldReadCondition ($process.Start()) 'verification-child-start-failed'
        $childId = $process.Id; $started = $process.StartTime.ToUniversalTime().ToString('o')
        $stdout = $process.StandardOutput.ReadToEndAsync(); $stderr = $process.StandardError.ReadToEndAsync()
        $finished = $process.WaitForExit($TimeoutMilliseconds)
        if (-not $finished) { $process.Kill(); $process.WaitForExit() }
        $out = $stdout.GetAwaiter().GetResult(); $err = $stderr.GetAwaiter().GetResult()
        Assert-FieldReadCondition ($out.Length -le 2MB -and $err.Length -le 2MB) 'verification-output-budget'
        return [ordered]@{pid=$childId;started_utc=$started;actual_exit_code=$process.ExitCode;timed_out=(-not $finished);stdout=$out;stderr=$err}
    } finally { $process.Dispose() }
}

$resultRoot = $null; $held = $null
try {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    $native = [IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
    Assert-FieldReadCondition ([Environment]::Is64BitProcess -and $PSVersionTable.PSEdition -ceq 'Desktop' -and $PSVersionTable.PSVersion.Major -eq 5 -and $PSVersionTable.PSVersion.Minor -eq 1 -and [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName -ieq $native) 'native-powershell-5.1-x64-required'
    Assert-FieldReadCondition ($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) 'administrator-required'
    $root = Get-FieldReadPlainPath $PackageRoot
    $parent = Get-FieldReadPlainPath $ResultParent
    Assert-FieldReadCondition ([IO.Directory]::Exists($root) -and $parent -ine $root -and -not $parent.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase)) 'package-or-result-boundary'
    $verifier = Get-FieldReadPlainPath (Join-Path $root 'verify-field-package.ps1')
    $held = [IO.File]::Open($verifier,'Open','Read','Read')
    Assert-FieldReadCondition ($held.Length -eq $fieldVerifierLength -and (Get-FieldReadHash $held) -ceq $fieldVerifierHash) 'parent-verifier-identity'
    $resultRoot = New-FieldReadResult $parent $OperatorSid
    $code = Get-FieldReadChildCode $root $fieldVerifierHash $fieldVerifierLength $fieldManifestHash
    $child = Invoke-FieldReadChild $code
    $files = [ordered]@{}
    foreach ($name in @('stdout','stderr')) { $files['verifier.'+$name+'.txt'] = Write-FieldReadNew ($resultRoot+'\verifier.'+$name+'.txt') $child[$name] }
    $passed = $false; $parsed = $null; $reason = 'child-exit-timeout-or-stderr'
    if ($child.actual_exit_code -eq 0 -and -not $child.timed_out -and [string]::IsNullOrEmpty($child.stderr)) {
        try {
            $parsed = $child.stdout | ConvertFrom-Json
            Assert-FieldReadCondition ($parsed.result -ceq 'FIELD_PACKAGE_BYTES_AND_IDENTITIES_VERIFIED' -and $parsed.manifest_sha256 -ceq $fieldManifestHash -and $parsed.files_verified -eq 26 -and $parsed.release_gate -ceq 'HOLD') 'child-result-contract'
            foreach ($name in @('installed_tree_verified','installation_performed','canary_started','promotion_allowed')) { Assert-FieldReadCondition ($parsed.$name -is [bool] -and -not $parsed.$name) 'child-result-scope' }
            $passed = $true; $reason = 'PACKAGE_BYTES_ONLY'
        } catch { $reason = $_.Exception.Message }
    }
    $record = [ordered]@{schema_version='sfl-field-package-read-v1';result=$(if($passed){'FIELD_PACKAGE_READ_VERIFIED'}else{'FIELD_PACKAGE_READ_HOLD'});reason=$reason;
        recorded_utc=[DateTimeOffset]::UtcNow.ToString('o');computer=[Environment]::MachineName;user_sid=$identity.User.Value;
        package_root=$root;verifier_sha256=$fieldVerifierHash;manifest_sha256=$fieldManifestHash;child_pid=$child.pid;
        child_started_utc=$child.started_utc;child_exit_code=$child.actual_exit_code;child_timed_out=$child.timed_out;
        package_verification=$parsed;installation_performed=$false;field_qa_executed=$false;canary_started=$false;promotion_allowed=$false;release_gate='HOLD'}
    $files['result.json'] = Write-FieldReadNew ($resultRoot+'\result.json') ($record | ConvertTo-Json -Depth 8)
    Assert-FieldReadAcl $resultRoot $OperatorSid
    $manifest = Write-FieldReadNew ($resultRoot+'\manifest.json') ([ordered]@{schema_version='sfl-field-read-result-manifest-v1';files=$files} | ConvertTo-Json -Depth 5)
    Write-Host ('RESULT_PATH='+$resultRoot)
    Write-Host ('MANIFEST_SHA256='+$manifest.sha256)
    [ordered]@{result=$record.result;result_path=$resultRoot;manifest_sha256=$manifest.sha256;child_exit_code=$child.actual_exit_code;release_gate='HOLD'} | ConvertTo-Json -Compress
    if (-not $passed) { exit 1 }
    exit 0
} catch {
    [ordered]@{result='FIELD_PACKAGE_READ_HOLD';reason=$_.Exception.Message;partial_result_path=$resultRoot;installation_performed=$false;canary_started=$false;release_gate='HOLD'} | ConvertTo-Json -Compress
    exit 1
} finally { if ($null -ne $held) { $held.Dispose() } }
