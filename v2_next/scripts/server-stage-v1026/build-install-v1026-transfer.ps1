[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ValidationResult,
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-F0-9]{64}$')][string]$ExpectedValidationSha256,
    [Parameter(Mandatory=$true)][string]$OutputRoot
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

function HashFile{param([string]$Path)(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash}
function Fact{param([string]$Path)$item=Get-Item -LiteralPath $Path -ErrorAction Stop;[pscustomobject]@{name=$item.Name;length=[long]$item.Length;sha256=HashFile $item.FullName;path=$item.FullName}}

$helper=Join-Path $PSScriptRoot 'install-v1026-after-minimal-backup.ps1'
$guide=Join-Path $PSScriptRoot 'V1026_INSTALL_AFTER_MINIMAL_BACKUP_GUIDE.md'
$validation=[IO.Path]::GetFullPath($ValidationResult)
$output=[IO.Path]::GetFullPath($OutputRoot)
if([IO.File]::Exists($output)-or[IO.Directory]::Exists($output)){throw'OutputRoot already exists and is preserved.'}
foreach($path in @($helper,$guide,$validation)){if(-not[IO.File]::Exists($path)){throw('Required file missing: '+$path)}}
if((HashFile $validation)-cne$ExpectedValidationSha256){throw'Validation receipt differs from external pin.'}
$review=Get-Content -LiteralPath $validation -Raw|ConvertFrom-Json
if($review.result-cne'V1026_INSTALL_HELPER_LOCAL_TEST_PASS'-or
    $review.helper_sha256-cne(HashFile $helper)-or
    $review.installer_sha256-cne'1096276CC7C82E765A7BD1F03597CC09FF285AE587AC6B666CC86A04A3BFC25F'-or
    $review.payload_tree_sha256-cne'0C18CE2E9F810A8636DA007BE00F02ADD5AEB7869E693E4827774B0E3C53F908'-or
    $review.uninstaller_sha256-cne'610F5540AA0C6C24EF7DBEFFC1B5EE749D1B9C8CDCFC2B6EF643F8EA6F0DE837'-or
    [bool]$review.server_main_executed-or[bool]$review.installer_started-or[bool]$review.network_queries_performed-or[bool]$review.product_changes_made){throw'Validation result does not authorize packaging.'}

[void][IO.Directory]::CreateDirectory($output)
$files=Join-Path $output 'transfer-files';[void][IO.Directory]::CreateDirectory($files)
$helperTarget=Join-Path $files 'install-v1026-after-minimal-backup.ps1'
$guideTarget=Join-Path $files 'V1026_INSTALL_AFTER_MINIMAL_BACKUP_GUIDE.md'
[IO.File]::Copy($helper,$helperTarget,$false);[IO.File]::Copy($guide,$guideTarget,$false)
$helperHash=HashFile $helperTarget
[IO.File]::WriteAllText($helperTarget+'.sha256.txt',$helperHash+"`n",[Text.Encoding]::ASCII)
$facts=@(Fact $helperTarget;Fact($helperTarget+'.sha256.txt');Fact $guideTarget)
$zip=Join-Path $output 'v1026-install-after-minimal-backup-ready.zip'
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

$result=[pscustomobject]@{result='V1026_INSTALL_TRANSFER_READY_NOT_EXECUTED';zip=[pscustomobject]@{path=$zip;length=[long]$zipLength;sha256=$zipHash};entries=$facts|Select-Object name,length,sha256;validation_sha256=$ExpectedValidationSha256;helper_sha256=$helperHash;zip_closed_reopened_all_entries_rehashed=$true;server_execution_authorized=$false;installation_started=$false;product_changes_made=$false;automatic_rollback_performed=$false}
$json=$result|ConvertTo-Json -Depth 8
[IO.File]::WriteAllText((Join-Path $output 'build-result.json'),$json,[Text.UTF8Encoding]::new($false))
$json
