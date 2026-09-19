[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$OutputDirectory)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$workspace=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$output=[IO.Path]::GetFullPath($OutputDirectory)
if(-not $output.StartsWith($workspace+'\artifacts\',[StringComparison]::OrdinalIgnoreCase) -or
    [IO.Directory]::Exists($output) -or [IO.File]::Exists($output)){throw 'Use a new build output child under workspace artifacts.'}
$node=[IO.Directory]::GetParent($output)
while($null -ne $node){
    if($node.Exists -and ($node.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){throw 'Build output ancestor is a reparse point.'}
    $node=$node.Parent
}
$expectedRead='EBEB041A42D0FC2232ADCDDA13547C8151209C22E8D85F1B1B1D70D7021A1765'
if((Get-FileHash -LiteralPath (Join-Path $PSScriptRoot 'read-quarantine-pre-v1020.ps1')).Hash -cne $expectedRead){throw 'Published read-only helper changed.'}
$coreHash=(Get-FileHash -LiteralPath (Join-Path $PSScriptRoot 'cleanup-archive-core.ps1')).Hash
$main=[IO.File]::ReadAllText((Join-Path $PSScriptRoot 'cleanup-pre-v1020.ps1'))
if(-not $main.Contains("@('cleanup-archive-core.ps1','$coreHash')") -or $main.Contains('CORE_HASH_PENDING')){throw 'Core dependency pin is stale.'}
$names=@('cleanup-pre-v1020.ps1','cleanup-archive-core.ps1','read-quarantine-pre-v1020.ps1','CLEANUP_GUIDE.md')
$null=[IO.Directory]::CreateDirectory($output)
$zipPath=Join-Path $output 'pre-v1020-duplicate-cleanup-ready-r1.zip'
Add-Type -AssemblyName System.IO.Compression
$file=[IO.File]::Open($zipPath,'CreateNew','ReadWrite','None');$zip=[IO.Compression.ZipArchive]::new($file,'Create',$true)
$entries=@()
try {
    foreach($name in $names){
        $bytes=[IO.File]::ReadAllBytes((Join-Path $PSScriptRoot $name))
        $entry=$zip.CreateEntry($name);$stream=$entry.Open()
        try{$stream.Write($bytes,0,$bytes.Length)}finally{$stream.Dispose()}
        $entries+=[pscustomobject]@{name=$name;length=$bytes.Length;sha256=(Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $name)).Hash}
    }
}finally{$zip.Dispose();$file.Dispose()}
$file=[IO.File]::Open($zipPath,'Open','Read','Read');$zip=[IO.Compression.ZipArchive]::new($file,'Read',$true)
try {
    if($zip.Entries.Count -ne $names.Count){throw 'Final transfer count differs.'}
    foreach($spec in $entries){
        $found=@($zip.Entries|Where-Object FullName -ceq $spec.name)
        if($found.Count -ne 1 -or $found[0].Length -ne $spec.length){throw 'Final transfer entry differs.'}
        $s=$found[0].Open();$sha=[Security.Cryptography.SHA256]::Create()
        try{$hash=[BitConverter]::ToString($sha.ComputeHash($s)).Replace('-','')}finally{$sha.Dispose();$s.Dispose()}
        if($hash -cne $spec.sha256){throw 'Final transfer entry hash differs.'}
    }
}finally{$zip.Dispose();$file.Dispose()}
$hash=(Get-FileHash -LiteralPath $zipPath).Hash;$length=[IO.FileInfo]::new($zipPath).Length
$utf8=[Text.UTF8Encoding]::new($false)
[IO.File]::WriteAllText(($zipPath+'.sha256.txt'),$hash+"`n",$utf8)
$launcher=[IO.File]::ReadAllText((Join-Path $PSScriptRoot 'cleanup-launch.template.txt')).Replace('__ZIP_HASH__',$hash).Replace('__ZIP_LENGTH__',[string]$length)
$tokens=$null;$errors=$null;$null=[Management.Automation.Language.Parser]::ParseInput($launcher,[ref]$tokens,[ref]$errors)
if(@($errors).Count -ne 0){throw 'Final launcher syntax error.'}
[IO.File]::WriteAllText((Join-Path $output 'RUN_CLEANUP.txt'),$launcher,$utf8)
$receipt=[pscustomobject]@{result='CLEANUP_TRANSFER_REOPENED_ALL_ENTRIES_VERIFIED';created_at=[DateTimeOffset]::Now.ToString('o');
    zip=$zipPath;length=$length;sha256=$hash;entries=$entries;launcher_sha256=(Get-FileHash -LiteralPath (Join-Path $output 'RUN_CLEANUP.txt')).Hash;
    server_execution_performed=$false;tooling_status='LOCAL_PREPARATION_NOT_COMMITTED'}
[IO.File]::WriteAllText((Join-Path $output 'build-result.json'),($receipt|ConvertTo-Json -Depth 8),$utf8)
$receipt | ConvertTo-Json -Depth 8
