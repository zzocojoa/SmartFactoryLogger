[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ValidationResult,
    [Parameter(Mandatory=$true)][string]$EngineAssembly,
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-F0-9]{64}$')][string]$ExpectedValidationSha256,
    [Parameter(Mandatory=$true)][string]$OutputRoot
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

function HashFile{param([string]$Path)(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash}
function Fact{param([string]$Path)$item=Get-Item -LiteralPath $Path -ErrorAction Stop;[pscustomobject]@{name=$item.Name;length=[long]$item.Length;sha256=HashFile $item.FullName;path=$item.FullName}}
$pins=[Collections.Generic.List[IDisposable]]::new()
function ReadPinnedValidation {
    param([string]$Path,[string]$ExpectedHash)
    $stream=[IO.File]::Open($Path,'Open','Read','Read');$pins.Add($stream)
    if($stream.Length-gt1048576){throw 'Validation receipt exceeds bound'}
    $sha=[Security.Cryptography.SHA256]::Create()
    try{$actual=[BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-','')}finally{$sha.Dispose()}
    if($actual-cne$ExpectedHash){throw 'Validation receipt differs from external pin.'}
    $stream.Position=0
    $reader=[IO.StreamReader]::new($stream,[Text.UTF8Encoding]::new($false,$true),$true,4096,$true)
    try{return ($reader.ReadToEnd()|ConvertFrom-Json)}finally{$reader.Dispose()}
}
function AssertCopiedHelper {
    param([string]$Path,[string]$ValidatedHash)
    $hash=HashFile $Path
    if($hash-cne$ValidatedHash){throw 'Copied helper differs from tested bytes.'}
    return $hash
}

try {
$helper=Join-Path $PSScriptRoot 'install-v1026-after-minimal-backup-r2.ps1'
$guide=Join-Path $PSScriptRoot 'V1026_INSTALL_R2_GUIDE.md'
$engine=[IO.Path]::GetFullPath($EngineAssembly)
if(-not[IO.File]::Exists($engine)-or(Get-Item -LiteralPath $engine).Length-ne19456-or(HashFile $engine)-cne'3B8B3649C623EB8A7112C762D95A00AD9745231291C50CCC2B66E0AA2C7F8A71'){throw'Existing pinned backup engine DLL required'}
$validation=[IO.Path]::GetFullPath($ValidationResult)
$output=[IO.Path]::GetFullPath($OutputRoot)
if([IO.File]::Exists($output)-or[IO.Directory]::Exists($output)){throw'OutputRoot already exists and is preserved.'}
foreach($path in @($helper,$guide,$validation)){if(-not[IO.File]::Exists($path)){throw('Required file missing: '+$path)}}
$review=ReadPinnedValidation $validation $ExpectedValidationSha256
if($review.result-cne'V1026_INSTALL_R2_COLD_BOUNDARY_TEST_PASS'-or
    $review.helper_sha256-cne(HashFile $helper)-or $review.assertions-lt34-or
    $review.engine_source_sha256-cne(HashFile (Join-Path $PSScriptRoot 'cold-backup-core.cs'))-or
    $review.server_main_executed-isnot[bool]-or$review.server_main_executed-or
    $review.installer_started-isnot[bool]-or$review.installer_started-or
    $review.network_queries-isnot[bool]-or$review.network_queries){throw'Validation result does not authorize r2 packaging.'}

[void][IO.Directory]::CreateDirectory($output)
$files=Join-Path $output 'transfer-files';[void][IO.Directory]::CreateDirectory($files)
$helperTarget=Join-Path $files 'install-v1026-after-minimal-backup-r2.ps1'
$guideTarget=Join-Path $files 'V1026_INSTALL_R2_GUIDE.md'
[IO.File]::Copy($helper,$helperTarget,$false);[IO.File]::Copy($guide,$guideTarget,$false)
$engineTarget=Join-Path $files 'cold-backup-core.dll'
[IO.File]::Copy($engine,$engineTarget,$false)
if((HashFile $engineTarget)-cne'3B8B3649C623EB8A7112C762D95A00AD9745231291C50CCC2B66E0AA2C7F8A71'){throw'Copied engine DLL differs'}
$helperHash=AssertCopiedHelper $helperTarget $review.helper_sha256
[IO.File]::WriteAllText($helperTarget+'.sha256.txt',$helperHash+"`n",[Text.Encoding]::ASCII)
$facts=@(Fact $helperTarget;Fact($helperTarget+'.sha256.txt');Fact $guideTarget;Fact $engineTarget)
if($facts[0].sha256-cne$review.helper_sha256){throw 'ZIP helper fact differs from tested bytes.'}
$zip=Join-Path $output 'v1026-install-after-minimal-backup-ready-r2.zip'
Add-Type -AssemblyName System.IO.Compression
$stream=[IO.File]::Open($zip,'CreateNew','ReadWrite','None')
try{
    $archive=[IO.Compression.ZipArchive]::new($stream,[IO.Compression.ZipArchiveMode]::Create,$true)
    try{
        foreach($fact in $facts){
            $entry=$archive.CreateEntry($fact.name,[IO.Compression.CompressionLevel]::Optimal)
            $input=[IO.File]::OpenRead($fact.path);$target=$entry.Open()
            try{$input.CopyTo($target)}finally{$target.Dispose();$input.Dispose()}
        }
    }finally{$archive.Dispose()}
    $stream.Flush($true)
}finally{$stream.Dispose()}

$zipHash=HashFile $zip;$zipLength=(Get-Item -LiteralPath $zip).Length
[IO.File]::WriteAllText($zip+'.sha256.txt',$zipHash+"`n",[Text.Encoding]::ASCII)
$pin=[IO.File]::Open($zip,'Open','Read','Read');$archive=$null
try{
    $archive=[IO.Compression.ZipArchive]::new($pin,'Read',$true)
    if($archive.Entries.Count-ne$facts.Count){throw'ZIP entry count mismatch.'}
    foreach($fact in $facts){
        $matches=@($archive.Entries|Where-Object FullName -CEQ $fact.name)
        if($matches.Count-ne1-or$matches[0].Length-ne$fact.length){throw('ZIP entry mismatch: '+$fact.name)}
        $entryStream=$matches[0].Open();$sha=[Security.Cryptography.SHA256]::Create()
        try{$actual=[BitConverter]::ToString($sha.ComputeHash($entryStream)).Replace('-','')}finally{$sha.Dispose();$entryStream.Dispose()}
        if($actual-cne$fact.sha256){throw('ZIP entry hash mismatch: '+$fact.name)}
    }
}finally{if($null-ne$archive){$archive.Dispose()};$pin.Dispose()}

$result=[pscustomobject]@{result='V1026_INSTALL_R2_TRANSFER_PREPARED_NOT_SERVER_AUTHORIZED';zip=[pscustomobject]@{path=$zip;length=[long]$zipLength;sha256=$zipHash};entries=$facts|Select-Object name,length,sha256;validation_sha256=$ExpectedValidationSha256;helper_sha256=$helperHash;zip_closed_reopened_all_entries_rehashed=$true;server_execution_authorized=$false;installation_started=$false;product_changes_made=$false;automatic_rollback_performed=$false}
$json=$result|ConvertTo-Json -Depth 8
[IO.File]::WriteAllText((Join-Path $output 'build-result.json'),$json,[Text.UTF8Encoding]::new($false))
$json
} finally {foreach($pin in $pins){$pin.Dispose()}}
