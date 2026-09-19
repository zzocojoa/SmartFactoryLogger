[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($PSVersionTable.PSEdition -cne 'Desktop' -or $PSVersionTable.PSVersion.ToString() -notlike '5.1.*' -or -not [Environment]::Is64BitProcess){throw 'Native PS5.1 x64 required.'}
$checks=[Collections.Generic.List[string]]::new()
function Check {param([bool]$Ok,[string]$Name) if(-not $Ok){throw $Name};$checks.Add($Name)}
function HashBytes {param([byte[]]$Bytes) $sha=[Security.Cryptography.SHA256]::Create();try{return [BitConverter]::ToString($sha.ComputeHash($Bytes)).Replace('-','')}finally{$sha.Dispose()}}
$template=[IO.File]::ReadAllText((Join-Path $PSScriptRoot 'acl-repair-launch.template.txt'))
$parsed=$template.Replace('@@LENGTH@@','1').Replace('@@SHA256@@',('0'*64))
$t=$null;$e=$null;$ast=[Management.Automation.Language.Parser]::ParseInput($parsed,[ref]$t,[ref]$e)
Check (@($e).Count -eq 0) 'Native outer launcher parser'
$childNodes=@($ast.FindAll({param($n) $n -is [Management.Automation.Language.StringConstantExpressionAst] -and $n.Value.StartsWith('Set-StrictMode -Version Latest')},$true))
Check ($childNodes.Count -eq 1) 'One fixed child bootstrap'
$child=$childNodes[0].Value
$t=$null;$e=$null;$null=[Management.Automation.Language.Parser]::ParseInput($child,[ref]$t,[ref]$e)
Check (@($e).Count -eq 0) 'Native child bootstrap parser'
Check ($parsed.Contains('-NoProfile -NonInteractive -OutputFormat Text') -and $parsed.Contains('-EncodedCommand $encoded') -and $parsed -notmatch '(?m)^\s*& \$native .* -File ') 'Fresh text-output child, no path reopen execution'
Check ($child.Contains('$verifiedSha.ComputeHash($verifiedStream)') -and $child.Contains('$verifiedStream.Position=0') -and $child.Contains('$verifiedBlock=[scriptblock]::Create($verifiedReader.ReadToEnd())') -and $child.Contains('& $verifiedBlock -Execute')) 'Same stream hash then ScriptBlock execution'
$workspace=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$fixture=Join-Path $workspace ('.tmp\acl-launch-tests-'+[Guid]::NewGuid().ToString('N'))
if(-not $fixture.StartsWith($workspace+'\.tmp\',[StringComparison]::OrdinalIgnoreCase)){throw 'Fixture scope mismatch.'}
$null=[IO.Directory]::CreateDirectory($fixture)
$native=[IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
$text='param([switch]$Execute); if(-not $Execute){throw "Missing test Execute"}; Write-Host "FIXTURE_PROGRESS"; Write-Output "FIXTURE_VERIFIED_EXECUTE"'
$payload=[Text.Encoding]::ASCII.GetBytes($text)
foreach($mode in @('exact','hash-mismatch','length-mismatch','invalid-utf8')){
    $bytes=$payload
    if($mode -ceq 'invalid-utf8'){$bytes=[byte[]]@(255,255,255)}
    $path=Join-Path $fixture ($mode+'.ps1')
    $s=[IO.File]::Open($path,'CreateNew','Write','None');try{$s.Write($bytes,0,$bytes.Length);$s.Flush($true)}finally{$s.Dispose()}
    $length=$bytes.Length;$hash=HashBytes $bytes
    if($mode -ceq 'length-mismatch'){$length++}
    if($mode -ceq 'hash-mismatch'){$hash='0'*64}
    $code=$child.Replace("'C:\Users\user\Desktop\SmartFactory\repair-sflops-acl-r2.ps1'",("'"+$path.Replace("'","''")+"'"))
    $code=$code.Replace('$verifiedStream.Length -ne 1',('$verifiedStream.Length -ne '+$length)).Replace(('0'*64),$hash)
    if($code.Contains('C:\Users\user\Desktop\SmartFactory')){throw 'Server path remained in synthetic test.'}
    $encoded=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($code))
    $output=@(& $native -NoLogo -NoProfile -NonInteractive -OutputFormat Text -ExecutionPolicy Bypass -EncodedCommand $encoded)
    $exitCode=$LASTEXITCODE
    $matched=@($output|Where-Object {[string]$_ -ceq 'FIXTURE_VERIFIED_EXECUTE'}).Count
    if($mode -ceq 'exact'){
        Check ($exitCode -eq 0 -and $matched -eq 1) 'Exact locked fixture bytes execute in child'
        Check (@($output|Where-Object {[string]$_ -ceq 'FIXTURE_PROGRESS'}).Count -eq 1) 'Child progress prints as plain text'
    }
    else{Check ($exitCode -eq 1 -and $matched -eq 0) ('Fixture never executes on '+$mode)}
}
[pscustomobject]@{result='ACL_REPAIR_BYTE_BOUND_LAUNCH_TEST_PASS';assertions=$checks.Count;checks=$checks.ToArray();
    fixture=$fixture;actual_server_helper_executed=$false;server_paths_used=$false}|ConvertTo-Json -Depth 5
