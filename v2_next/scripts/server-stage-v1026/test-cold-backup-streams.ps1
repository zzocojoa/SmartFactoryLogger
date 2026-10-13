param([Parameter(Mandatory=$true)][string]$OutputRoot,[Parameter(Mandatory=$true)][string]$EngineAssembly,[Parameter(Mandatory=$true)][string]$ExpectedEngineSha256,[string]$EngineNamespace='SflColdCopyStreamsV2',[switch]$LargeFile)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$checks=[Collections.Generic.List[string]]::new()
function Test([bool]$OK,[string]$Name){if(-not $OK){throw ('TEST FAILED: '+$Name)};$checks.Add($Name)}
function Reject([scriptblock]$Action,[string]$Name){$failed=$false;try{& $Action|Out-Null}catch{$failed=$true};Test $failed $Name}
Test ($PSVersionTable.PSEdition -ceq 'Desktop' -and $PSVersionTable.PSVersion.Major -eq 5 -and $PSVersionTable.PSVersion.Minor -eq 1) 'native Windows PowerShell 5.1'
$output=[IO.Path]::GetFullPath($OutputRoot)
Test (-not [IO.Directory]::Exists($output) -and -not [IO.File]::Exists($output)) 'new isolated fixture root'
[void][IO.Directory]::CreateDirectory($output)
$dll=[IO.File]::ReadAllBytes([IO.Path]::GetFullPath($EngineAssembly));$sha=[Security.Cryptography.SHA256]::Create()
try{$dllHash=[BitConverter]::ToString($sha.ComputeHash($dll)).Replace('-','')}finally{$sha.Dispose()}
Test ($dllHash -ceq $ExpectedEngineSha256) 'exact compiled engine DLL bytes'
$assembly=[Reflection.Assembly]::Load($dll)
$engineType=$assembly.GetType($EngineNamespace+'.Engine',$true)
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class NamedStreamTestFixture {
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern IntPtr CreateFileW(string p,uint a,uint s,IntPtr sa,uint c,uint f,IntPtr t);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool WriteFile(IntPtr h,byte[] b,uint n,out uint w,IntPtr o);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool ReadFile(IntPtr h,byte[] b,uint n,out uint r,IntPtr o);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool GetFileSizeEx(IntPtr h,out long n);
 [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool DeleteFileW(string p);
 public static void Write(string p,byte[] b,bool create) {var h=CreateFileW("\\\\?\\"+p,0x40000000,0,IntPtr.Zero,create?1u:3u,0x02000000,IntPtr.Zero);if(h==new IntPtr(-1))throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());try {uint n;if(!WriteFile(h,b,(uint)b.Length,out n,IntPtr.Zero)||n!=b.Length)throw new Exception("fixture write failed");}finally{CloseHandle(h);}}
 public static byte[] Read(string p) {var h=CreateFileW("\\\\?\\"+p,0x80000000,1,IntPtr.Zero,3,0x02000000,IntPtr.Zero);if(h==new IntPtr(-1))throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());try {long n;if(!GetFileSizeEx(h,out n)||n>16777216)throw new Exception("fixture size invalid");var b=new byte[(int)n];uint r;if(!ReadFile(h,b,(uint)n,out r,IntPtr.Zero)||r!=n)throw new Exception("fixture read failed");return b;}finally{CloseHandle(h);}}
 public static IntPtr HoldWrite(string p) {var h=CreateFileW("\\\\?\\"+p,0x40000000,1,IntPtr.Zero,3,0x02000000,IntPtr.Zero);if(h==new IntPtr(-1))throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());return h;}
 public static void Release(IntPtr h) {CloseHandle(h);}
 public static void Remove(string p) {if(!DeleteFileW("\\\\?\\"+p))throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());}
}
'@
function Fixture([string]$Name){
    $root=Join-Path $output $Name;[void][IO.Directory]::CreateDirectory($root)
    $a=Join-Path $root 'a';$b=Join-Path $root 'b'
    [void][IO.Directory]::CreateDirectory($a);[void][IO.Directory]::CreateDirectory($b+'\empty')
    [IO.File]::WriteAllBytes(($a+'\sample.bin'),[byte[]]@(65,66,67))
    [IO.File]::WriteAllBytes(($b+'\zero.bin'),[byte[]]@())
    $engine=[Activator]::CreateInstance($engineType,[object[]]@([string[]]@($a,$b),[Action]{},[Action[string,long,long,long]]{}))
    [pscustomobject]@{root=$root;a=$a;b=$b;engine=$engine;copy=($root+'\c');restore=($root+'\r');manifest=($root+'\files.tsv')}
}
function Stream-Path([string]$Base,[string]$Name){
    Test ($Base.StartsWith($output+'\',[StringComparison]::OrdinalIgnoreCase)) 'fixture stream operation stays in exact new test root'
    return $Base+':'+$Name
}
function Put-Stream([string]$Base,[string]$Name,[byte[]]$Bytes,[bool]$Create=$true){[NamedStreamTestFixture]::Write((Stream-Path $Base $Name),$Bytes,$Create)}
function Bytes-Equal([byte[]]$A,[byte[]]$B){return [Convert]::ToBase64String($A) -ceq [Convert]::ToBase64String($B)}
function Copy-Verify($f){$r=$f.engine.Backup($f.copy,$f.manifest);$v=$f.engine.Verify($f.manifest,$r.ManifestSha256,$f.copy,$null,$false);return [pscustomobject]@{backup=$r;verified=$v}}

$f=Fixture 'all-streams-roundtrip'
$zone=New-Object byte[] 26;for($i=0;$i -lt $zone.Length;$i++){$zone[$i]=[byte]$i}
Put-Stream ($f.a+'\sample.bin') 'Zone.Identifier' $zone
Put-Stream ($f.a+'\sample.bin') ('unicode-'+[char]0xD55C+[char]0xAE00) ([byte[]]@(255,0,13,10,128))
Put-Stream ($f.a+'\sample.bin') 'zero-length' ([byte[]]@())
Put-Stream $f.a 'directory-stream' ([byte[]]@(1,2,3,4))
$large=New-Object byte[] (3MB+19);for($i=0;$i -lt $large.Length;$i+=8192){$large[$i]=173}
Put-Stream ($f.b+'\zero.bin') 'chunked' $large
$plan=$f.engine.Inventory($f.copy)
Test ($plan.Files -eq 2 -and $plan.Directories -eq 3 -and $plan.NamedStreams -eq 5 -and $plan.Bytes -eq (3+$zone.Length+5+4+$large.Length)) 'inventory includes every named stream and exact byte budget'
Test (-not [IO.Directory]::Exists($f.copy)) 'live inventory makes no copy'
$r=Copy-Verify $f
Test ($r.verified.NamedStreams -eq 5 -and $r.verified.Bytes -eq $plan.Bytes) 'all fork hashes and memberships verified against original and copied bytes'
Test (Bytes-Equal ([NamedStreamTestFixture]::Read((Stream-Path ($f.copy+'\r0\sample.bin') 'Zone.Identifier'))) $zone) '26-byte Zone.Identifier preserved on copied file'
Test (Bytes-Equal ([NamedStreamTestFixture]::Read((Stream-Path ($f.copy+'\r0') 'directory-stream'))) ([byte[]]@(1,2,3,4))) 'directory data stream preserved on copied directory'
Test (([NamedStreamTestFixture]::Read((Stream-Path ($f.copy+'\r0\sample.bin') 'zero-length'))).Length -eq 0) 'zero-length named stream remains present'
Test (Bytes-Equal ([NamedStreamTestFixture]::Read((Stream-Path ($f.copy+'\r1\zero.bin') 'chunked'))) $large) 'named stream larger than buffer copied across chunks'
Test (Bytes-Equal ([IO.File]::ReadAllBytes($f.a+'\sample.bin')) ([byte[]]@(65,66,67))) 'ordinary source bytes unchanged'
Test (Bytes-Equal ([NamedStreamTestFixture]::Read((Stream-Path ($f.a+'\sample.bin') 'Zone.Identifier'))) $zone) 'original named stream unchanged'
Test (([IO.File]::ReadLines($f.manifest)|Select-Object -First 1) -ceq 'SFL-COLD-BACKUP-STREAMS-2') 'new grouped stream manifest format'
$restored=$f.engine.Verify($f.manifest,$r.backup.ManifestSha256,$f.copy,$f.restore,$true)
Test ($restored.NamedStreams -eq 5) 'isolated byte restoration preserves named stream totals'
Test (Bytes-Equal ([NamedStreamTestFixture]::Read((Stream-Path ($f.restore+'\r0\sample.bin') 'Zone.Identifier'))) $zone) 'isolated restored file retains Zone.Identifier'
Reject {$f.engine.Backup($f.copy,$f.root+'\new.tsv')} 'existing copy not overwritten'
Reject {$f.engine.Verify($f.manifest,('0'*64),$f.copy,$null,$false)} 'wrong manifest pin rejected'

foreach($kind in @('source-drift','copy-drift','missing-source','missing-copy','extra-source','extra-copy')){
    $f=Fixture $kind;Put-Stream ($f.a+'\sample.bin') 'Zone.Identifier' ([byte[]]@(1,2,3))
    $r=$f.engine.Backup($f.copy,$f.manifest)
    $base=if($kind.EndsWith('source') -or $kind.StartsWith('source')){$f.a+'\sample.bin'}else{$f.copy+'\r0\sample.bin'}
    $mtime=[IO.File]::GetLastWriteTimeUtc($base)
    if($kind.EndsWith('drift')){Put-Stream $base 'Zone.Identifier' ([byte[]]@(9,8,7)) $false;[IO.File]::SetLastWriteTimeUtc($base,$mtime)}
    elseif($kind.StartsWith('missing')){[NamedStreamTestFixture]::Remove((Stream-Path $base 'Zone.Identifier'));[IO.File]::SetLastWriteTimeUtc($base,$mtime)}
    else{Put-Stream $base 'extra' ([byte[]]@(4));[IO.File]::SetLastWriteTimeUtc($base,$mtime)}
    Reject {$f.engine.Verify($f.manifest,$r.ManifestSha256,$f.copy,$null,$false)} ($kind+' named stream hash or membership change detected')
    Test ([IO.File]::Exists($f.a+'\sample.bin') -and [IO.Directory]::Exists($f.copy)) 'failure preserves original and partial copy'
}
$f=Fixture 'writer-lock';Put-Stream ($f.a+'\sample.bin') 'Zone.Identifier' ([byte[]]@(1))
$handle=[NamedStreamTestFixture]::HoldWrite((Stream-Path ($f.a+'\sample.bin') 'Zone.Identifier'))
try{Reject {$f.engine.Backup($f.copy,$f.manifest)} 'active source fork writer prevents cold read lock'}finally{[NamedStreamTestFixture]::Release($handle)}
$f=Fixture 'junction';$null=New-Item -ItemType Junction -Path ($f.a+'\link') -Target $f.b
Reject {$f.engine.Inventory($f.copy)} 'reparse point rejected without following'
$f=Fixture 'bad-guard';$bad=[Activator]::CreateInstance($engineType,[object[]]@([string[]]@($f.a,$f.b),[Action]{throw 'synthetic runtime guard stop'},[Action[string,long,long,long]]{}))
Reject {$bad.Backup($f.copy,$f.manifest)} 'runtime guard aborts before writing copy'
Test (-not [IO.Directory]::Exists($f.copy)) 'guard rejection creates no copy'
Reject {$f.engine.Inventory($f.a+'\overlap')} 'overlapping destination rejected'
$f=Fixture 'default-file-drift';$r=$f.engine.Backup($f.copy,$f.manifest)
$mtime=[IO.File]::GetLastWriteTimeUtc($f.a+'\sample.bin');[IO.File]::WriteAllBytes($f.a+'\sample.bin',[byte[]]@(88,89,90));[IO.File]::SetLastWriteTimeUtc($f.a+'\sample.bin',$mtime)
Reject {$f.engine.Verify($f.manifest,$r.ManifestSha256,$f.copy,$null,$false)} 'same-size same-mtime default stream drift rejected'

$f=Fixture 'long-named-stream'
$longBase=$f.a
while($longBase.Length -lt 170){$longBase+='\nested-0123456789';[void][IO.Directory]::CreateDirectory($longBase)}
$longBase+='\'+('f'*(224-$longBase.Length-5))+'.bin'
[IO.File]::WriteAllBytes($longBase,[byte[]]@(42))
$longName='n'*180
Put-Stream $longBase $longName ([byte[]]@(0,255,127))
Test (($longBase+':'+$longName+':$DATA').Length -gt 260 -and $longBase.Length -lt 240) 'actual named stream exceeds legacy full-path limit while base remains within budget'
$r=Copy-Verify $f
$longCopy=$f.copy+'\r0'+$longBase.Substring($f.a.Length)
Test (Bytes-Equal ([NamedStreamTestFixture]::Read((Stream-Path $longCopy $longName))) ([byte[]]@(0,255,127))) 'extended native stream path retains exact long stream bytes'

foreach($kind in @('bad-parent','bad-count','duplicate-fork')){
    $f=Fixture $kind;Put-Stream ($f.a+'\sample.bin') 'first' ([byte[]]@(1));Put-Stream ($f.a+'\sample.bin') 'second' ([byte[]]@(2))
    $r=$f.engine.Backup($f.copy,$f.manifest)
    $lines=[IO.File]::ReadAllLines($f.manifest)
    $index=@(0..($lines.Length-1)|Where-Object {$lines[$_].StartsWith('A'+[char]9)})[0]
    if($kind -eq 'bad-parent'){$parts=$lines[$index].Split([char]9);$parts[1]='1';$lines[$index]=$parts -join [char]9}
    elseif($kind -eq 'bad-count'){$parts=$lines[$index-1].Split([char]9);$parts[9]='1';$lines[$index-1]=$parts -join [char]9}
    else{$lines[$index+1]=$lines[$index]}
    [IO.File]::WriteAllLines($f.manifest,$lines,[Text.UTF8Encoding]::new($false,$true))
    $forgedHash=(Get-FileHash -LiteralPath $f.manifest -Algorithm SHA256).Hash
    Reject {$f.engine.Verify($f.manifest,$forgedHash,$f.copy,$null,$false)} ($kind+' rejected even when new manifest hash supplied')
}
$f=Fixture 'readonly-source';[IO.File]::SetAttributes(($f.a+'\sample.bin'),[IO.FileAttributes]::ReadOnly)
Put-Stream $f.a 'directory-mark' ([byte[]]@(3))
$beforeACL=[IO.File]::GetAccessControl($f.a+'\sample.bin').GetSecurityDescriptorSddlForm([Security.AccessControl.AccessControlSections]::All)
$r=Copy-Verify $f
Test ([IO.File]::GetAttributes($f.a+'\sample.bin') -eq [IO.FileAttributes]::ReadOnly) 'original readonly attribute retained'
Test ([IO.File]::GetAccessControl($f.a+'\sample.bin').GetSecurityDescriptorSddlForm([Security.AccessControl.AccessControlSections]::All) -ceq $beforeACL) 'original file ACL retained'
$f=Fixture 'default-writer-lock';$lock=[IO.File]::Open(($f.a+'\sample.bin'),'Open','Write','Read')
try{Reject {$f.engine.Backup($f.copy,$f.manifest)} 'active default stream writer prevents cold read lock'}finally{$lock.Dispose()}
foreach($kind in @('extra-main-source','extra-main-copy','missing-main-copy')){
    $f=Fixture $kind;$r=$f.engine.Backup($f.copy,$f.manifest)
    if($kind -eq 'extra-main-source'){[IO.File]::WriteAllText(($f.a+'\extra.txt'),'extra')}
    elseif($kind -eq 'extra-main-copy'){[IO.File]::WriteAllText(($f.copy+'\r0\extra.txt'),'extra')}
    else{$target=$f.copy+'\r0\sample.bin';Test ($target.StartsWith($output+'\',[StringComparison]::OrdinalIgnoreCase)) 'fixture-only default file removal boundary';[IO.File]::Delete($target)}
    Reject {$f.engine.Verify($f.manifest,$r.ManifestSha256,$f.copy,$null,$false)} ($kind+' rejected')
}
foreach($badPath in @('C:\','C:relative','\\server\share','C:\scope\..\secret','C:\scope\file:stream','C:\scope\CON.txt','C:\scope\x.','C:\scope\x ','C:\scope\PROGRA~1','C:\scope\a?','C:\scope\\b',('C:\scope\'+[char]10+'x'))){
    Reject {$engineType.GetMethod('Canonical').Invoke($null,[object[]]@($badPath))} 'invalid source/target base path rejected'
}
if($LargeFile){
    $f=Fixture 'ordinary-over-two-gib';$largePath=$f.a+'\large-zero.bin'
    $multiGibStream=[IO.File]::Open($largePath,'CreateNew','Write','None')
    try{$multiGibStream.SetLength(([long]2147483648)+17);$multiGibStream.Flush($true)}finally{$multiGibStream.Dispose()}
    $r=Copy-Verify $f
    Test ($r.verified.Bytes -gt 2147483648 -and $r.verified.Files -eq 3) 'real ordinary file over two GiB copied and source/copy rehashed'
}
$result=[ordered]@{status='PASS';assertions=$checks.Count;checks=$checks.ToArray();native_ps_version=$PSVersionTable.PSVersion.ToString();engine_dll_sha256=$dllHash;test_fixture_root=$output;multi_gib_file_tested=[bool]$LargeFile;real_server_data_read=$false;actual_server_shutdown_tested=$false;application_restore_QA_performed=$false}
[IO.File]::WriteAllText((Join-Path $output 'validation-result.json'),($result|ConvertTo-Json -Depth 6),[Text.UTF8Encoding]::new($false,$true))
[pscustomobject]$result|Select-Object status,assertions,native_ps_version,engine_dll_sha256|ConvertTo-Json
