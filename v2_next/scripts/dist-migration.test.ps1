[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if(-not$IsWindows-or$PSVersionTable.PSVersion.Major-lt 7){throw 'Windows PowerShell 7 required'}
$count=0
function Check([bool]$OK,[string]$Name){if(-not$OK){throw $Name};$script:count++}
function Reject([scriptblock]$Block,[string]$Name){$caught=$false;try{&$Block}catch{$caught=$true};Check $caught $Name}
foreach($name in @('dist-migration-core.ps1','migrate-dist-protected.ps1')){
    $tokens=$null;$errors=$null;[void][Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot $name),[ref]$tokens,[ref]$errors)
    Check ($errors.Count-eq 0) ($name+' syntax: '+(@($errors|ForEach-Object {$_.Message})-join'; '))
}
. (Join-Path $PSScriptRoot 'dist-migration-core.ps1')
$native=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'server-path-audit\cleanup-archive-core.ps1') -Raw
$tokens=$null;$errors=$null;$ast=[Management.Automation.Language.Parser]::ParseInput($native,[ref]$tokens,[ref]$errors)
$fn=$ast.Find({param($n)$n-is[Management.Automation.Language.FunctionDefinitionAst]-and$n.Name-eq'Initialize-CleanupNative'},$false)
. ([scriptblock]::Create($fn.Extent.Text));Initialize-CleanupNative
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot ('..\.tmp\dist-migration-test-'+[Guid]::NewGuid().ToString('N'))))
if(-not$root.StartsWith([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\.tmp'))+'\',[StringComparison]::Ordinal)){throw 'Fixture outside intended directory'}
[void][IO.Directory]::CreateDirectory($root)
$guards=@{};$handles=[Collections.Generic.List[IDisposable]]::new()
function Fixture([string]$Name,[string]$Value='test-bytes'){$p=Join-Path $root $Name;$s=[IO.File]::Open($p,'CreateNew','Write','None');try{$s.Write([Text.Encoding]::UTF8.GetBytes($Value))}finally{$s.Dispose()};return $p}
function Record([string]$Path){$s=[IO.File]::OpenRead($Path);try{return [pscustomobject]@{path=$Path;bytes=$s.Length;sha256=Get-DistHash $s;metadata=[pscustomobject](Get-DistMetadata $Path);keeper=''}}finally{$s.Dispose()}}
try{
    $p=Fixture 'source.txt';$r=Record $p;$src=Open-DistSource $r $true $guards;$handles.Add($src.stream)
    Reject {[IO.File]::WriteAllText($p,'bad')} 'Held source rejects write'
    Reject {Set-Content -LiteralPath $p -Stream 'racing-stream' -Value 'bad' -ErrorAction Stop} 'Held source rejects new alternate stream'
    Reject {[IO.File]::Move($p,(Join-Path $root 'replacement.txt'))} 'Held source rejects path rename'
    Reject {[IO.Directory]::Move($root,$root+'-moved')} 'Guarded ancestor rejects rename'
    $kp=Fixture 'keeper.txt';$ks=[SflCleanupNativeV1]::OpenFile($kp,$false);$handles.Add($ks)
    $keeper=[pscustomobject]@{path=$kp;stream=$ks;bytes=$r.bytes;sha256=$r.sha256;identity=[SflCleanupNativeV1]::Identity($ks.SafeFileHandle,$kp,$false)}
    $r.keeper=$kp
    $j=[IO.File]::Open((Join-Path $root 'journal.jsonl'),'CreateNew','Write','Read');$handles.Add($j)
    $done=[Collections.Generic.List[object]]::new()
    $original=$src.identity;$src.identity='wrong'
    Reject {Remove-DistPinned $src $keeper $j $done} 'Wrong file identity blocks deletion';$src.identity=$original
    $r.keeper=$kp+'x';Reject {Remove-DistPinned $src $keeper $j $done} 'Wrong keeper path blocks deletion';$r.keeper=$kp
    $closed=[IO.MemoryStream]::new();$closed.Dispose()
    Reject {Remove-DistPinned $src $keeper $closed $done} 'Journal failure blocks deletion'
    Check ([IO.File]::Exists($p)-and$done.Count-eq 0) 'All precommit failures preserve source'
    Remove-DistPinned $src $keeper $j $done
    Check (-not[IO.File]::Exists($p)-and$done.Count-eq 1-and[IO.File]::Exists($kp)) 'Only verified source deleted'
    $j.Dispose();$events=@(Get-Content -LiteralPath (Join-Path $root 'journal.jsonl')|ForEach-Object {$_|ConvertFrom-Json})
    Check ($events.Count-eq 2-and$events[0].event-eq'DELETE_INTENT'-and$events[1].event-eq'DELETED') 'Intent is durable before delete'
    $bad=Fixture 'hash-mismatch.txt';$br=Record $bad;$br.sha256='0'*64
    Reject {Open-DistSource $br $true $guards} 'Wrong hash blocks opening for commit'
    Check ([IO.File]::Exists($bad)) 'Hash failure leaves bytes'
    $ads=Fixture 'ads.txt';$ar=Record $ads;Set-Content -LiteralPath $ads -Stream 'extra' -Value 'keep'
    Reject {Open-DistSource $ar $true $guards} 'Alternate stream blocks eligibility'
    $hard=Fixture 'hard-original.txt';$hr=Record $hard;New-Item -ItemType HardLink -Path (Join-Path $root 'hard-link.txt') -Target $hard|Out-Null
    Reject {Open-DistSource $hr $true $guards} 'Hard link blocks eligibility'
    $late=Fixture 'late-receipt-failure.txt';$lr=Record $late;$lr.keeper=$kp;$ls=Open-DistSource $lr $true $guards;$handles.Add($ls.stream)
    $saved=(Get-Command Write-DistEvent).ScriptBlock
    function Write-DistEvent($Journal,$Record){if($Record.event-eq'DELETED'){throw 'Synthetic post-delete failure'};&$saved $Journal $Record}
    $j2=[IO.File]::Open((Join-Path $root 'journal2.jsonl'),'CreateNew','Write','Read');$handles.Add($j2)
    Reject {Remove-DistPinned $ls $keeper $j2 $done} 'Post-delete receipt failure propagates'
    Check ($done.Count-eq 2-and-not[IO.File]::Exists($late)) 'Irreversible removal counted even if receipt fails'
    Set-Item -LiteralPath Function:Write-DistEvent -Value $saved
    $idxPath=Join-Path $root 'index.json'
    $a=[pscustomobject]@{id='fixture';kind='DESKTOP_DIST_PROTECTED_CI_MIGRATION';state='COMPLETE';plan=@{root=$root;archive_root=(Join-Path $root 'archive');files=@(@{path='remove-me'});groups=@(@{files=@(@{path='remove-me';destination='kept-copy';bytes=12;sha256=('A'*64)})})}}
    $sample=@{updated_at='before';audits=@(@{id='unrelated';state='UNCHANGED'},@{id='fixture';state='PREPARED'});history=@();files=@(@{path='remove-me'},@{path='preserve-me'});roots=@(@{path=$root;file_count=3836;bytes=6547977441});summary=@{files=41757;bytes=23384777258;roots=409;deleted_files=164594;deleted_bytes=9116943800;migrated_files=2352};validation=@{state='OLD_VALIDATION'};unchanged=@{large_number=9223372036854775806}}
    $bytes=[Text.Encoding]::UTF8.GetBytes(($sample|ConvertTo-Json -Depth 20 -Compress));$o=[IO.File]::Open($idxPath,'CreateNew','Write','None');try{$o.Write($bytes)}finally{$o.Dispose()}
    $ip=[IO.File]::OpenRead($idxPath);try{$indexHash=Get-DistHash $ip}finally{$ip.Dispose()}
    $jd=[System.Text.Json.JsonDocument]::Parse([IO.File]::ReadAllText($idxPath))
    try{Write-DistIndexCompletion $jd $a $idxPath $indexHash}finally{$jd.Dispose()}
    $after=[IO.File]::ReadAllText($idxPath)|ConvertFrom-Json -Depth 30
    Check ($after.audits[0].state-ceq'UNCHANGED'-and$after.audits[1].state-ceq'COMPLETE') 'Registry audit append preserves unrelated history'
    Check ($after.files.Count-eq 2-and$after.files[0].path-eq'preserve-me'-and$after.files[1].path-eq'kept-copy') 'Registry maps retired source to retained copy'
    Check ($after.summary.bytes-eq(23384777258-744244326)-and$after.summary.deleted_files-eq164603-and$after.summary.migrated_files-eq2364) 'Registry counts distinguish obsolete and migrated originals'
    Check ($after.unchanged.large_number-eq9223372036854775806) 'Streaming rewrite preserves large integer precision'
    Check ($after.validation.state-eq'DIST_TRANSACTION_VERIFIED_GLOBAL_RECHECK_PENDING') 'Does not claim global validation was rerun'
    $admin=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if($admin){
        $private=Join-Path $root 'private';New-DistDirectory $private $guards;Check $true 'Atomic private directory ACL'
        $cp=Fixture 'copy-source.txt';$cr=Record $cp;$cs=Open-DistSource $cr $false $guards;$handles.Add($cs.stream)
        $ck=Copy-DistPinned $cs (Join-Path $private 'copy.txt');$handles.Add($ck.stream)
        Check ($ck.sha256-eq$cr.sha256-and[IO.File]::Exists($cp)) 'Private owner and copy hashes verified before source removal'
    }
    Write-Host ('[PASS] '+$count+' dist migration checks; administrator_acl_copy_tests='+$admin+'; fixture='+$root)
    Write-Host '[NO MANAGED CHANGE] Only generated fixture files were removed; retained fixture evidence is not recursively deleted.'
}finally{foreach($h in $handles){$h.Dispose()};foreach($g in $guards.Values){$g.handle.Dispose()}}
