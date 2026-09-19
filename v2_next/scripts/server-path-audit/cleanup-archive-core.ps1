# Shared by the fixed server entry point and synthetic Windows 5.1 tests.
# Never execute inspected scripts or restore/install anything from a retained ZIP.
function Initialize-CleanupNative {
    if ('SflCleanupNativeV1' -as [type]) { return }
    Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Text;
using System.ComponentModel;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class SflCleanupNativeV1 {
    [StructLayout(LayoutKind.Sequential)] struct Info {
        public uint Attr; public System.Runtime.InteropServices.ComTypes.FILETIME Created, Accessed, Written;
        public uint Volume, SizeHigh, SizeLow, Links, IndexHigh, IndexLow;
    }
    [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)] struct StreamInfo {
        public long Size; [MarshalAs(UnmanagedType.ByValTStr, SizeConst=296)] public string Name;
    }
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern SafeFileHandle CreateFileW(string p,uint a,uint share,IntPtr s,uint creation,uint flags,IntPtr t);
    [DllImport("kernel32.dll", SetLastError=true)] static extern bool GetFileInformationByHandle(SafeFileHandle h,out Info i);
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern uint GetFinalPathNameByHandleW(SafeFileHandle h,StringBuilder p,uint n,uint flags);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool SetFileInformationByHandle(SafeFileHandle h,int kind,ref byte value,uint size);
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern IntPtr FindFirstStreamW(string p,int level,out StreamInfo data,uint flags);
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern bool FindNextStreamW(IntPtr h,out StreamInfo data);
    [DllImport("kernel32.dll")] static extern bool FindClose(IntPtr h);
    static Exception Error() { return new Win32Exception(Marshal.GetLastWin32Error()); }
    public static string Identity(SafeFileHandle h,string p,bool directory) {
        Info i; if(!GetFileInformationByHandle(h,out i)) throw Error();
        if((i.Attr & 0x400)!=0 || ((i.Attr & 0x10)!=0)!=directory) throw new IOException("Reparse/type mismatch.");
        if(!directory && i.Links!=1) throw new IOException("Hard-linked file is not eligible.");
        var b=new StringBuilder(1024); uint n=GetFinalPathNameByHandleW(h,b,1024,0);
        if(n==0 || n>=1024) throw Error();
        string actual=b.ToString(); if(actual.StartsWith(@"\\?\")) actual=actual.Substring(4);
        if(!String.Equals(actual.TrimEnd('\\'),Path.GetFullPath(p).TrimEnd('\\'),StringComparison.OrdinalIgnoreCase))
            throw new IOException("Opened handle path differs.");
        return i.Volume.ToString("X8")+":"+i.IndexHigh.ToString("X8")+i.IndexLow.ToString("X8");
    }
    static SafeFileHandle Open(string p,bool directory,bool delete) {
        // OPEN_REPARSE_POINT plus handle checks; never follow a final symlink.
        uint access=directory ? 0U : 0x80000000U;
        if(delete) access|=0x10000U;
        var h=CreateFileW(p,access,(directory && !delete) ? 3U : 1U,IntPtr.Zero,3,0x02200000U,IntPtr.Zero);
        if(h.IsInvalid) { h.Dispose(); throw Error(); }
        try { Identity(h,p,directory); return h; } catch { h.Dispose(); throw; }
    }
    public static SafeFileHandle GuardDirectory(string p) { return Open(p,true,false); }
    public static FileStream OpenFile(string p,bool delete) {
        var h=Open(p,false,delete);
        try { return new FileStream(h,FileAccess.Read); } catch { h.Dispose(); throw; }
    }
    public static void NoAlternateStreams(string p,bool directory) {
        StreamInfo data; var h=FindFirstStreamW(p,0,out data,0);
        if(h==new IntPtr(-1)) {
            int e=Marshal.GetLastWin32Error();
            if(directory && e==38) return;
            throw new Win32Exception(e);
        }
        try {
            do { if(data.Name!="::$DATA") throw new IOException("Unarchived alternate stream; preserve item."); }
            while(FindNextStreamW(h,out data));
            int e=Marshal.GetLastWin32Error(); if(e!=38) throw new Win32Exception(e);
        } finally { FindClose(h); }
    }
    public static void MarkFile(FileStream s) {
        byte remove=1; if(!SetFileInformationByHandle(s.SafeFileHandle,4,ref remove,1)) throw Error();
    }
    public static void DeleteEmptyDirectory(string p,string expectedIdentity) {
        using(var h=Open(p,true,true)) {
            if(Identity(h,p,true)!=expectedIdentity) throw new IOException("Directory identity changed.");
            NoAlternateStreams(p,true);
            if(Directory.GetFileSystemEntries(p).Length!=0) throw new IOException("Directory is not empty.");
            byte remove=1; if(!SetFileInformationByHandle(h,4,ref remove,1)) throw Error();
        }
    }
}
'@
}

function Assert-CleanupChild {
    param([string]$Root,[string]$Path)
    Assert-QPlain $Root
    Assert-QPlain $Path
    if (-not $Path.StartsWith($Root.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)) {
        throw 'Delete target is not a strict child of the approved quarantine.'
    }
}

function Open-CleanupDirectoryGuard {
    param([string]$Path,[hashtable]$Guards)
    $parent=[IO.Directory]::GetParent($Path)
    if ($null -ne $parent -and -not $Guards.ContainsKey($parent.FullName)) {
        Open-CleanupDirectoryGuard $parent.FullName $Guards
    }
    if (-not $Guards.ContainsKey($Path)) {
        Assert-QPlain $Path
        $handle=[SflCleanupNativeV1]::GuardDirectory($Path)
        try {
            $Guards[$Path]=[pscustomobject]@{handle=$handle;identity=[SflCleanupNativeV1]::Identity($handle,$Path,$true)}
        } catch { $handle.Dispose(); throw }
    }
}

function Get-CleanupZipIndex {
    param([IO.Stream]$Stream,[ref]$ExpandedTotal)
    $Stream.Position=0
    $zip=[IO.Compression.ZipArchive]::new($Stream,'Read',$true)
    $index=@{}; $seen=@{}; $directories=@{}
    try {
        if ($zip.Entries.Count -gt 10000) { throw 'Archive entry limit.' }
        foreach ($entry in $zip.Entries) {
            $name=$entry.FullName.Replace('/','\'); $directory=$name.EndsWith('\')
            if ($directory) { $name=$name.Substring(0,$name.Length-1) }
            Assert-QRelative $name
            $unixType=($entry.ExternalAttributes -shr 16) -band 0xF000
            if ($seen.ContainsKey($name) -or $name.Length -gt 259 -or
                $unixType -notin @(0,0x8000,0x4000) -or
                ($unixType -eq 0x4000 -and -not $directory) -or
                ($unixType -eq 0x8000 -and $directory) -or
                (($entry.ExternalAttributes -band 0x10) -ne 0 -and -not $directory) -or
                ($entry.ExternalAttributes -band 0x400) -ne 0) { throw 'Unsafe/ambiguous archive entry.' }
            $seen[$name]=$true
            if ($directory) {
                if ($entry.Length -ne 0) { throw 'Nonempty archive directory entry.' }
                $directories[$name]=$true; continue
            }
            if ($entry.Length -gt 600MB -or $ExpandedTotal.Value+$entry.Length -gt 3GB) { throw 'ZIP expansion budget reached.' }
            $inputStream=$entry.Open(); $sha=[Security.Cryptography.SHA256]::Create()
            $actual=0L; $buffer=New-Object byte[] 65536
            try {
                while (($read=$inputStream.Read($buffer,0,$buffer.Length)) -gt 0) {
                    $actual+=$read
                    if ($actual -gt $entry.Length) { throw 'ZIP expansion exceeded entry length.' }
                    $null=$sha.TransformBlock($buffer,0,$read,$buffer,0)
                }
                $null=$sha.TransformFinalBlock($buffer,0,0)
                if ($actual -ne $entry.Length) { throw 'Truncated archive entry.' }
                $index[$name]=[pscustomobject]@{entry=$entry.FullName;length=$actual;sha256=[BitConverter]::ToString($sha.Hash).Replace('-','')}
                $ExpandedTotal.Value+=$actual
            } finally { $sha.Dispose(); $inputStream.Dispose() }
        }
        foreach ($name in @($seen.Keys)) {
            $parent=[IO.Path]::GetDirectoryName($name)
            while (-not [string]::IsNullOrEmpty($parent)) {
                if ($index.ContainsKey($parent)) { throw 'Archive file/directory prefix conflict.' }
                $parent=[IO.Path]::GetDirectoryName($parent)
            }
        }
        return ,$index
    } finally { $zip.Dispose() }
}

function Find-CleanupArchiveMapping {
    param([string]$Top,[object[]]$Files,[hashtable]$Index)
    if ($Files.Count -eq 0) { return }
    # Only a ZIP root or its exact top folder; no basename/suffix guessing.
    foreach ($prefix in @('',($Top+'\'))) {
        $matches=[Collections.Generic.List[object]]::new()
        foreach ($row in $Files) {
            $key=$prefix+$row.relative_path.Substring($Top.Length+1)
            if (-not $Index.ContainsKey($key)) { break }
            $entry=$Index[$key]
            # Hashtable lookup is case insensitive; require exact entry spelling too.
            if ($entry.entry.Replace('/','\') -cne $key -or $entry.length -ne $row.length -or $entry.sha256 -cne $row.sha256) { break }
            $matches.Add([pscustomobject]@{relative_path=$row.relative_path;length=$row.length;sha256=$row.sha256;zip_entry=$entry.entry})
        }
        if ($matches.Count -eq $Files.Count) { return ,$matches.ToArray() }
    }
}

function Protect-CleanupReferences {
    param([hashtable]$Candidates,[hashtable]$Texts,[hashtable]$Protected)
    do {
        $changed=$false
        foreach ($relative in @($Texts.Keys | Sort-Object)) {
            $owner=$relative.Split('\')[0]
            if ($Candidates.ContainsKey($owner) -and -not $Protected.ContainsKey($owner)) { continue }
            foreach ($top in @($Candidates.Keys)) {
                if ($Protected.ContainsKey($top)) { continue }
                if (@(Find-QReferences $Texts[$relative] @($top)).Count -gt 0) {
                    $Protected[$top]='retained-text-reference:'+ $relative; $changed=$true
                }
            }
        }
    } while ($changed)
}

function Assert-CleanupReferenceCoverage {
    param([object[]]$Coverage)
    $legacyName=-join ([char[]]@(0xD504,0xB85C,0xADF8,0xB7A8))
    $allowedJunctions=@(('C:\Users\user\AppData\Roaming\Microsoft\Windows\Start Menu\'+$legacyName),
        ('C:\ProgramData\Microsoft\Windows\Start Menu\'+$legacyName))
    foreach ($row in $Coverage) {
        if ($null -ne $row.PSObject.Properties['status'] -or $row.read_errors -gt 0 -or
            $row.size_or_budget_skipped -gt 0 -or $row.omitted_hits -gt 0) {
            throw 'Scoped reference read incomplete.'
        }
        foreach ($issue in $row.enumeration_issues) {
            if ($issue.kind -ceq 'DEPTH_NOT_INSPECTED') { continue }
            if ($issue.kind -ceq 'REPARSE_SKIPPED' -and $row.kind -ceq 'shortcut' -and $issue.path -cin $allowedJunctions) { continue }
            throw 'Unexpected scoped enumeration gap or reparse point.'
        }
    }
}

function Write-CleanupRecord {
    param([IO.FileStream]$Journal,[object]$Record)
    $bytes=[Text.UTF8Encoding]::new($false).GetBytes(($Record | ConvertTo-Json -Depth 15 -Compress)+"`n")
    $Journal.Write($bytes,0,$bytes.Length); $Journal.Flush($true)
}

function New-CleanupPrivateDirectory {
    param([string]$Path)
    if ([IO.File]::Exists($Path)) { throw 'File blocks receipt directory.' }
    if (-not [IO.Directory]::Exists($Path)) {
        Assert-QPlain ([IO.Directory]::GetParent($Path).FullName)
        $acl=[Security.AccessControl.DirectorySecurity]::new()
        $acl.SetAccessRuleProtection($true,$false)
        $acl.SetOwner([Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))
        foreach ($sid in @('S-1-5-18','S-1-5-32-544')) {
            $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
                [Security.Principal.SecurityIdentifier]::new($sid),'FullControl','ContainerInherit,ObjectInherit','None','Allow'))
        }
        $null=[IO.Directory]::CreateDirectory($Path,$acl)
    }
    Assert-QPlain $Path
    $actual=[IO.Directory]::GetAccessControl($Path)
    if ($actual.GetOwner([Security.Principal.SecurityIdentifier]).Value -notin @('S-1-5-18','S-1-5-32-544') -or
        -not $actual.AreAccessRulesProtected) { throw 'Existing receipt directory ownership/inheritance is not approved.' }
    $rules=$actual.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])
    foreach ($rule in $rules) {
        if ($rule.AccessControlType -ne 'Allow' -or $rule.IdentityReference.Value -notin @('S-1-5-18','S-1-5-32-544')) {
            throw 'Existing receipt directory ACL is not administrator/SYSTEM-only.'
        }
    }
}

function Remove-CleanupVerifiedFile {
    param([string]$Root,[object]$Row,[string]$ExpectedIdentity,[IO.FileStream]$Journal,
        [IO.FileStream]$VerifiedStream=$null,[Collections.Generic.List[object]]$Confirmed=$null)
    $path=Join-Path $Root $Row.relative_path
    Assert-CleanupChild $Root $path
    $s=$VerifiedStream
    if ($null -eq $s) { $s=[SflCleanupNativeV1]::OpenFile($path,$true) }
    try {
        if ([SflCleanupNativeV1]::Identity($s.SafeFileHandle,$path,$false) -cne $ExpectedIdentity -or
            $s.Length -ne $Row.length -or (Get-QHash $s) -cne $Row.sha256) { throw 'Delete target changed; preserved.' }
        [SflCleanupNativeV1]::NoAlternateStreams($path,$false)
        Write-CleanupRecord $Journal ([pscustomobject]@{event='DELETE_INTENT';at=[DateTimeOffset]::Now.ToString('o');file=$Row})
        # Same verified handle, not a second path-based Delete call. Errors do not clear attributes.
        [SflCleanupNativeV1]::MarkFile($s)
    } finally { $s.Dispose() }
    if ([IO.File]::Exists($path) -or [IO.Directory]::Exists($path)) { throw 'Deletion not confirmed; stop without retry.' }
    if ($null -ne $Confirmed) { $Confirmed.Add($Row) }
    Write-CleanupRecord $Journal ([pscustomobject]@{event='DELETED';at=[DateTimeOffset]::Now.ToString('o');relative_path=$Row.relative_path})
}
