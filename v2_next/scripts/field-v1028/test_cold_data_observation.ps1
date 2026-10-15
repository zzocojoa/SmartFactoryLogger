param(
    [Parameter(Mandatory=$true)][string]$OutputRoot,
    [Parameter(Mandatory=$true)][string]$EngineAssembly
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$checks=[Collections.Generic.List[string]]::new()
function Test([bool]$Value,[string]$Name){if(-not $Value){throw ('FAILED: '+$Name)};$checks.Add($Name)}
function Reject([scriptblock]$Action,[string]$Name){
    $failure=$null;try{& $Action|Out-Null}catch{$failure=$_.Exception.Message}
    Test ($null -ne $failure) ($Name+': '+$failure)
}
function Hash([string]$Path){return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash}
Test ($PSVersionTable.PSEdition -ceq 'Desktop' -and [Environment]::Is64BitProcess) 'PS51-x64-runtime'
$output=[IO.Path]::GetFullPath($OutputRoot)
Test (-not (Test-Path -LiteralPath $output)) 'fresh-output'
$null=[IO.Directory]::CreateDirectory($output)
Test ((Hash $EngineAssembly) -ceq 'FB12E3ACB370D86999156600EFB3CD23083D890DFEC1216CF4E06E9C1CCE2A26') 'pinned-stream-engine'
[void][Reflection.Assembly]::LoadFrom([IO.Path]::GetFullPath($EngineAssembly))
$source=Join-Path $PSScriptRoot 'cold-data-observation.cs'
$observerDll=Join-Path $output 'observer.dll'
Add-Type -Path $source -ReferencedAssemblies @($EngineAssembly,'System.dll','System.Core.dll') -OutputAssembly $observerDll
[void][Reflection.Assembly]::LoadFrom($observerDll)
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class ObservationForkFixture {
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern IntPtr CreateFileW(string p,uint a,uint s,IntPtr sa,uint c,uint f,IntPtr t);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool WriteFile(IntPtr h,byte[] b,uint n,out uint w,IntPtr o);
 [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool DeleteFileW(string p);
 public static void Put(string p,byte[] b,bool create) {
  var h=CreateFileW("\\\\?\\"+p,0x40000000,0,IntPtr.Zero,create?1u:3u,0x02000000,IntPtr.Zero);
  if(h==new IntPtr(-1))throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
  try{uint written;if(!WriteFile(h,b,(uint)b.Length,out written,IntPtr.Zero)||written!=b.Length)throw new Exception("fixture-write");}finally{CloseHandle(h);}
 }
 public static void Remove(string p){if(!DeleteFileW("\\\\?\\"+p))throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());}
}
'@
function PutFork([string]$Path,[byte[]]$Bytes,[bool]$Create=$true){
    Test ($Path.StartsWith($output+'\',[StringComparison]::OrdinalIgnoreCase)) 'fixture-write-boundary'
    [ObservationForkFixture]::Put($Path,$Bytes,$Create)
}
function Fixture([string]$Name){
    $root=Join-Path $output $Name;$a=$root+'\a';$b=$root+'\b'
    $null=[IO.Directory]::CreateDirectory($a);$null=[IO.Directory]::CreateDirectory($b+'\empty')
    $file=$a+'\sample.bin';[IO.File]::WriteAllBytes($file,[byte[]]@(65,66,67))
    [IO.File]::WriteAllBytes(($b+'\zero.bin'),[byte[]]@())
    PutFork ($file+':proof') ([byte[]]@(4,5,6))
    PutFork ($file+':empty') ([byte[]]@())
    PutFork ($a+':directory-proof') ([byte[]]@(7,8))
    $observer=[SflColdObservationV1.Observer]::new([string[]]@($a,$b),[Action]{},[Action[string,long,long,long]]{})
    return [pscustomobject]@{root=$root;a=$a;b=$b;file=$file;manifest=$root+'\observed.tsv';observer=$observer}
}
$f=Fixture 'roundtrip'
$large=New-Object byte[] (3MB+19);$large[0]=173;$large[$large.Length-1]=229
PutFork ($f.file+':large') $large
$captured=$f.observer.Capture($f.manifest)
$verified=$f.observer.Verify($f.manifest,$captured.ManifestSha256)
Test ($verified.Files -eq 2 -and $verified.Directories -eq 3 -and $verified.NamedStreams -eq 4 -and $verified.Bytes -eq (8+$large.Length)) 'exact-default-directory-and-named-stream-counts'
Test (-not $verified.RecoverableBackupCreated -and @([IO.Directory]::GetFileSystemEntries($f.root)).Count -eq 3) 'only-manifest-created-no-data-copy'
Test (([IO.File]::ReadAllText($f.manifest)).StartsWith('SFL-COLD-OBSERVATION-1'+[char]10+'ROOT'+[char]9)) 'distinct-observation-format-and-root-binding'
Test ((Hash $f.manifest) -ceq $captured.ManifestSha256) 'manifest-pin'
Reject {$f.observer.Capture($f.manifest)} 'existing-manifest-not-overwritten'
Reject {$f.observer.Capture($f.a+'\inside.tsv')} 'manifest-inside-source-rejected'
Reject {$f.observer.Verify($f.manifest,('0'*64))} 'wrong-pin-rejected'
Reject {[SflColdObservationV1.Observer]::new([string[]]@($f.a,$f.a),[Action]{},[Action[string,long,long,long]]{})} 'overlapping-roots-rejected'

foreach($kind in @('default-content','named-content','missing-stream','extra-stream','extra-file','missing-file','metadata','directory-stream','manifest-extra','manifest-truncated','writer-lock','reparse')){
    $f=Fixture $kind;$captured=$f.observer.Capture($f.manifest)
    $fileTime=[IO.File]::GetLastWriteTimeUtc($f.file);$dirTime=[IO.Directory]::GetLastWriteTimeUtc($f.a)
    $pin=$captured.ManifestSha256;$lock=$null
    try{
        switch($kind){
            'default-content' {[IO.File]::WriteAllBytes($f.file,[byte[]]@(90,91,92));[IO.File]::SetLastWriteTimeUtc($f.file,$fileTime)}
            'named-content' {PutFork ($f.file+':proof') ([byte[]]@(1,2,3)) $false;[IO.File]::SetLastWriteTimeUtc($f.file,$fileTime)}
            'missing-stream' {[ObservationForkFixture]::Remove($f.file+':proof');[IO.File]::SetLastWriteTimeUtc($f.file,$fileTime)}
            'extra-stream' {PutFork ($f.file+':extra') ([byte[]]@(9));[IO.File]::SetLastWriteTimeUtc($f.file,$fileTime)}
            'extra-file' {[IO.File]::WriteAllText($f.a+'\extra.txt','new');[IO.Directory]::SetLastWriteTimeUtc($f.a,$dirTime)}
            'missing-file' {[IO.File]::Delete($f.file);[IO.Directory]::SetLastWriteTimeUtc($f.a,$dirTime)}
            'metadata' {[IO.File]::SetCreationTimeUtc($f.file,[DateTime]::UtcNow.AddDays(-2))}
            'directory-stream' {PutFork ($f.a+':directory-proof') ([byte[]]@(1,1)) $false;[IO.Directory]::SetLastWriteTimeUtc($f.a,$dirTime)}
            'manifest-extra' {[IO.File]::AppendAllText($f.manifest,('EXTRA'+[char]10));$pin=Hash $f.manifest}
            'manifest-truncated' {$raw=[IO.File]::ReadAllBytes($f.manifest);[IO.File]::WriteAllBytes($f.manifest,$raw[0..($raw.Length-3)]);$pin=Hash $f.manifest}
            'writer-lock' {$lock=[IO.File]::Open($f.file,'Open','Write','Read')}
            'reparse' {$null=New-Item -ItemType Junction -Path ($f.a+'\linked') -Target $f.b;[IO.Directory]::SetLastWriteTimeUtc($f.a,$dirTime)}
        }
        Reject {$f.observer.Verify($f.manifest,$pin)} ($kind+' rejected')
    }finally{if($lock){$lock.Dispose()}}
}
$f=Fixture 'guard'
$guarded=[SflColdObservationV1.Observer]::new([string[]]@($f.a,$f.b),[Action]{throw 'runtime-active'},[Action[string,long,long,long]]{})
Reject {$guarded.Capture($f.manifest)} 'active-runtime-before-capture-rejected'
Test (-not [IO.File]::Exists($f.manifest)) 'guard-failure-created-no-manifest'
$result=[ordered]@{status='PASS';scope='LOCAL_SYNTHETIC_NTFS_OBSERVATION_ONLY';checks=$checks.Count;names=$checks.ToArray();source_sha256=(Hash $source);observer_dll_sha256=(Hash $observerDll);server_accessed=$false;recoverable_backup_created=$false}
[IO.File]::WriteAllText(($output+'\tests-result.json'),($result|ConvertTo-Json -Depth 6),[Text.UTF8Encoding]::new($false))
$result|ConvertTo-Json -Depth 6
