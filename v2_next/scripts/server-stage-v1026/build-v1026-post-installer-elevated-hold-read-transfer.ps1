Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = [IO.Path]::GetFullPath(
    (Join-Path $PSScriptRoot '..\..')
)
$outputRoot = Join-Path $repoRoot (
    'artifacts\' +
    'v1026-post-installer-elevated-hold-read-ready-20260916'
)
$stagingRoot = Join-Path $outputRoot 'transfer-files'
$zipPath = Join-Path $outputRoot (
    'v1026-post-installer-elevated-hold-read-ready.zip'
)

if (
    [IO.Directory]::Exists($outputRoot) -or
    [IO.File]::Exists($outputRoot)
) {
    throw "Output already exists: $outputRoot"
}

[void][IO.Directory]::CreateDirectory($stagingRoot)

$sourceFiles = [ordered]@{
    'read-v1026-post-installer-elevated-hold.ps1' =
        (Join-Path $PSScriptRoot (
            'read-v1026-post-installer-elevated-hold.ps1'
        ))
    'V1026_POST_INSTALLER_ELEVATED_HOLD_READ_GUIDE.md' =
        (Join-Path $PSScriptRoot (
            'V1026_POST_INSTALLER_ELEVATED_HOLD_READ_GUIDE.md'
        ))
}

foreach ($name in $sourceFiles.Keys) {
    $source = $sourceFiles[$name]
    if (-not [IO.File]::Exists($source)) {
        throw "Source file missing: $source"
    }

    [IO.File]::Copy(
        $source,
        (Join-Path $stagingRoot $name),
        $false
    )
}

$helperPath = Join-Path $stagingRoot (
    'read-v1026-post-installer-elevated-hold.ps1'
)
$helperHash = (Get-FileHash -LiteralPath $helperPath -Algorithm SHA256).Hash
[IO.File]::WriteAllText(
    ($helperPath + '.sha256.txt'),
    ($helperHash + "`n"),
    [Text.UTF8Encoding]::new($false)
)

Add-Type -AssemblyName System.IO.Compression

$zipStream = [IO.File]::Open(
    $zipPath,
    [IO.FileMode]::CreateNew,
    [IO.FileAccess]::ReadWrite,
    [IO.FileShare]::None
)

try {
    $archive = [IO.Compression.ZipArchive]::new(
        $zipStream,
        [IO.Compression.ZipArchiveMode]::Create,
        $true
    )

    try {
        foreach (
            $file in Get-ChildItem `
                -LiteralPath $stagingRoot `
                -File |
                Sort-Object Name
        ) {
            $entry = $archive.CreateEntry(
                $file.Name,
                [IO.Compression.CompressionLevel]::Optimal
            )
            $entry.LastWriteTime = [DateTimeOffset]::new(
                2026,
                9,
                16,
                0,
                0,
                0,
                [TimeSpan]::Zero
            )

            $input = [IO.File]::OpenRead($file.FullName)
            $output = $entry.Open()
            try {
                $input.CopyTo($output)
            }
            finally {
                $output.Dispose()
                $input.Dispose()
            }
        }
    }
    finally {
        $archive.Dispose()
    }
}
finally {
    $zipStream.Dispose()
}

$zipHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash
[IO.File]::WriteAllText(
    ($zipPath + '.sha256.txt'),
    ($zipHash + "`n"),
    [Text.UTF8Encoding]::new($false)
)

[pscustomobject][ordered]@{
    result = 'V1026_POST_INSTALLER_ELEVATED_HOLD_READ_TRANSFER_READY'
    zip_path = $zipPath
    zip_length = (Get-Item -LiteralPath $zipPath).Length
    zip_sha256 = $zipHash
    helper_length = (Get-Item -LiteralPath $helperPath).Length
    helper_sha256 = $helperHash
    files = @(
        Get-ChildItem -LiteralPath $stagingRoot -File |
            Sort-Object Name |
            ForEach-Object {
                [pscustomobject]@{
                    name = $_.Name
                    length = $_.Length
                    sha256 = (
                        Get-FileHash `
                            -LiteralPath $_.FullName `
                            -Algorithm SHA256
                    ).Hash
                }
            }
    )
} | ConvertTo-Json -Depth 5
