[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-F0-9]{64}$')][string]$ExpectedBundleManifestSha256,
    [string]$BundlePath='',
    [switch]$LibraryOnly
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$native=[Environment]::SystemDirectory+'\WindowsPowerShell\v1.0\powershell.exe'
if(-not [Environment]::Is64BitProcess -or $PSVersionTable.PSEdition -cne 'Desktop' -or
    $PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1 -or
    [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName -ine $native){throw 'native-ps51-x64-required'}
$env:PATH=[Environment]::SystemDirectory+';'+[IO.Path]::GetDirectoryName($native)
$env:PSModulePath=[IO.Path]::GetDirectoryName($native)+'\Modules'
if([string]::IsNullOrEmpty($BundlePath)){$BundlePath=Join-Path $PSScriptRoot 'backup'}

# Original pinned carrier contract, retained without changing the copy engine or wrapper.
function Invoke-PinnedStreamsCopyCommand([string]$Path,[string]$Pin,[switch]$LibraryOnly) {
    $held=[Collections.Generic.List[IDisposable]]::new()
    $sha=[Security.Cryptography.SHA256]::Create()
    try {
        $root=[IO.Path]::GetFullPath($Path)
        $allowed=@('cold-backup-streams-core.dll','copy-cold-operating-streams.ps1','README.txt','scope.json','cold-backup-streams-core.cs','test-cold-backup-streams.ps1')
        $manifest=[IO.File]::Open((Join-Path $root 'bundle-manifest.json'),'Open','Read','Read');$held.Add($manifest)
        if([BitConverter]::ToString($sha.ComputeHash($manifest)).Replace('-','') -cne $Pin){throw 'External manifest pin mismatch.'}
        $manifest.Position=0;$reader=[IO.StreamReader]::new($manifest,[Text.UTF8Encoding]::new($false,$true),$true,4096,$true)
        try {$definition=$reader.ReadToEnd()|ConvertFrom-Json}finally{$reader.Dispose()}
        $names=@($definition.files|ForEach-Object name)
        if($names.Count -ne 6 -or @($names|Select-Object -Unique).Count -ne 6 -or @($names|Where-Object {$_ -cnotin $allowed}).Count -ne 0){throw 'Manifest membership mismatch.'}
        $actual=@([IO.Directory]::GetFileSystemEntries($root)|ForEach-Object {[IO.Path]::GetFileName($_)})
        if($actual.Count -ne 7 -or @($actual|Where-Object {$_ -cnotin ($allowed+@('bundle-manifest.json'))}).Count -ne 0){throw 'Folder membership mismatch.'}
        $helperBytes=$null
        foreach($item in $definition.files){
            $stream=[IO.File]::Open((Join-Path $root $item.name),'Open','Read','Read');$held.Add($stream)
            if($stream.Length -ne $item.bytes -or [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-','') -cne $item.sha256){throw 'Payload length/hash mismatch.'}
            if($item.name -ceq 'copy-cold-operating-streams.ps1'){
                $stream.Position=0;$memory=[IO.MemoryStream]::new()
                try {$stream.CopyTo($memory);$helperBytes=$memory.ToArray()}finally{$memory.Dispose()}
            }
        }
        $source=[Text.UTF8Encoding]::new($false,$true).GetString($helperBytes).TrimStart([char]0xFEFF)
        $script=[ScriptBlock]::Create($source)
        if($LibraryOnly){& $script -BundlePath $root -ExpectedBundleManifestSha256 $Pin -LibraryOnly}
        else {& $script -BundlePath $root -ExpectedBundleManifestSha256 $Pin}
    }finally{foreach($item in $held){$item.Dispose()};$sha.Dispose()}
}
Invoke-PinnedStreamsCopyCommand $BundlePath $ExpectedBundleManifestSha256 -LibraryOnly:$LibraryOnly
if($LibraryOnly){Write-Host 'LIBRARY_ONLY_VERIFIED_NO_SOURCE_DATA_ACCESSED'}
exit 0
