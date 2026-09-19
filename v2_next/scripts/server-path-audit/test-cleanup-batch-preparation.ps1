[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$PreparedHelper)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($PreparedHelper,[ref]$tokens,[ref]$errors)
if(@($errors).Count -gt 0){throw 'Prepared syntax error.'}
# Load functions only. Never run the server main block or query embedded server paths.
foreach($fn in $ast.FindAll({param($n)$n -is [Management.Automation.Language.FunctionDefinitionAst]},$true)){
    . ([scriptblock]::Create($fn.Extent.Text))
}
Add-Type -AssemblyName System.IO.Compression
$checks=0
function Check {param([bool]$Ok,[string]$Name);if(-not $Ok){throw ('FAIL '+$Name)};$script:checks++;Write-Host ('PASS '+$Name)}
function MustThrow {param([scriptblock]$Work,[string]$Name);$thrown=$false;try{& $Work}catch{$thrown=$true};Check $thrown $Name}
function ZipFixture {
    param([string[]]$Names)
    $m=[IO.MemoryStream]::new();$z=[IO.Compression.ZipArchive]::new($m,'Create',$true)
    try{foreach($name in $Names){$e=$z.CreateEntry($name);$s=$e.Open();try{$bytes=[Text.Encoding]::ASCII.GetBytes('abc');$s.Write($bytes,0,$bytes.Length)}finally{$s.Dispose()}}}
    finally{$z.Dispose()}
    $m.Position=0
    return [pscustomobject]@{memory=$m;zip=[IO.Compression.ZipArchive]::new($m,'Read',$true)}
}
function TestState {return @{clock=[Diagnostics.Stopwatch]::StartNew();last_progress=0;bytes_read=0L;rehashed_zip_bytes=0L;expanded_bytes=0L;files_done=0;total_files=1}}
$scope=Read-BatchScope
Check ($scope.groups.Count -eq 366 -and @($scope.entries|Where-Object type -CEQ 'file').Count -eq 959) 'embedded exact 366/959 scope'
Check ((($scope.entries|Where-Object type -CEQ 'file'|Measure-Object bytes -Sum).Sum) -eq 5380527285L) 'embedded exact byte sum'
Check ($scope.new_exclusions.Count -eq 70 -and $scope.protected_paths.Count -eq 205) 'protected 202 groups plus 3 operational roots'
$ids=@{};foreach($g in $scope.groups){$ids[[int]$g.id]=$true}
Check (-not $ids.ContainsKey(41) -and -not $ids.ContainsKey(472) -and -not $ids.ContainsKey(64)) 'updater, mixed evidence and R1 excluded'
$overlap=$false;foreach($g in $scope.groups){foreach($p in $scope.protected_paths){if((Test-BatchWithin $g.path $p) -or (Test-BatchWithin $p $g.path)){$overlap=$true}}}
Check (-not $overlap) 'no candidate/protected path overlap'
Check ((Test-BatchWithin 'C:\a\b' 'C:\a') -and -not (Test-BatchWithin 'C:\ab\b' 'C:\a')) 'path boundary separator'
$expected=@([pscustomobject]@{path='C:\fixture\a.txt';type='file';bytes=3;last_write_utc='2026-09-15T00:00:00Z'})
Check (Test-BatchMetadata $expected $expected) 'metadata equal'
Check (-not (Test-BatchMetadata $expected @())) 'missing source preserved'
$changed=@([pscustomobject]@{path='C:\fixture\a.txt';type='file';bytes=4;last_write_utc='2026-09-15T00:00:00Z'})
Check (-not (Test-BatchMetadata $expected $changed)) 'changed length preserved'
$changed[0].bytes=3;$changed[0].last_write_utc='2026-09-15T00:00:01Z'
Check (-not (Test-BatchMetadata $expected $changed)) 'changed timestamp preserved'
Check (-not (Test-BatchMetadata $expected @($expected[0],$expected[0]))) 'extra/duplicate metadata preserved'
$group=[pscustomobject]@{path='C:\fixture\unpacked'}
$sha='BA7816BF8F01CFEA414140DE5DAE2223B00361A396177A9CB410FF61F20015AD'
$files=@([pscustomobject]@{path='C:\fixture\unpacked\a.txt';length=3;sha256=$sha})
$m=[IO.MemoryStream]::new([Text.Encoding]::ASCII.GetBytes('abc'),$false)
try {
    $state=TestState
    Check ((Read-BatchArchiveHash $m 3 $state) -ceq $sha -and $state.rehashed_zip_bytes -eq 3) 'archive rehash bytes and digest'
    MustThrow {Read-BatchArchiveHash $m 4 (TestState)} 'archive rehash length mismatch'
    $state=TestState;$state.rehashed_zip_bytes=6GB
    MustThrow {Read-BatchArchiveHash $m 3 $state} 'archive rehash bounded bytes'
}finally{$m.Dispose()}
foreach($prefix in @('','unpacked/')){
    $f=ZipFixture @($prefix+'a.txt')
    try{
        $layout=Get-BatchZipLayout $f.zip;$match=Find-BatchZipMapping $group $files $layout
        Check ($null -ne $match -and $match.Count -eq 1 -and $match[0].sha256 -ceq $sha) ('exact ZIP relative mapping '+$prefix)
        Check ((Read-BatchZipEntryHash $f.zip.Entries[0] (TestState)) -ceq $sha) ('ZIP actual bytes hash '+$prefix)
        Check ((Read-BatchZipEntryHash $f.zip.Entries[0] (TestState)) -cne ('0'*64)) ('same length wrong digest not equal '+$prefix)
    }finally{$f.zip.Dispose();$f.memory.Dispose()}
}
foreach($name in @('../escape.txt','C:/absolute.txt','folder/../escape.txt','CON.txt','trailing./a.txt')){
    $f=ZipFixture @($name)
    try{MustThrow {Get-BatchZipLayout $f.zip} ('reject ZIP '+$name)}finally{$f.zip.Dispose();$f.memory.Dispose()}
}
$f=ZipFixture @('a.txt','A.txt')
try{MustThrow {Get-BatchZipLayout $f.zip} 'reject case-colliding ZIP paths'}finally{$f.zip.Dispose();$f.memory.Dispose()}
$f=ZipFixture @('a','a/b')
try{MustThrow {Get-BatchZipLayout $f.zip} 'reject ZIP file-directory conflict'}finally{$f.zip.Dispose();$f.memory.Dispose()}
$f=ZipFixture @('different.txt')
try{Check ($null -eq (Find-BatchZipMapping $group $files (Get-BatchZipLayout $f.zip))) 'different relative path not duplicate'}finally{$f.zip.Dispose();$f.memory.Dispose()}
$f=ZipFixture @('a.txt')
try{
    $layout=Get-BatchZipLayout $f.zip
    $more=@($files[0],[pscustomobject]@{path='C:\fixture\unpacked\b.txt';length=3;sha256=$sha})
    Check ($null -eq (Find-BatchZipMapping $group $more $layout)) 'partial folder match rejected'
    $wrong=@([pscustomobject]@{path='C:\fixture\unpacked\a.txt';length=4;sha256=$sha})
    Check ($null -eq (Find-BatchZipMapping $group $wrong $layout)) 'same name wrong length rejected'
}finally{$f.zip.Dispose();$f.memory.Dispose()}
# Real readonly I/O against an existing local fixture, never a path from the server inventory.
$fixture=Join-Path $PSScriptRoot 'fixtures\quarantine\one.txt'
if(-not [IO.File]::Exists($fixture)){
    $fixture=@(Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'fixtures\quarantine') -File -Recurse)[0].FullName
}
$info=[IO.FileInfo]::new($fixture)
$row=[pscustomobject]@{group=1;path=$fixture;bytes=$info.Length;last_write_utc=$info.LastWriteTimeUtc.ToString('o')}
$read=Read-BatchFile $row (TestState)
Check ($read.sha256 -ceq (Get-FileHash -LiteralPath $fixture -Algorithm SHA256).Hash) 'real fixture readonly hash'
$treeRoot=Join-Path $PSScriptRoot 'fixtures\quarantine'
$tree=Get-QTree $treeRoot -MaxDepth 30 -MaxEntries 5000 -Seconds 15
Check $tree.complete 'real bounded candidate tree coverage'
$rows=@($tree.rows|ForEach-Object {[pscustomobject]@{path=$_.path;type=$(if($_.directory){'directory'}else{'file'});bytes=$_.length;last_write_utc=[DateTime]::new($_.write_ticks,[DateTimeKind]::Utc).ToString('o')}})
$expectedRows=@(Get-ChildItem -LiteralPath $treeRoot -Force -Recurse|ForEach-Object {[pscustomobject]@{path=$_.FullName;type=$(if($_.PSIsContainer){'directory'}else{'file'});bytes=$(if($_.PSIsContainer){$null}else{$_.Length});last_write_utc=$_.LastWriteTimeUtc.ToString('o')}})
Check (Test-BatchMetadata $expectedRows $rows) 'real tree metadata conversion matches expected'
$row.bytes++
MustThrow {Read-BatchFile $row (TestState)} 'real changed-size file rejected'
$commands=@($ast.FindAll({param($n)$n -is [Management.Automation.Language.CommandAst]},$true)|ForEach-Object {$_.GetCommandName()})
$bad=@($commands|Where-Object {$_ -in @('Remove-Item','Move-Item','Set-Acl','Stop-Process','Start-Process','Invoke-Expression','Invoke-RestMethod','Invoke-WebRequest')})
Check ($bad.Count -eq 0) 'no deletion/move/ACL/process-control/API commands'
$text=[IO.File]::ReadAllText($PreparedHelper)
Check ($text -notmatch '(?i)::(?:Delete|Move|SetAccessControl)\s*\(') 'no filesystem deletion/move/ACL static calls'
Check ($text -notmatch '(?i)deletion_authorized\s*=\s*\$true') 'no deletion authorization success branch'
Write-Output ('BATCH_PREPARATION_OFFLINE_TEST_PASS checks='+$checks+' server_main_run=False source_writes=False')
