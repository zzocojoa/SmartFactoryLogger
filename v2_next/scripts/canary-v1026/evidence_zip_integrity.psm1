Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression

function Assert-EvidencePlainPath {
    param([Parameter(Mandatory=$true)][string]$Path)
    $node = [IO.FileInfo]::new([IO.Path]::GetFullPath($Path))
    while ($null -ne $node) {
        # FileInfo reports -1 for a not-yet-created destination; still inspect every ancestor.
        $attributes=$node.Attributes
        if ([int]$attributes -ne -1 -and ($attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Reparse path rejected: $Path"
        }
        if ($node -is [IO.FileInfo]) { $node = $node.Directory }
        else { $node = $node.Parent }
    }
}

function Assert-EvidenceEntryName {
    param([Parameter(Mandatory=$true)][string]$Name)
    if ($Name -match '[\\:<>"|?*\x00-\x1f]' -or $Name.StartsWith('/') -or
        $Name.EndsWith('/') -or $Name.Length -gt 240) { throw 'Unsafe ZIP entry name.' }
    foreach ($part in $Name.Split('/')) {
        if ([string]::IsNullOrWhiteSpace($part) -or $part -in @('.','..') -or
            $part -match '[. ]$' -or $part -match '^(?i:CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\.|$)') {
            throw 'Unsafe ZIP entry component.'
        }
    }
}

function Get-EvidenceStreamHash {
    param([Parameter(Mandatory=$true)][IO.Stream]$Stream)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        if ($Stream.CanSeek) { $Stream.Position = 0 }
        return [BitConverter]::ToString($sha.ComputeHash($Stream)).Replace('-','')
    } finally { $sha.Dispose() }
}

function Get-EvidenceFileFact {
    param([Parameter(Mandatory=$true)][string]$Path)
    Assert-EvidencePlainPath $Path
    $stream = [IO.File]::Open($Path,'Open','Read','Read')
    try { return [pscustomobject]@{length=$stream.Length;sha256=Get-EvidenceStreamHash $stream} }
    finally { $stream.Dispose() }
}

