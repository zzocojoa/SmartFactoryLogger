param(
    [Parameter(Mandatory=$true)][string]$EngineAssembly,
    [Parameter(Mandatory=$true)][string]$ValidationReceipt,
    [Parameter(Mandatory=$true)][string]$OutputRoot
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function HashBytes {
    param([byte[]]$Bytes)
    $sha=[Security.Cryptography.SHA256]::Create()
    try {
        $digest=[byte[]]$sha.ComputeHash($Bytes)
        $hex=[BitConverter]::ToString($digest)
        return $hex.Replace('-','')
    }
    finally {$sha.Dispose()}
}
function NewBytes{param([string]$Path,[byte[]]$Bytes)$stream=[IO.File]::Open($Path,'CreateNew','Write','None');try{$stream.Write($Bytes,0,$Bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}}
$output=[IO.Path]::GetFullPath($OutputRoot)
if([IO.File]::Exists($output)-or[IO.Directory]::Exists($output)){throw'Existing output is preserved.'}
$helper=[IO.File]::ReadAllBytes((Join-Path $PSScriptRoot 'minimal-cold-backup-v1025.ps1'));$helperHash=HashBytes $helper
$engine=[IO.File]::ReadAllBytes([IO.Path]::GetFullPath($EngineAssembly));$engineHash=HashBytes $engine
if($engineHash-cne'3B8B3649C623EB8A7112C762D95A00AD9745231291C50CCC2B66E0AA2C7F8A71'){throw'Engine hash differs.'}
$receiptBytes=[IO.File]::ReadAllBytes([IO.Path]::GetFullPath($ValidationReceipt))
$receipt=ConvertFrom-Json -InputObject ([Text.UTF8Encoding]::new($false,$true).GetString($receiptBytes))
if($receipt.result-cne'V1025_MINIMAL_COLD_BACKUP_LOCAL_TEST_PASS'-or$receipt.helper_sha256-cne$helperHash-or
    $receipt.engine_sha256-cne$engineHash-or$receipt.server_main_executed-ne$false-or
    $receipt.network_queries_performed-ne$false-or$receipt.application_stopped-ne$false-or$receipt.product_changes_made-ne$false){
    throw'Exact helper/engine lacks required test receipt.'
}
if(-not[Text.UTF8Encoding]::new($false,$true).GetString($helper).Contains($engineHash)){throw'Helper does not pin the engine.'}
$payloads=[ordered]@{
    'minimal-cold-backup-v1025.ps1'=$helper
    'minimal-cold-backup-v1025.ps1.sha256.txt'=[Text.Encoding]::ASCII.GetBytes($helperHash+"`n")
    'cold-backup-core.dll'=$engine
    'cold-backup-core.dll.sha256.txt'=[Text.Encoding]::ASCII.GetBytes($engineHash+"`n")
    'MINIMAL_COLD_BACKUP_GUIDE.md'=[IO.File]::ReadAllBytes((Join-Path $PSScriptRoot 'MINIMAL_COLD_BACKUP_GUIDE.md'))
}
[void][IO.Directory]::CreateDirectory($output)
Add-Type -AssemblyName System.IO.Compression
$zipPath=Join-Path $output 'v1025-minimal-cold-backup-ready.zip'
$stream=[IO.File]::Open($zipPath,'CreateNew','Write','None')
try{$archive=[IO.Compression.ZipArchive]::new($stream,'Create',$true);try{foreach($payload in $payloads.GetEnumerator()){
    $entry=$archive.CreateEntry($payload.Key,[IO.Compression.CompressionLevel]::Optimal);$entryStream=$entry.Open()
    try{$entryStream.Write($payload.Value,0,$payload.Value.Length)}finally{$entryStream.Dispose()}}}finally{$archive.Dispose()};$stream.Flush($true)}finally{$stream.Dispose()}
$stream=[IO.File]::Open($zipPath,'Open','Read','Read')
try{$archive=[IO.Compression.ZipArchive]::new($stream,'Read',$true);try{
    if($archive.Entries.Count-ne$payloads.Count){throw'Reopened ZIP entry count differs.'};$seen=@{}
    foreach($entry in $archive.Entries){if(-not$payloads.Contains($entry.FullName)-or$seen.ContainsKey($entry.FullName)-or
        $entry.FullName.Contains('/')-or$entry.FullName.Contains('\')-or(($entry.ExternalAttributes-shr 16)-band 0xF000)-eq 0xA000-or
        ($entry.ExternalAttributes-band 0x400)-ne 0){throw'Unapproved reopened ZIP entry.'};$seen[$entry.FullName]=$true
        $expected=[byte[]]$payloads[$entry.FullName];if($entry.Length-ne$expected.Length){throw'Reopened entry length differs.'}
        $input=$entry.Open();$buffer=[IO.MemoryStream]::new();try{$input.CopyTo($buffer);if($buffer.Length-ne$expected.Length-or
            (HashBytes $buffer.ToArray())-cne(HashBytes $expected)){throw'Reopened entry hash differs.'}}finally{$input.Dispose();$buffer.Dispose()}}
}finally{$archive.Dispose()}}finally{$stream.Dispose()}
$zipBytes=[IO.File]::ReadAllBytes($zipPath);$zipHash=HashBytes $zipBytes
NewBytes ($zipPath+'.sha256.txt') ([Text.Encoding]::ASCII.GetBytes($zipHash+"`n"))
$record=[ordered]@{result='V1025_MINIMAL_COLD_BACKUP_TRANSFER_READY_NOT_EXECUTED';zip_path=$zipPath;zip_bytes=$zipBytes.Length;
    zip_sha256=$zipHash;helper_sha256=$helperHash;engine_sha256=$engineHash;entry_count=$payloads.Count;reopened_zip_verified=$true;
    validation_receipt_sha256=(HashBytes $receiptBytes);server_execution_performed=$false;backup_created=$false;application_stopped=$false;
    installation_authorized=$false;entries=@(foreach($payload in $payloads.GetEnumerator()){
        [ordered]@{name=$payload.Key;bytes=$payload.Value.Length;sha256=(HashBytes $payload.Value)}})}
NewBytes (Join-Path $output 'build-result.json') ([Text.UTF8Encoding]::new($false).GetBytes(($record|ConvertTo-Json -Depth 6)))
$record|ConvertTo-Json -Depth 6
