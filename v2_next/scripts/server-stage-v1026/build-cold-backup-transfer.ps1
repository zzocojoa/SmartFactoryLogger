param(
    [Parameter(Mandatory=$true)][string]$EngineAssembly,
    [Parameter(Mandatory=$true)][string]$ValidationReceipt
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$workspace=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$output=Join-Path $workspace 'artifacts\v1026-cold-backup-ready-20260912-r2'
if([IO.Directory]::Exists($output) -or [IO.File]::Exists($output)){throw 'Existing transfer preparation preserved.'}
function Sha {param([byte[]]$Bytes) $s=[Security.Cryptography.SHA256]::Create();try{[BitConverter]::ToString($s.ComputeHash($Bytes)).Replace('-','')}finally{$s.Dispose()}}
function NewBytes {param([string]$Path,[byte[]]$Bytes) $s=[IO.File]::Open($Path,'CreateNew','Write','None');try{$s.Write($Bytes,0,$Bytes.Length);$s.Flush($true)}finally{$s.Dispose()}}
$dll=[IO.File]::ReadAllBytes([IO.Path]::GetFullPath($EngineAssembly));$dllHash=Sha $dll
if($dllHash -cne '3B8B3649C623EB8A7112C762D95A00AD9745231291C50CCC2B66E0AA2C7F8A71'){throw 'Exact compiled DLL differs.'}
$script=[IO.File]::ReadAllBytes((Join-Path $PSScriptRoot 'backup-restore-v1025.ps1'));$scriptHash=Sha $script
$core=[IO.File]::ReadAllBytes((Join-Path $PSScriptRoot 'cold-backup-core.cs'))
$receipt=[IO.File]::ReadAllBytes([IO.Path]::GetFullPath($ValidationReceipt))
$test=ConvertFrom-Json -InputObject ([Text.Encoding]::UTF8.GetString($receipt))
if($test.result -cne 'COLD_BACKUP_SYNTHETIC_TEST_PASS' -or $test.wrapper_sha256 -cne $scriptHash -or
    $test.engine_dll_sha256 -cne $dllHash -or $test.core_sha256 -cne (Sha $core) -or
    $test.server_main_executed -ne $false -or $test.multi_gib_file_tested -ne $true){throw 'Exact shipped bytes lack the required test receipt.'}
if(-not [Text.Encoding]::UTF8.GetString($script).Contains($dllHash)){throw 'Helper does not pin this engine.'}
$payloads=[ordered]@{
    'backup-restore-v1025.ps1'=$script
    'backup-restore-v1025.ps1.sha256.txt'=[Text.Encoding]::ASCII.GetBytes($scriptHash+"`n")
    'cold-backup-core.dll'=$dll
    'cold-backup-core.dll.sha256.txt'=[Text.Encoding]::ASCII.GetBytes($dllHash+"`n")
    'COLD_BACKUP_GUIDE.md'=[IO.File]::ReadAllBytes((Join-Path $PSScriptRoot 'COLD_BACKUP_GUIDE.md'))
}
[void][IO.Directory]::CreateDirectory($output)
$payload=Join-Path $output 'payload';[void][IO.Directory]::CreateDirectory($payload)
foreach($p in $payloads.GetEnumerator()){NewBytes (Join-Path $payload $p.Key) $p.Value}
NewBytes (Join-Path $output 'validation-result.json') $receipt
Add-Type -AssemblyName System.IO.Compression
$zipPath=Join-Path $output 'v1025-cold-backup-restore-ready.zip'
$stream=[IO.File]::Open($zipPath,'CreateNew','Write','None')
try{
    $zip=[IO.Compression.ZipArchive]::new($stream,'Create',$true)
    try{foreach($p in $payloads.GetEnumerator()){$entry=$zip.CreateEntry($p.Key,[IO.Compression.CompressionLevel]::Optimal);$s=$entry.Open();try{$s.Write($p.Value,0,$p.Value.Length)}finally{$s.Dispose()}}}
    finally{$zip.Dispose()}
    $stream.Flush($true)
}finally{$stream.Dispose()}
$zipHash=Sha ([IO.File]::ReadAllBytes($zipPath));$zipLength=[IO.FileInfo]::new($zipPath).Length
$stream=[IO.File]::Open($zipPath,'Open','Read','Read')
try{
    $zip=[IO.Compression.ZipArchive]::new($stream,'Read',$true)
    try{
        if($zip.Entries.Count -ne $payloads.Count){throw 'Archive entry count differs.'}
        foreach($e in $zip.Entries){
            if(-not $payloads.Contains($e.FullName) -or $e.Length -ne $payloads[$e.FullName].Length){throw 'Archive membership/size differs.'}
            $s=$e.Open();$b=[IO.MemoryStream]::new()
            try{$s.CopyTo($b);if((Sha $b.ToArray()) -cne (Sha $payloads[$e.FullName])){throw 'Reopened ZIP content differs.'}}
            finally{$s.Dispose();$b.Dispose()}
        }
    }finally{$zip.Dispose()}
}finally{$stream.Dispose()}
NewBytes ($zipPath+'.sha256.txt') ([Text.Encoding]::ASCII.GetBytes($zipHash+"`n"))
$record=[ordered]@{result='COLD_BACKUP_TRANSFER_PREPARED_NOT_EXECUTED';zip_sha256=$zipHash;zip_bytes=$zipLength;
    helper_sha256=$scriptHash;engine_sha256=$dllHash;core_source_sha256=(Sha $core);entry_count=$payloads.Count;
    assertions=$test.assertions;multi_gib_file_tested=$true;server_execution_performed=$false;installation_authorized=$false;
    entries=@(foreach($p in $payloads.GetEnumerator()){[ordered]@{name=$p.Key;bytes=$p.Value.Length;sha256=(Sha $p.Value)}})}
NewBytes (Join-Path $output 'package-validation.json') ([Text.UTF8Encoding]::new($false).GetBytes(($record|ConvertTo-Json -Depth 5)))
$record|ConvertTo-Json -Depth 5