function Get-EvidenceFileNames {
    param([Parameter(Mandatory=$true)][string]$Root)
    Assert-EvidencePlainPath $Root
    if (-not [IO.Directory]::Exists($Root)) { throw 'Evidence root missing.' }
    $full = [IO.Path]::GetFullPath($Root).TrimEnd('\')
    $queue = [Collections.Generic.Queue[string]]::new()
    $queue.Enqueue($full)
    $names = [Collections.Generic.List[string]]::new()
    while ($queue.Count -gt 0) {
        $directory = $queue.Dequeue()
        Assert-EvidencePlainPath $directory
        foreach ($item in @(Get-ChildItem -LiteralPath $directory -Force)) {
            Assert-EvidencePlainPath $item.FullName
            if ($item.PSIsContainer) { $queue.Enqueue($item.FullName); continue }
            $name = $item.FullName.Substring($full.Length+1).Replace('\','/')
            Assert-EvidenceEntryName $name
            $names.Add($name)
        }
    }
    $sorted = $names.ToArray()
    [Array]::Sort($sorted,[StringComparer]::Ordinal)
    return ,$sorted
}

function Test-VerifiedEvidenceZip {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)][object[]]$Entries,
        [string]$ExpectedSha256 = ''
    )
    Assert-EvidencePlainPath $Path
    $specs = [Collections.Generic.Dictionary[string,object]]::new([StringComparer]::OrdinalIgnoreCase)
    if ($Entries.Count -eq 0) { throw 'Empty ZIP contract.' }
    foreach ($spec in $Entries) {
        Assert-EvidenceEntryName $spec.name
        if ($spec.length -isnot [int] -and $spec.length -isnot [long]) { throw 'Invalid entry length type.' }
        if ($spec.length -lt 0 -or $spec.sha256 -cnotmatch '^[A-F0-9]{64}$' -or $specs.ContainsKey($spec.name)) {
            throw 'Invalid or duplicate entry contract.'
        }
        $specs.Add($spec.name,$spec)
    }
    $stream = [IO.File]::Open($Path,'Open','Read','Read')
    $archive = $null
    try {
        $hash = Get-EvidenceStreamHash $stream
        if ($ExpectedSha256 -ne '' -and $hash -cne $ExpectedSha256) { throw 'ZIP SHA256 mismatch.' }
        $stream.Position = 0
        $archive = [IO.Compression.ZipArchive]::new($stream,'Read',$true)
        if ($archive.Entries.Count -ne $specs.Count) { throw 'ZIP entry count mismatch.' }
        $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
        foreach ($entry in $archive.Entries) {
            Assert-EvidenceEntryName $entry.FullName
            if (-not $seen.Add($entry.FullName) -or -not $specs.ContainsKey($entry.FullName)) { throw 'Unapproved/duplicate ZIP entry.' }
            $spec = $specs[$entry.FullName]
            if ($entry.FullName -cne $spec.name -or $entry.Length -ne $spec.length -or
                (($entry.ExternalAttributes -shr 16) -band 0xF000) -eq 0xA000 -or
                ($entry.ExternalAttributes -band 0x400) -ne 0) { throw 'ZIP entry metadata mismatch.' }
            $input = $entry.Open()
            $sha = [Security.Cryptography.SHA256]::Create()
            try {
                $buffer = New-Object byte[] 81920
                $count = [long]0
                while (($read = $input.Read($buffer,0,$buffer.Length)) -gt 0) {
                    $count += $read
                    if ($count -gt $spec.length) { throw 'ZIP expansion exceeds contract.' }
                    $null = $sha.TransformBlock($buffer,0,$read,$buffer,0)
                }
                $null = $sha.TransformFinalBlock($buffer,0,0)
                $actual = [BitConverter]::ToString($sha.Hash).Replace('-','')
                if ($count -ne $spec.length -or $actual -cne $spec.sha256) { throw 'ZIP entry content mismatch.' }
            } finally { $input.Dispose(); $sha.Dispose() }
        }
        return [pscustomobject]@{path=[IO.Path]::GetFullPath($Path);length=$stream.Length;sha256=$hash;entry_count=$specs.Count;entries=$Entries}
    } finally { if ($null -ne $archive) { $archive.Dispose() }; $stream.Dispose() }
}

function Write-EvidenceJsonNew {
    param([string]$Path,[object]$Value)
    Assert-EvidencePlainPath $Path
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes(($Value | ConvertTo-Json -Depth 16))
    $stream = [IO.File]::Open($Path,'CreateNew','Write','None')
    try { $stream.Write($bytes,0,$bytes.Length); $stream.Flush($true) }
    finally { $stream.Dispose() }
    return Get-EvidenceFileFact $Path
}

