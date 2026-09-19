[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($PSVersionTable.PSEdition -cne 'Desktop' -or $PSVersionTable.PSVersion.ToString() -notlike '5.1.*' -or -not [Environment]::Is64BitProcess){throw 'Native PS5.1 x64 required.'}
function Build-Hash {
    param([byte[]]$Bytes)
    $sha=[Security.Cryptography.SHA256]::Create()
    try{return [BitConverter]::ToString($sha.ComputeHash($Bytes)).Replace('-','')}finally{$sha.Dispose()}
}
function Build-NewFile {
    param([string]$Path,[byte[]]$Bytes)
    $s=[IO.File]::Open($Path,'CreateNew','Write','Read')
    try{$s.Write($Bytes,0,$Bytes.Length);$s.Flush($true)}finally{$s.Dispose()}
    $read=[IO.File]::ReadAllBytes($Path)
    if($read.Length -ne $Bytes.Length -or (Build-Hash $read) -cne (Build-Hash $Bytes)){throw 'Generated file readback mismatch.'}
}
$workspace=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$output=Join-Path $workspace 'artifacts\server-acl-repair-r2'
$node=[IO.DirectoryInfo]::new([IO.Path]::GetDirectoryName($output))
while($null -ne $node){
    if($node.Exists -and ($node.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){throw 'Build output ancestor is a reparse point.'}
    $node=$node.Parent
}
if([IO.Directory]::Exists($output) -or [IO.File]::Exists($output)){throw 'Delivery already exists; preserve it, do not overwrite.'}
$existingZip=Join-Path $workspace 'artifacts\server-cleanup-release-pair-r1\v1019-release-pair-cleanup-ready-r1.zip'
$bytes=[IO.File]::ReadAllBytes($existingZip)
if($bytes.Length -ne 22604 -or (Build-Hash $bytes) -cne '62CCE5F9B9E020FE859ABEA2977EAF366A0945C5C402B2839632C00A952065F3'){throw 'Existing dependency ZIP differs.'}
$helper=[IO.File]::ReadAllBytes((Join-Path $PSScriptRoot 'repair-sflops-acl.ps1'))
$helperHash=Build-Hash $helper
$template=[IO.File]::ReadAllText((Join-Path $PSScriptRoot 'acl-repair-launch.template.txt'),[Text.UTF8Encoding]::new($false,$true))
$launcher=$template.Replace('@@SHA256@@',$helperHash).Replace('@@LENGTH@@',[string]$helper.Length)
if($launcher.Contains('@@')){throw 'Unresolved launcher placeholder.'}
$utf8=[Text.UTF8Encoding]::new($false,$true)
foreach($code in @($utf8.GetString($helper),$launcher)){
    $t=$null;$e=$null;$null=[Management.Automation.Language.Parser]::ParseInput($code,[ref]$t,[ref]$e)
    if(@($e).Count -ne 0){throw 'Native parser rejected helper/launcher.'}
}
$null=[IO.Directory]::CreateDirectory($output)
Build-NewFile (Join-Path $output 'repair-sflops-acl-r2.ps1') $helper
Build-NewFile (Join-Path $output 'repair-sflops-acl-r2.ps1.sha256.txt') ([Text.Encoding]::ASCII.GetBytes($helperHash+"`n"))
Build-NewFile (Join-Path $output 'RUN_ACL_REPAIR.txt') ($utf8.GetBytes($launcher))
Build-NewFile (Join-Path $output 'ACL_REPAIR_GUIDE.md') ([IO.File]::ReadAllBytes((Join-Path $PSScriptRoot 'ACL_REPAIR_GUIDE.md')))
$files=@(Get-ChildItem -LiteralPath $output -File|ForEach-Object {[pscustomobject]@{name=$_.Name;length=$_.Length;sha256=(Build-Hash ([IO.File]::ReadAllBytes($_.FullName)))}})
$result=[pscustomobject]@{result='SFLOPS_ACL_REPAIR_DELIVERY_PREPARED_NOT_SERVER_EXECUTED';generated_at=[DateTimeOffset]::Now.ToString('o');
    directory=$output;files=$files;existing_dependency_zip_sha256='62CCE5F9B9E020FE859ABEA2977EAF366A0945C5C402B2839632C00A952065F3';
    new_files_to_transfer=@('repair-sflops-acl-r2.ps1','repair-sflops-acl-r2.ps1.sha256.txt');
    server_acl_changes_made=$false;cleanup_retried=$false;production_code_changed=$false}
Build-NewFile (Join-Path $output 'build-result.json') ($utf8.GetBytes(($result|ConvertTo-Json -Depth 6)))
$result|ConvertTo-Json -Depth 6
