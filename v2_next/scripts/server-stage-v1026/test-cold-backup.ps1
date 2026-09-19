param([Parameter(Mandatory=$true)][string]$OutputRoot,[switch]$LargeFile,[string]$EngineAssembly,[string]$ExpectedEngineSha256)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$checks=[Collections.Generic.List[string]]::new()
function Test {param([bool]$OK,[string]$Name) if(-not $OK){throw ('TEST FAILED: '+$Name)};$checks.Add($Name)}
function Reject {param([scriptblock]$Code,[string]$Name) $failed=$false;try{& $Code|Out-Null}catch{$failed=$true};Test $failed $Name}
Test ($PSVersionTable.PSEdition -ceq 'Desktop' -and $PSVersionTable.PSVersion.Major -eq 5 -and $PSVersionTable.PSVersion.Minor -eq 1) 'native PS51 test host'
$output=[IO.Path]::GetFullPath($OutputRoot)
Test (-not [IO.Directory]::Exists($output) -and -not [IO.File]::Exists($output)) 'new fixture root'
[void][IO.Directory]::CreateDirectory($output)
$engineSource=[IO.File]::ReadAllText((Join-Path $PSScriptRoot 'cold-backup-core.cs'))
if($EngineAssembly){
    $engineBytes=[IO.File]::ReadAllBytes([IO.Path]::GetFullPath($EngineAssembly));$sha=[Security.Cryptography.SHA256]::Create()
    try{$loadedHash=[BitConverter]::ToString($sha.ComputeHash($engineBytes)).Replace('-','')}finally{$sha.Dispose()}
    Test ($loadedHash -ceq $ExpectedEngineSha256) 'exact shipped engine DLL bytes'
    [void][Reflection.Assembly]::Load($engineBytes)
}else{Add-Type -TypeDefinition $engineSource -Language CSharp;$loadedHash=$null}
$helper=Join-Path $PSScriptRoot 'backup-restore-v1025.ps1'
$tokens=$null;$parseErrors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($helper,[ref]$tokens,[ref]$parseErrors)
Test ($parseErrors.Count -eq 0) 'wrapper parses'
$functions=@($ast.FindAll({param($n)$n -is [Management.Automation.Language.FunctionDefinitionAst]},$true))
foreach($f in $functions){. ([scriptblock]::Create($f.Extent.Text))}
$helperText=[IO.File]::ReadAllText($helper)
$commands=@($ast.FindAll({param($n)$n -is [Management.Automation.Language.CommandAst]},$true)|ForEach-Object {$_.GetCommandName()})
Test (@($commands|Where-Object {$_ -cin @('Stop-Process','taskkill','Start-Process','Remove-Item','Move-Item','Copy-Item','Invoke-Expression','Expand-Archive')}).Count -eq 0) 'no mutation/control commands (warnings aside)'
Test ($engineSource -notmatch '\b(File|Directory)\.(Delete|Move)|FileMode\.(Create|Truncate|Append)\b|File\.WriteAll') 'engine writes CreateNew only; no delete/move/overwrite'
Test ($helperText.Contains('if(-not $Execute)')) 'default non-execution gate'
Test ($helperText.Contains("-ceq 'BACKUP V1.0.25'")) 'explicit maintenance token'
Test ($helperText.Contains('WaitForExit(0)')) 'nonblocking retained process exit-code check'
Test ($helperText.Contains("'backend.shutdown-failed'")) 'shutdown failed event rejected'
Test ($helperText.Contains('original_acls_applied=$false') -and $helperText.Contains('application_restore_test_performed=$false')) 'no false ACL or application restoration claim'
Test ($helperText.Contains('installation_ready=$false')) 'no installation readiness promotion'
foreach($bad in @('C:\','C:relative','\\server\share','C:\scope\..\secret','C:\scope\file:stream','C:\scope\CON.txt','C:\scope\x.',
    'C:\scope\x ','C:\scope\PROGRA~1','C:\scope\a?','C:\scope\\b',('C:\scope\'+[char]10+'x'))){Reject {[SflColdBackupV1.Engine]::Canonical($bad)} 'bad path rejected'}
Test ([SflColdBackupV1.Engine]::Within('C:\scope\child','c:\SCOPE')) 'case-insensitive containment'
Test (-not [SflColdBackupV1.Engine]::Within('C:\scope-other','C:\scope')) 'prefix sibling rejected'
Test ([SflColdBackupV1.Engine]::RequiredSpace(100,10) -eq (10GB+210+163840)) 'two copies and metadata capacity budget'
Reject {[SflColdBackupV1.Engine]::RequiredSpace([long]::MaxValue,1)} 'capacity overflow rejected'
Reject {[SflColdBackupV1.Engine]::RequiredSpace(1,-1)} 'negative entry count rejected'
$script:guardCalls=0
$guard=[Action]{$script:guardCalls++}
$progress=[Action[string,long,long,long]]{param($name,$done,$count,$millis)}
function Fixture {
    param([string]$Name)
    $root=Join-Path $output $Name;[void][IO.Directory]::CreateDirectory($root)
    $a=Join-Path $root 'sourceA';$b=Join-Path $root 'sourceB'
    [void][IO.Directory]::CreateDirectory($a+'\empty');[void][IO.Directory]::CreateDirectory($b+'\nested')
    [IO.File]::WriteAllBytes($a+'\alpha.txt',[byte[]]@(65,66,67))
    [IO.File]::WriteAllBytes($a+'\zero.bin',[byte[]]@())
    [IO.File]::WriteAllText(($b+'\nested\unicode-'+[char]0xD55C+[char]0xAE00+'.json'),'synthetic private value',[Text.UTF8Encoding]::new($false))
    [pscustomobject]@{root=$root;a=$a;b=$b;engine=[SflColdBackupV1.Engine]::new([string[]]@($a,$b),$guard,$progress);
        backup=($root+'\backup');restore=($root+'\restore');manifest=($root+'\files.tsv')}
}
$f=Fixture 'roundtrip'
$large=New-Object byte[] 3145737;for($i=0;$i -lt $large.Length;$i+=8192){$large[$i]=173}
[IO.File]::WriteAllBytes($f.a+'\stream.bin',$large)
[IO.File]::SetAttributes($f.a+'\alpha.txt',[IO.FileAttributes]::ReadOnly)
$plan=$f.engine.Inventory($f.restore)
Test ($plan.Files -eq 4 -and $plan.Directories -eq 4 -and $plan.Bytes -gt 3MB) 'recursive inventory with empty dirs, Unicode and stream chunks'
$backup=$f.engine.Backup($f.backup,$f.manifest)
Test ($backup.Files -eq $plan.Files -and $backup.Bytes -eq $plan.Bytes) 'backup exactly covers cold inventory'
$r=$f.engine.Verify($f.manifest,$backup.ManifestSha256,$f.backup,$f.restore,$true)
$v=$f.engine.Verify($f.manifest,$backup.ManifestSha256,$f.restore,$null,$false)
Test ($v.Files -eq 4 -and $v.Bytes -eq $plan.Bytes) 'backup reopened, restored files reopened, original sources rehashed'
Test ([IO.Directory]::Exists($f.restore+'\r0\empty')) 'empty directory restoration'
Test ([IO.File]::GetAttributes($f.a+'\alpha.txt') -eq [IO.FileAttributes]::ReadOnly) 'source readonly attribute unchanged'
Test ($guardCalls -gt 5) 'guard invoked during phases'
Reject {$f.engine.Backup($f.backup,$f.root+'\second.tsv')} 'existing backup preserved'
Reject {$f.engine.Verify($f.manifest,$backup.ManifestSha256,$f.backup,$f.restore,$true)} 'existing rehearsal preserved'
Reject {$f.engine.Inventory($f.a+'\nested-destination')} 'overlapping destination rejected'
Reject {[SflColdBackupV1.Engine]::new([string[]]@($f.a,$f.a+'\empty'),$guard,$progress)} 'overlapping sources rejected'
Reject {$f.engine.Verify($f.manifest,('0'*64),$f.backup,$null,$false)} 'wrong manifest pin rejected'

$f=Fixture 'backup-corruption';$r=$f.engine.Backup($f.backup,$f.manifest)
[IO.File]::WriteAllBytes($f.backup+'\r0\alpha.txt',[byte[]]@(88,89,90))
Reject {$f.engine.Verify($f.manifest,$r.ManifestSha256,$f.backup,$f.restore,$true)} 'backup corruption detected on readback'
Test ([IO.File]::Exists($f.a+'\alpha.txt') -and [IO.Directory]::Exists($f.backup)) 'failure preserves original and partial backup'
$f=Fixture 'restored-corruption';$r=$f.engine.Backup($f.backup,$f.manifest)
$null=$f.engine.Verify($f.manifest,$r.ManifestSha256,$f.backup,$f.restore,$true)
[IO.File]::WriteAllBytes($f.restore+'\r0\alpha.txt',[byte[]]@(88,89,90))
Reject {$f.engine.Verify($f.manifest,$r.ManifestSha256,$f.restore,$null,$false)} 'restored corruption detected'
$f=Fixture 'source-content-drift';$r=$f.engine.Backup($f.backup,$f.manifest)
$null=$f.engine.Verify($f.manifest,$r.ManifestSha256,$f.backup,$f.restore,$true)
$old=[IO.File]::GetLastWriteTimeUtc($f.a+'\alpha.txt')
[IO.File]::WriteAllBytes($f.a+'\alpha.txt',[byte[]]@(88,89,90));[IO.File]::SetLastWriteTimeUtc($f.a+'\alpha.txt',$old)
Reject {$f.engine.Verify($f.manifest,$r.ManifestSha256,$f.restore,$null,$false)} 'same-size same-mtime source change still rejected by SHA256'
$f=Fixture 'extra-backup-member';$r=$f.engine.Backup($f.backup,$f.manifest)
[IO.File]::WriteAllText($f.backup+'\r0\extra.txt','extra')
Reject {$f.engine.Verify($f.manifest,$r.ManifestSha256,$f.backup,$f.restore,$true)} 'extra backup member rejected'
$f=Fixture 'extra-source-member';$r=$f.engine.Backup($f.backup,$f.manifest)
[IO.File]::WriteAllText($f.a+'\extra.txt','extra')
Reject {$f.engine.Verify($f.manifest,$r.ManifestSha256,$f.backup,$f.restore,$true)} 'extra source member rejected'
$f=Fixture 'ads';Set-Content -LiteralPath ($f.a+'\alpha.txt') -Stream hidden -Value 'synthetic ADS'
Reject {$f.engine.Inventory($f.restore)} 'real NTFS named stream rejected, not silently lost'
$f=Fixture 'junction';$null=New-Item -ItemType Junction -Path ($f.a+'\link') -Target $f.b
Reject {$f.engine.Inventory($f.restore)} 'real junction rejected, not followed'
$f=Fixture 'writer-lock';$s=[IO.File]::Open($f.a+'\alpha.txt','Open','Write','Read')
try{Reject {$f.engine.Backup($f.backup,$f.manifest)} 'active writer prevents cold read lock'}finally{$s.Dispose()}
$f=Fixture 'guard-abort';$badGuard=[Action]{throw 'synthetic guard stop'}
$e=[SflColdBackupV1.Engine]::new([string[]]@($f.a,$f.b),$badGuard,$progress)
Reject {$e.Backup($f.backup,$f.manifest)} 'guard failure aborts before backup writes'
Test (-not [IO.Directory]::Exists($f.backup)) 'no backup tree created after failing initial guard'

if($LargeFile){
    $f=Fixture 'over-2gib';$largePath=$f.a+'\large-zero.bin'
    $s=[IO.File]::Open($largePath,'CreateNew','Write','None')
    try{$s.SetLength(([long]2147483648)+17);$s.Flush($true)}finally{$s.Dispose()}
    $r=$f.engine.Backup($f.backup,$f.manifest)
    $null=$f.engine.Verify($f.manifest,$r.ManifestSha256,$f.backup,$f.restore,$true)
    $v=$f.engine.Verify($f.manifest,$r.ManifestSha256,$f.restore,$null,$false)
    Test ($v.Bytes -gt 2147483648) 'real file larger than two GiB streamed and both copies verified'
}

function Event {param([string]$Name,[object]$Payload)
    [pscustomobject]@{at=[DateTimeOffset]::Now;event=$Name;session='6728-synthetic';payload=$Payload}}
$good=[pscustomobject]@{pid=7620;reason='close';exit_code=0;signal_code=$null;forced=$false}
$since=[DateTimeOffset]::Now.AddMinutes(-1)
$proof=ShutdownProof @((Event 'backend.shutdown-complete' $good)) '6728-synthetic' $since
Test ($proof.exit_code -eq 0 -and -not $proof.forced) 'fresh exact-session zero-exit nonforced shutdown event'
Reject {ShutdownProof @() '6728-synthetic' $since} 'missing shutdown log rejected'
Reject {ShutdownProof @((Event 'backend.shutdown-complete' $good),(Event 'backend.shutdown-complete' $good)) '6728-synthetic' $since} 'duplicate shutdown proof rejected'
Reject {ShutdownProof @((Event 'backend.shutdown-complete' $good)) '6728-other' $since} 'wrong session rejected'
Reject {ShutdownProof @((Event 'backend.shutdown-complete' $good)) '6728-synthetic' ([DateTimeOffset]::Now.AddMinutes(1))} 'old shutdown event rejected'
$forced=[pscustomobject]@{pid=7620;reason='close';exit_code=0;signal_code=$null;forced=$true}
Reject {ShutdownProof @((Event 'backend.shutdown-complete' $forced)) '6728-synthetic' $since} 'forced shutdown rejected even exit zero'
Reject {ShutdownProof @((Event 'backend.shutdown-complete' $good),(Event 'backend.shutdown-failed' @{})) '6728-synthetic' $since} 'failure plus complete rejected'

$receipt=[ordered]@{result='COLD_BACKUP_SYNTHETIC_TEST_PASS';assertions=$checks.Count;checks=$checks.ToArray();
    powershell_version=$PSVersionTable.PSVersion.ToString();core_sha256=[SflColdBackupV1.Engine]::FileHash((Join-Path $PSScriptRoot 'cold-backup-core.cs'),1048576);
    wrapper_sha256=[SflColdBackupV1.Engine]::FileHash($helper,1048576);server_main_executed=$false;real_server_data_read=$false;
    engine_dll_sha256=$loadedHash;
    actual_server_shutdown_tested=$false;application_restore_tested=$false;multi_gib_file_tested=[bool]$LargeFile}
[IO.File]::WriteAllText(($output+'\validation-result.json'),($receipt|ConvertTo-Json -Depth 6),[Text.UTF8Encoding]::new($false))
[pscustomobject]$receipt|Select-Object result,assertions,powershell_version,core_sha256,server_main_executed|Format-List
