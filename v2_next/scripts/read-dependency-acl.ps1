# Read-only snapshot of the eight approved roots; no recursive ACL or product changes.
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$checkout=Join-Path ([Environment]::GetFolderPath('UserProfile')) 'Desktop\SmartFactoryLogger_Builds\spot-tcp-connection-reuse-remediation_bfd9be7\source'
$run=Join-Path $repo '.tmp\dep-428c970f-1f0e-4127-802c-7b4ba9d621c0'
$roots=[ordered]@{
    'old-node'=(Join-Path $checkout 'v2_next\node_modules');'old-frontend'=(Join-Path $checkout 'v2_next\frontend\node_modules')
    'old-python'=(Join-Path $checkout 'v2_next\backend\.venv');'old-browsers'=(Join-Path $checkout 'v2_next\backend\browsers')
    'test-node'=(Join-Path $run 'node\node_modules');'test-frontend'=(Join-Path $run 'frontend\node_modules')
    'test-python'=(Join-Path $run 'venv');'test-node-cache'=(Join-Path $run 'temp\node-compile-cache')
}
$trusted=@('S-1-5-18','S-1-5-32-544',[Security.Principal.WindowsIdentity]::GetCurrent().User.Value)
$result=foreach($key in $roots.Keys){
    $path=$roots[$key];$acl=Get-Acl -LiteralPath $path
    $outside=foreach($rule in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])){
        if($rule.AccessControlType-eq'Allow'-and($rule.PropagationFlags-band[Security.AccessControl.PropagationFlags]::InheritOnly)-eq 0-and$rule.IdentityReference.Value-cnotin$trusted-and([int]$rule.FileSystemRights-band 0xD0156)-ne 0){
            $account=$null;try{$account=$rule.IdentityReference.Translate([Security.Principal.NTAccount]).Value}catch [Security.Principal.IdentityNotMappedException]{}
            [pscustomobject]@{sid=$rule.IdentityReference.Value;account=$account;rights=[string]$rule.FileSystemRights;inherited=$rule.IsInherited}
        }
    }
    [pscustomobject]@{id=$key;path=$path;owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value;sddl=$acl.Sddl;outside_writers=@($outside)}
}
[pscustomobject]@{at=[DateTimeOffset]::Now.ToString('o');roots=@($result);acl_writes=0;deleted_files=0;remote_server_operations=0}|ConvertTo-Json -Depth 8 -Compress
