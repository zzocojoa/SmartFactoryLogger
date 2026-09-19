[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if ($PSVersionTable.PSEdition -cne 'Desktop' -or $PSVersionTable.PSVersion.Major -ne 5 -or
    $PSVersionTable.PSVersion.Minor -ne 1 -or -not [Environment]::Is64BitProcess) { throw 'Native Windows PowerShell 5.1 x64 required.' }
$checks=[Collections.Generic.List[string]]::new()
function Check { param([bool]$Ok,[string]$Name) if(-not $Ok){throw $Name};$checks.Add($Name) }
function Reject { param([scriptblock]$Code,[string]$Name) $caught=$false;try{& $Code}catch{$caught=$true};Check $caught $Name }
foreach ($name in @('read-quarantine-pre-v1020.ps1','cleanup-archive-core.ps1','cleanup-pre-v1020.ps1')) {
    $tokens=$null; $errors=$null
    $ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot $name),[ref]$tokens,[ref]$errors)
    Check (@($errors).Count -eq 0) ($name+' syntax')
    if ($name -eq 'cleanup-pre-v1020.ps1') { continue }
    foreach($fn in $ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst]},$true)) {
        . ([scriptblock]::Create($fn.Extent.Text))
    }
}
Initialize-CleanupNative
Add-Type -AssemblyName System.IO.Compression
$workspace=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$tempParent=Join-Path $workspace '.tmp'
if (-not [IO.Directory]::Exists($tempParent)) { $null=[IO.Directory]::CreateDirectory($tempParent) }
Assert-QPlain $tempParent
$fixture=Join-Path $tempParent ('cleanup-synthetic-'+[Guid]::NewGuid().ToString('N'))
$null=[IO.Directory]::CreateDirectory($fixture)
if (-not $fixture.StartsWith($workspace+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Test escaped workspace.' }
# Test fixtures are generated here only. No server inputs, live APIs or product paths are opened.
function FixtureFile {
    param([string]$Name,[string]$Text='synthetic-bytes')
    Assert-QRelative $Name
    $path=Join-Path $fixture $Name; $parent=[IO.Path]::GetDirectoryName($path)
    if (-not [IO.Directory]::Exists($parent)) { $null=[IO.Directory]::CreateDirectory($parent) }
    $s=[IO.File]::Open($path,'CreateNew','Write','None')
    try {$b=[Text.UTF8Encoding]::new($false).GetBytes($Text);$s.Write($b,0,$b.Length)}finally{$s.Dispose()}
    return $path
}
function MakeZip {
    param([object[]]$Entries)
    $mem=[IO.MemoryStream]::new();$z=[IO.Compression.ZipArchive]::new($mem,'Create',$true)
    try { foreach($item in $Entries){
        $e=$z.CreateEntry($item.name)
        if ($null -ne $item.PSObject.Properties['attrs']) { $e.ExternalAttributes=$item.attrs }
        $s=$e.Open();try{$b=[Text.UTF8Encoding]::new($false).GetBytes($item.text);$s.Write($b,0,$b.Length)}finally{$s.Dispose()}
    }} finally {$z.Dispose()}
    $mem.Position=0; return ,$mem
}
function Row {
    param([string]$Relative,[string]$Text='synthetic-bytes')
    $b=[Text.UTF8Encoding]::new($false).GetBytes($Text);$sha=[Security.Cryptography.SHA256]::Create()
    try {return [pscustomobject]@{relative_path=$Relative;length=[long]$b.Length;sha256=[BitConverter]::ToString($sha.ComputeHash($b)).Replace('-','')}}finally{$sha.Dispose()}
}
$all=[Collections.Generic.List[IDisposable]]::new(); $guards=@{}
try {
    $mem=MakeZip @([pscustomobject]@{name='a.txt';text='synthetic-bytes'},[pscustomobject]@{name='nested/b.txt';text='two'})
    $all.Add($mem);$total=0L;$idx=Get-CleanupZipIndex $mem ([ref]$total)
    $rows=@((Row 'folder\a.txt'),(Row 'folder\nested\b.txt' 'two'))
    Check ($idx.Count -eq 2 -and $total -eq 18) 'ZIP content rehashed'
    $map=Find-CleanupArchiveMapping 'folder' $rows $idx
    Check (@($map).Count -eq 2 -and $map[1].zip_entry -ceq 'nested/b.txt') 'Flat ZIP full folder mapping'
    $mem2=MakeZip @([pscustomobject]@{name='folder/a.txt';text='synthetic-bytes'},[pscustomobject]@{name='folder/nested/b.txt';text='two'})
    $all.Add($mem2);$idx2=Get-CleanupZipIndex $mem2 ([ref]$total)
    Check (@(Find-CleanupArchiveMapping 'folder' $rows $idx2).Count -eq 1) 'Wrapped array returned as one mapping object'
    Check ((Find-CleanupArchiveMapping 'folder' $rows $idx2).Count -eq 2) 'Exact named ZIP folder mapping'
    $missing=@($rows)+@((Row 'folder\absent.txt'))
    Check ($null -eq (Find-CleanupArchiveMapping 'folder' $missing $idx)) 'Partial duplicate folder rejected'
    $different=@((Row 'folder\a.txt' 'different'),$rows[1])
    Check ($null -eq (Find-CleanupArchiveMapping 'folder' $different $idx)) 'Different byte hash rejected'
    Check ($null -eq (Find-CleanupArchiveMapping 'folder' @((Row 'folder\A.txt'),$rows[1]) $idx)) 'Case mismatch rejected'
    $arbitrary=@{};foreach($key in $idx.Keys){$arbitrary['other\'+$key]=[pscustomobject]@{entry='other\'+$key;length=$idx[$key].length;sha256=$idx[$key].sha256}}
    Check ($null -eq (Find-CleanupArchiveMapping 'folder' $rows $arbitrary)) 'Arbitrary suffix prefix matching rejected'
    foreach($names in @(@('../x'),@('C:/x'),@('a:stream'),@('NUL.txt'),@('a. '),@('a','A'),@('a','a/b'))){
        $entries=@(foreach($name in $names){[pscustomobject]@{name=$name;text='x'}})
        $m=MakeZip $entries;$all.Add($m)
        Reject {Get-CleanupZipIndex $m ([ref]$total)} ('Unsafe ZIP '+($names -join ','))
    }
    $m=MakeZip @([pscustomobject]@{name='symlink';text='x';attrs=[int](-1610612736)})
    $all.Add($m);Reject {Get-CleanupZipIndex $m ([ref]$total)} 'ZIP symbolic link rejected'
    foreach($spec in @(@('fifo',0x10000000),@('socket',-1073741824),@('directory-without-slash',0x40000000),@('file/',-2147483648),@('dos-directory',16),@('double//',0))){
        $m=MakeZip @([pscustomobject]@{name=$spec[0];text='';attrs=[int]$spec[1]});$all.Add($m)
        Reject {Get-CleanupZipIndex $m ([ref]$total)} ('Unsafe ZIP type/layout '+$spec[0])
    }
    $near=3GB;Reject {Get-CleanupZipIndex $mem ([ref]$near)} 'Total ZIP expansion budget'
    $candidates=@{a=1;b=1;c=1};$protected=@{}
    $texts=@{'retained.json'='a';'a\child.json'='b';'b\next.json'='c';'c\self.json'=''}
    Protect-CleanupReferences $candidates $texts $protected
    Check ($protected.Count -eq 3) 'Transitive retained references reach fixed point'
    $protected=@{};Protect-CleanupReferences @{a=1;b=1} @{'a\x.json'='b';'b\x.json'='a'} $protected
    Check ($protected.Count -eq 0) 'Internal retired-folder reference cycle alone is not a retained dependency'
    $coverage=[pscustomobject]@{kind='text';read_errors=0;size_or_budget_skipped=0;omitted_hits=0;enumeration_issues=@()}
    Assert-CleanupReferenceCoverage @($coverage);Check $true 'Complete reference read accepted'
    $coverage.enumeration_issues=@([pscustomobject]@{kind='DEPTH_NOT_INSPECTED';path='C:\outside-scope'})
    Assert-CleanupReferenceCoverage @($coverage);Check $true 'Declared bounded reference depth recorded'
    $coverage.enumeration_issues=@([pscustomobject]@{kind='REPARSE_SKIPPED';path='C:\unknown-junction'})
    Reject {Assert-CleanupReferenceCoverage @($coverage)} 'Unknown scoped reparse blocks deletion'
    $coverage.kind='shortcut';$coverage.enumeration_issues[0].path='C:\ProgramData\Microsoft\Windows\Start Menu\'+(-join ([char[]]@(0xD504,0xB85C,0xADF8,0xB7A8)))
    Assert-CleanupReferenceCoverage @($coverage);Check $true 'Only exact previously observed Start Menu junction exempted'
    $target=FixtureFile 'owned\delete.txt'
    $keep=FixtureFile 'kept\keep.txt'
    Open-CleanupDirectoryGuard ([IO.Path]::GetDirectoryName($target)) $guards
    $h=[SflCleanupNativeV1]::OpenFile($target,$false);$all.Add($h)
    $id=[SflCleanupNativeV1]::Identity($h.SafeFileHandle,$target,$false)
    [SflCleanupNativeV1]::NoAlternateStreams($target,$false);Check $true 'Plain default data stream accepted'
    Reject {[IO.Directory]::Move((Join-Path $fixture 'owned'),(Join-Path $fixture 'moved'))} 'Ancestor guard blocks rename'
    Reject {[IO.File]::WriteAllText($target,'replaced')} 'Source pin blocks writes'
    Reject {[SflCleanupNativeV1]::OpenFile($target,$true)} 'Read pin prevents concurrent delete access'
    $h.Dispose()
    $journalPath=Join-Path $fixture 'journal.jsonl';$journal=[IO.File]::Open($journalPath,'CreateNew','Write','Read');$all.Add($journal)
    Reject {Remove-CleanupVerifiedFile $fixture (Row 'owned\delete.txt') 'wrong-id' $journal} 'Changed file identity stops deletion'
    Check ([IO.File]::Exists($target)) 'Identity mismatch keeps target'
    Reject {Remove-CleanupVerifiedFile $fixture (Row 'owned\delete.txt' 'wrong-bytes') $id $journal} 'Changed file bytes stop deletion'
    Check ([IO.File]::Exists($target)) 'Byte mismatch keeps target'
    Reject {Assert-CleanupChild $fixture $fixture} 'Root itself cannot be a delete target'
    Reject {Assert-CleanupChild $fixture $PSScriptRoot} 'Outside delete path rejected'
    $adsPath=FixtureFile 'owned\has-ads.txt'
    Set-Content -LiteralPath $adsPath -Stream 'private-data' -Value 'not-in-zip'
    Reject {[SflCleanupNativeV1]::NoAlternateStreams($adsPath,$false)} 'ADS blocks eligibility'
    $adsStream=[SflCleanupNativeV1]::OpenFile($adsPath,$false);$adsId=[SflCleanupNativeV1]::Identity($adsStream.SafeFileHandle,$adsPath,$false);$adsStream.Dispose()
    Reject {Remove-CleanupVerifiedFile $fixture (Row 'owned\has-ads.txt') $adsId $journal} 'ADS target not deleted'
    Check ([IO.File]::Exists($adsPath)) 'ADS contents preserved with target'
    $empty=Join-Path $fixture 'empty';$null=[IO.Directory]::CreateDirectory($empty)
    $d=[SflCleanupNativeV1]::GuardDirectory($empty);$emptyId=[SflCleanupNativeV1]::Identity($d,$empty,$true);$d.Dispose()
    [SflCleanupNativeV1]::DeleteEmptyDirectory($empty,$emptyId)
    Check (-not [IO.Directory]::Exists($empty)) 'Only an empty identified directory removed'
    $owned=Join-Path $fixture 'owned';$dg=$guards[$owned];$dg.handle.Dispose()
    Reject {[SflCleanupNativeV1]::DeleteEmptyDirectory($owned,$dg.identity)} 'Nonempty directory cannot be deleted'
    Remove-CleanupVerifiedFile $fixture (Row 'owned\delete.txt') $id $journal
    Check (-not [IO.File]::Exists($target) -and [IO.File]::Exists($keep)) 'Exact verified file deleted; kept file intact'
    $journal.Dispose()
    $events=@(Get-Content -LiteralPath $journalPath | ForEach-Object {ConvertFrom-Json -InputObject $_})
    Check ($events.Count -eq 2 -and $events[0].event -ceq 'DELETE_INTENT' -and $events[1].event -ceq 'DELETED') 'Durable intent precedes deletion receipt'
    Check ((Get-FileHash -LiteralPath $keep).Hash -ceq (Row 'kept\keep.txt').sha256) 'Retained bytes unchanged'
    # Stop-on-write-failure proof: no deletion if an intent cannot be flushed.
    $blocked=FixtureFile 'blocked.txt';$s=[SflCleanupNativeV1]::OpenFile($blocked,$false)
    $blockedId=[SflCleanupNativeV1]::Identity($s.SafeFileHandle,$blocked,$false);$s.Dispose()
    Reject {Remove-CleanupVerifiedFile $fixture (Row 'blocked.txt') $blockedId $journal} 'Closed journal prevents deletion'
    Check ([IO.File]::Exists($blocked)) 'Journal failure preserves target'
    $postFailure=FixtureFile 'post-journal-failure.txt'
    $s=[SflCleanupNativeV1]::OpenFile($postFailure,$false);$postId=[SflCleanupNativeV1]::Identity($s.SafeFileHandle,$postFailure,$false);$s.Dispose()
    $j2=[IO.File]::Open((Join-Path $fixture 'journal2.jsonl'),'CreateNew','Write','Read');$all.Add($j2)
    $originalWriter=(Get-Command Write-CleanupRecord).ScriptBlock
    function Write-CleanupRecord {param([IO.FileStream]$Journal,[object]$Record)
        if($Record.event -ceq 'DELETED'){throw 'synthetic post-deletion journal failure'}
        & $originalWriter $Journal $Record
    }
    $confirmed=[Collections.Generic.List[object]]::new()
    Reject {Remove-CleanupVerifiedFile $fixture (Row 'post-journal-failure.txt') $postId $j2 $null $confirmed} 'Post-deletion journal failure surfaced'
    Check ($confirmed.Count -eq 1 -and -not [IO.File]::Exists($postFailure)) 'Confirmed deletion counted even if receipt write fails'
    $entry=[IO.File]::ReadAllText((Join-Path $PSScriptRoot 'cleanup-pre-v1020.ps1'))
    Check ($entry -notmatch 'Remove-Item|Stop-Process|Start-Process|Invoke-RestMethod|Invoke-WebRequest') 'No recursive deletion, process control or live API calls'
    Check ($entry.Contains('[switch]$Execute') -and $entry.Contains("if (-not `$Execute)")) 'Default is plan-only'
    [pscustomobject]@{result='CLEANUP_SYNTHETIC_TEST_PASS';assertions=$checks.Count;fixture=$fixture;checks=$checks.ToArray();server_paths_opened=$false} | ConvertTo-Json -Depth 4
} finally {
    foreach($s in $all){$s.Dispose()};foreach($g in $guards.Values){$g.handle.Dispose()}
    # Keep small synthetic residual fixtures for inspection; no recursive test cleanup.
}
