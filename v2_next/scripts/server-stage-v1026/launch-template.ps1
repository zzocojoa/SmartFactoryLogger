& {
    Set-StrictMode -Version Latest
    $ErrorActionPreference='Stop'
    $path='C:\Users\user\Desktop\SmartFactory\@ZIP_NAME@'
    $expected='@ZIP_HASH@'
    $length=[long]@ZIP_LENGTH@
    $held=$null; $archive=$null
    $savedModules=$env:PSModulePath; $savedPath=$env:PATH
    function Launch-Plain {
        param([string]$Path)
        $node=[IO.FileInfo]::new([IO.Path]::GetFullPath($Path))
        while ($null -ne $node) {
            if ([int]$node.Attributes -ne -1 -and ($node.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Reparse transfer path rejected.' }
            if ($node -is [IO.FileInfo]) { $node=$node.Directory } else { $node=$node.Parent }
        }
    }
    function Launch-Hash {
        param([IO.Stream]$Stream)
        $sha=[Security.Cryptography.SHA256]::Create()
        try { $Stream.Position=0; return [BitConverter]::ToString($sha.ComputeHash($Stream)).Replace('-','') }
        finally { $sha.Dispose() }
    }
    try {
        $native=[IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
        $principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
        if (-not [Environment]::Is64BitProcess -or $PSVersionTable.PSEdition -cne 'Desktop' -or
            $PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1 -or
            [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName -ine $native -or
            -not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Use administrator native x64 Windows PowerShell 5.1.' }
        $env:PSModulePath=[IO.Path]::GetDirectoryName($native)+'\Modules'
        $env:PATH=[Environment]::SystemDirectory+';'+[IO.Path]::GetDirectoryName($native)
        Launch-Plain $path; Launch-Plain ($path+'.sha256.txt')
        $lines=@([IO.File]::ReadAllLines($path+'.sha256.txt'))
        if ($lines.Count -ne 1 -or $lines[0] -cne $expected) { throw 'Transfer sidecar differs from external expected hash.' }
        $held=[IO.File]::Open($path,'Open','Read','Read')
        if ($held.Length -ne $length -or (Launch-Hash $held) -cne $expected) { throw 'Transfer length/hash mismatch.' }
        Add-Type -AssemblyName System.IO.Compression
        $held.Position=0; $archive=[IO.Compression.ZipArchive]::new($held,'Read',$true)
        $matches=@($archive.Entries | Where-Object FullName -CEQ 'server-stage.ps1')
        if ($archive.Entries.Count -ne 32 -or $matches.Count -ne 1 -or $matches[0].Length -ne @HELPER_LENGTH@ -or
            (($matches[0].ExternalAttributes -shr 16) -band 0xF000) -eq 0xA000 -or ($matches[0].ExternalAttributes -band 0x400) -ne 0) { throw 'Helper entry mismatch.' }
        $source=$matches[0].Open(); $buffer=[IO.MemoryStream]::new()
        try {
            $chunk=New-Object byte[] 8192
            while (($read=$source.Read($chunk,0,$chunk.Length)) -gt 0) {
                if ($buffer.Length+$read -gt @HELPER_LENGTH@) { throw 'Helper expansion exceeds pin.' }
                $buffer.Write($chunk,0,$read)
            }
            if ($buffer.Length -ne @HELPER_LENGTH@ -or (Launch-Hash $buffer) -cne '@HELPER_HASH@') { throw 'Helper content differs.' }
            $code=[scriptblock]::Create([Text.UTF8Encoding]::new($false,$true).GetString($buffer.ToArray()))
        } finally { $source.Dispose(); $buffer.Dispose() }
        Write-Host '[LAUNCH] Externally hash-bound staging only. No installer, restart or observation.' -ForegroundColor Green
        & $code -TransferZip $path -ExpectedZipSha256 $expected -ExpectedZipLength $length -ExpectedManifestSha256 '@MANIFEST_HASH@'
    } catch {
        Write-Host '[HOLD] Preserve all files/output. No automatic retry, cleanup, install, restart or rollback.' -ForegroundColor Yellow
        throw
    } finally {
        if ($null -ne $archive) { $archive.Dispose() }
        if ($null -ne $held) { $held.Dispose() }
        $env:PSModulePath=$savedModules; $env:PATH=$savedPath
    }
}