function New-VerifiedEvidenceZip {
    param(
        [Parameter(Mandatory=$true)][string]$SourceRoot,
        [Parameter(Mandatory=$true)][string]$Destination,
        [string]$ReceiptPath = ''
    )
    $root = [IO.Path]::GetFullPath($SourceRoot).TrimEnd('\')
    $dest = [IO.Path]::GetFullPath($Destination)
    if ($dest.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'ZIP must be outside source root.' }
    foreach ($path in @($dest,($dest+'.partial'))) {
        Assert-EvidencePlainPath $path
        if (Test-Path -LiteralPath $path) { throw 'Existing ZIP target is preserved; choose a new destination.' }
    }
    if ($ReceiptPath -ne '') {
        $receipt = [IO.Path]::GetFullPath($ReceiptPath)
        Assert-EvidencePlainPath $receipt
        if ($receipt.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase) -or
            $receipt -ieq $dest -or $receipt -ieq ($dest+'.partial') -or (Test-Path -LiteralPath $receipt)) {
            throw 'Unsafe/existing completion receipt target.'
        }
    }
    $names = Get-EvidenceFileNames $root
    if ($names.Count -eq 0) { throw 'Empty evidence root.' }
    $entries = [Collections.Generic.List[object]]::new()
    $pins = [Collections.Generic.List[IO.FileStream]]::new()
    $out = $null; $archive = $null
    try {
        foreach ($name in $names) {
            $path = Join-Path $root $name.Replace('/','\')
            Assert-EvidencePlainPath $path
            # ReadWrite sharing supports a transcript already open by its writer.
            # This is a byte snapshot, not an assertion that the writer is stopped.
            $pin = [IO.File]::Open($path,'Open','Read','ReadWrite')
            $pins.Add($pin)
            $length = $pin.Length
            $hash = Get-EvidenceStreamHash $pin
            if ($pin.Length -ne $length) { throw 'Source changed while hashing.' }
            $entries.Add([pscustomobject]@{name=$name;length=$length;sha256=$hash})
        }
        $out = [IO.File]::Open($dest+'.partial','CreateNew','ReadWrite','None')
        $archive = [IO.Compression.ZipArchive]::new($out,'Create',$true)
        for ($i=0; $i -lt $pins.Count; $i++) {
            $spec = $entries[$i]; $pin = $pins[$i]
            $entry = $archive.CreateEntry($spec.name,[IO.Compression.CompressionLevel]::Optimal)
            $writer = $entry.Open()
            try {
                $pin.Position=0
                $remaining=[long]$spec.length
                $buffer=New-Object byte[] 81920
                while ($remaining -gt 0) {
                    $read=$pin.Read($buffer,0,[int][Math]::Min($buffer.Length,$remaining))
                    if ($read -le 0) { throw 'Source truncated during copy.' }
                    $writer.Write($buffer,0,$read); $remaining-=$read
                }
            } finally { $writer.Dispose() }
            if ($pin.Length -ne $spec.length -or (Get-EvidenceStreamHash $pin) -cne $spec.sha256) { throw 'Source changed during ZIP creation.' }
        }
        $archive.Dispose(); $archive = $null
        $out.Flush($true); $out.Dispose(); $out = $null
        $verified = Test-VerifiedEvidenceZip -Path ($dest+'.partial') -Entries $entries.ToArray()
        $afterNames = Get-EvidenceFileNames $root
        if (($afterNames -join "`n") -cne ($names -join "`n")) { throw 'Source file set changed during ZIP creation.' }
        for ($i=0; $i -lt $pins.Count; $i++) {
            if ($pins[$i].Length -ne $entries[$i].length -or
                (Get-EvidenceStreamHash $pins[$i]) -cne $entries[$i].sha256) { throw 'Source changed before ZIP publication.' }
        }
        [IO.File]::Move($dest+'.partial',$dest)
        $verified = Test-VerifiedEvidenceZip -Path $dest -Entries $entries.ToArray() -ExpectedSha256 $verified.sha256
        if ($ReceiptPath -ne '') {
            Write-EvidenceJsonNew -Path $ReceiptPath -Value ([ordered]@{
                schema_version='sfl-verified-zip-receipt-v1'; result='ZIP_VERIFIED_NOT_OBSERVATION_PASS'
                recorded_at=[DateTimeOffset]::Now.ToString('o'); archive=$verified
                source_snapshot_policy='shared-read-copy-rehash'; production_promotion_allowed=$false
            }) | Out-Null
        }
        return $verified
    } finally {
        if ($null -ne $archive) { $archive.Dispose() }
        if ($null -ne $out) { $out.Dispose() }
        foreach ($pin in $pins) { $pin.Dispose() }
        # Failed .partial/final ZIPs are retained. Never overwrite evidence or emit a success receipt on failure.
    }
}

Export-ModuleMember -Function Assert-EvidencePlainPath,Assert-EvidenceEntryName,Get-EvidenceStreamHash,Get-EvidenceFileFact,Get-EvidenceFileNames,Test-VerifiedEvidenceZip,New-VerifiedEvidenceZip,Write-EvidenceJsonNew
