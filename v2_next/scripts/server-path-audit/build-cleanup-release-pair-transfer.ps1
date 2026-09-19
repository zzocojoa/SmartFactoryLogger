[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$OutputDirectory)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($PSVersionTable.PSEdition -cne 'Desktop' -or $PSVersionTable.PSVersion.ToString() -notlike '5.1.*' -or -not [Environment]::Is64BitProcess){throw 'Native Windows PowerShell 5.1 x64 required.'}
$workspace=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$output=[IO.Path]::GetFullPath($OutputDirectory)
if(-not $output.StartsWith($workspace+'\artifacts\',[StringComparison]::OrdinalIgnoreCase) -or
    [IO.Directory]::Exists($output) -or [IO.File]::Exists($output)){throw 'Use a NEW child directory under workspace artifacts.'}
$node=[IO.Directory]::GetParent($output)
while($null -ne $node){
    if($node.Exists -and ($node.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){throw 'Reparse output ancestor.'}
    $node=$node.Parent
}
$pins=@{
    'read-quarantine-pre-v1020.ps1'='EBEB041A42D0FC2232ADCDDA13547C8151209C22E8D85F1B1B1D70D7021A1765'
    'cleanup-archive-core.ps1'='CD9F2387581C52FA9A26EC6E217909919F472CB5DF9853C2E96A2A368FF40A28'
    'cleanup-launch.template.txt'='E0E2088A05253BE6719597EA7270F56818C8F7FAF1DB45391DFEEFB77D83FD04'
}
function ByteHash {param([byte[]]$Bytes) $s=[Security.Cryptography.SHA256]::Create();try{return [BitConverter]::ToString($s.ComputeHash($Bytes)).Replace('-','')}finally{$s.Dispose()}}
function ParseCheck {param([string]$Code) $t=$null;$e=$null;$null=[Management.Automation.Language.Parser]::ParseInput($Code,[ref]$t,[ref]$e);if(@($e).Count -ne 0){throw 'Native PowerShell parse failed.'}}
$utf8=[Text.UTF8Encoding]::new($false,$true)
$names=@('cleanup-v1019-release-pair.ps1','cleanup-archive-core.ps1','read-quarantine-pre-v1020.ps1','RELEASE_PAIR_CLEANUP_GUIDE.md')
$bytesByName=@{};$entries=@()
foreach($name in (@($names)+@('cleanup-launch.template.txt'))){
    $bytes=[IO.File]::ReadAllBytes((Join-Path $PSScriptRoot $name));$hash=ByteHash $bytes
    if($pins.ContainsKey($name) -and $hash -cne $pins[$name]){throw ('Published dependency/template changed: '+$name)}
    $bytesByName[$name]=$bytes
    if($name -cin $names){$entries+=[pscustomobject]@{name=$name;length=$bytes.Length;sha256=$hash}}
    if($name.EndsWith('.ps1')){ParseCheck ($utf8.GetString($bytes))}
}
$main=$utf8.GetString($bytesByName['cleanup-v1019-release-pair.ps1'])
foreach($name in @('read-quarantine-pre-v1020.ps1','cleanup-archive-core.ps1')){
    if(-not $main.Contains("@('$name','$($pins[$name])')")){throw 'Main dependency pin stale.'}
}
$null=[IO.Directory]::CreateDirectory($output)
$zipName='v1019-release-pair-cleanup-ready-r1.zip';$zipPath=Join-Path $output $zipName
Add-Type -AssemblyName System.IO.Compression
$file=[IO.File]::Open($zipPath,'CreateNew','ReadWrite','None');$zip=[IO.Compression.ZipArchive]::new($file,'Create',$true)
try{foreach($name in $names){$entry=$zip.CreateEntry($name);$s=$entry.Open();try{$b=$bytesByName[$name];$s.Write($b,0,$b.Length)}finally{$s.Dispose()}}}finally{$zip.Dispose();$file.Dispose()}
$file=[IO.File]::Open($zipPath,'Open','Read','Read');$zip=[IO.Compression.ZipArchive]::new($file,'Read',$true)
try{
    if($zip.Entries.Count -ne 4){throw 'Transfer count differs.'}
    foreach($spec in $entries){
        $matches=@($zip.Entries|Where-Object FullName -CEQ $spec.name)
        if($matches.Count -ne 1 -or $matches[0].Length -ne $spec.length){throw 'Transfer entry length/name differs.'}
        $s=$matches[0].Open();$sha=[Security.Cryptography.SHA256]::Create()
        try{$hash=[BitConverter]::ToString($sha.ComputeHash($s)).Replace('-','')}finally{$sha.Dispose();$s.Dispose()}
        if($hash -cne $spec.sha256){throw 'Reopened transfer entry bytes differ.'}
    }
}finally{$zip.Dispose();$file.Dispose()}
$zipHash=(Get-FileHash -LiteralPath $zipPath).Hash;$length=[IO.FileInfo]::new($zipPath).Length
[IO.File]::WriteAllText(($zipPath+'.sha256.txt'),$zipHash+"`n",$utf8)
# Same reviewed launcher control flow; exact named replacements only, then native AST check.
$launcher=$utf8.GetString($bytesByName['cleanup-launch.template.txt'])
$replacements=[ordered]@{
    'pre-v1020-duplicate-cleanup-ready-r1.zip'=$zipName
    'cleanup-pre-v1020.ps1'='cleanup-v1019-release-pair.ps1'
    'CLEANUP_GUIDE.md'='RELEASE_PAIR_CLEANUP_GUIDE.md'
    'q20-helper-'='q19-pair-helper-'
    '[LAUNCH] Approved cleanup: only complete ZIP-backed duplicate folders in the fixed old quarantine. No app changes.'='[LAUNCH] Approved cleanup: delete only 22 R1 duplicate files; retain R2_clean and BOTH unique JSONs. No directory or app changes.'
    '__ZIP_HASH__'=$zipHash
    '__ZIP_LENGTH__'=[string]$length
}
foreach($key in $replacements.Keys){if(-not $launcher.Contains($key)){throw 'Launcher template replacement missing.'};$launcher=$launcher.Replace($key,$replacements[$key])}
if($launcher -match '__ZIP_|cleanup-pre-v1020\.ps1|q20-helper-|pre-v1020-duplicate-cleanup-ready-r1'){throw 'Stale launcher fields.'}
ParseCheck $launcher
if(-not $launcher.Contains("-File (Join-Path `$helperRoot 'cleanup-v1019-release-pair.ps1') -Execute")){throw 'Wrong launcher target/mode.'}
[IO.File]::WriteAllText((Join-Path $output 'RUN_RELEASE_PAIR_CLEANUP.txt'),$launcher,$utf8)
$receipt=[pscustomobject]@{result='RELEASE_PAIR_TRANSFER_REOPENED_ALL_ENTRIES_VERIFIED';created_at=[DateTimeOffset]::Now.ToString('o');
    zip=$zipPath;length=$length;sha256=$zipHash;entries=$entries;
    launcher_sha256=(Get-FileHash -LiteralPath (Join-Path $output 'RUN_RELEASE_PAIR_CLEANUP.txt')).Hash;
    server_execution_performed=$false;tooling_status='LOCAL_PREPARATION_NOT_COMMITTED'}
[IO.File]::WriteAllText((Join-Path $output 'build-result.json'),($receipt|ConvertTo-Json -Depth 8),$utf8)
$receipt|ConvertTo-Json -Depth 8
