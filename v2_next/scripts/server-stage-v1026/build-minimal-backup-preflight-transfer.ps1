param(
    [Parameter(Mandatory=$true)][string]$ValidationReceipt,
    [Parameter(Mandatory=$true)][string]$OutputRoot
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
function HashBytes {param([byte[]]$Bytes) $sha=[Security.Cryptography.SHA256]::Create();try{return [BitConverter]::ToString($sha.ComputeHash($Bytes)).Replace('-','')}finally{$sha.Dispose()}}
function NewBytes {param([string]$Path,[byte[]]$Bytes) $stream=[IO.File]::Open($Path,'CreateNew','Write','None');try{$stream.Write($Bytes,0,$Bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}}
$output = [IO.Path]::GetFullPath($OutputRoot)
if ([IO.File]::Exists($output) -or [IO.Directory]::Exists($output)) { throw 'Existing output is preserved.' }
$helperPath = Join-Path $PSScriptRoot 'read-minimal-backup-preflight-v1025.ps1'
$guidePath = Join-Path $PSScriptRoot 'MINIMAL_BACKUP_PREFLIGHT_GUIDE.md'
$helper = [IO.File]::ReadAllBytes($helperPath)
$helperHash = HashBytes $helper
$receiptBytes = [IO.File]::ReadAllBytes([IO.Path]::GetFullPath($ValidationReceipt))
$receipt = ConvertFrom-Json -InputObject ([Text.UTF8Encoding]::new($false,$true).GetString($receiptBytes))
if ($receipt.result -cne 'V1025_MINIMAL_BACKUP_PREFLIGHT_LOCAL_TEST_PASS' -or
    $receipt.server_main_executed -ne $false -or $receipt.network_queries_performed -ne $false -or
    $receipt.product_changes_made -ne $false) { throw 'Required local validation receipt is missing.' }
$payloads = [ordered]@{
    'read-minimal-backup-preflight-v1025.ps1' = $helper
    'read-minimal-backup-preflight-v1025.ps1.sha256.txt' = [Text.Encoding]::ASCII.GetBytes($helperHash + "`n")
    'MINIMAL_BACKUP_PREFLIGHT_GUIDE.md' = [IO.File]::ReadAllBytes($guidePath)
}
[void][IO.Directory]::CreateDirectory($output)
Add-Type -AssemblyName System.IO.Compression
$zipPath = Join-Path $output 'v1025-minimal-backup-preflight-ready-r2.zip'
$stream = [IO.File]::Open($zipPath,'CreateNew','Write','None')
try {
    $archive = [IO.Compression.ZipArchive]::new($stream,'Create',$true)
    try {
        foreach ($payload in $payloads.GetEnumerator()) {
            $entry = $archive.CreateEntry($payload.Key,[IO.Compression.CompressionLevel]::Optimal)
            $entryStream = $entry.Open()
            try { $entryStream.Write($payload.Value,0,$payload.Value.Length) }
            finally { $entryStream.Dispose() }
        }
    }
    finally { $archive.Dispose() }
    $stream.Flush($true)
}
finally { $stream.Dispose() }
$stream = [IO.File]::Open($zipPath,'Open','Read','Read')
try {
    $archive = [IO.Compression.ZipArchive]::new($stream,'Read',$true)
    try {
        if ($archive.Entries.Count -ne $payloads.Count) { throw 'Reopened ZIP entry count differs.' }
        $seen = @{}
        foreach ($entry in $archive.Entries) {
            if (-not $payloads.Contains($entry.FullName) -or $seen.ContainsKey($entry.FullName) -or
                $entry.FullName.Contains('/') -or $entry.FullName.Contains('\') -or
                (($entry.ExternalAttributes -shr 16) -band 0xF000) -eq 0xA000 -or
                ($entry.ExternalAttributes -band 0x400) -ne 0) { throw 'Reopened ZIP contains an unapproved entry.' }
            $seen[$entry.FullName] = $true
            $expectedBytes = [byte[]]$payloads[$entry.FullName]
            if ($entry.Length -ne $expectedBytes.Length) { throw 'Reopened ZIP entry length differs.' }
            $entryStream = $entry.Open()
            $buffer = [IO.MemoryStream]::new()
            try {
                $entryStream.CopyTo($buffer)
                if ($buffer.Length -ne $expectedBytes.Length -or
                    (HashBytes $buffer.ToArray()) -cne (HashBytes $expectedBytes)) {
                    throw 'Reopened ZIP entry content differs.'
                }
            }
            finally { $entryStream.Dispose(); $buffer.Dispose() }
        }
    }
    finally { $archive.Dispose() }
}
finally { $stream.Dispose() }
$zipBytes = [IO.File]::ReadAllBytes($zipPath)
$zipHash = HashBytes $zipBytes
NewBytes ($zipPath + '.sha256.txt') ([Text.Encoding]::ASCII.GetBytes($zipHash + "`n"))
$record = [ordered]@{
    result = 'V1025_MINIMAL_BACKUP_PREFLIGHT_TRANSFER_READY_NOT_EXECUTED'
    zip_path = $zipPath
    zip_bytes = $zipBytes.Length
    zip_sha256 = $zipHash
    helper_bytes = $helper.Length
    helper_sha256 = $helperHash
    entries = @(foreach ($payload in $payloads.GetEnumerator()) {
        [ordered]@{name=$payload.Key;bytes=$payload.Value.Length;sha256=(HashBytes $payload.Value)}
    })
    validation_receipt_sha256 = HashBytes $receiptBytes
    reopened_zip_verified = $true
    server_execution_performed = $false
    backup_created = $false
    installation_authorized = $false
}
NewBytes (Join-Path $output 'build-result.json') ([Text.UTF8Encoding]::new($false).GetBytes(
    ($record | ConvertTo-Json -Depth 6)))
$record | ConvertTo-Json -Depth 6
