[CmdletBinding()]
param([string]$EvidenceDirectory = '')
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if ($PSVersionTable.PSEdition -cne 'Desktop' -or $PSVersionTable.PSVersion.Major -ne 5 -or
    $PSVersionTable.PSVersion.Minor -ne 1 -or -not [Environment]::Is64BitProcess) {
    throw 'Run these compatibility tests in native x64 Windows PowerShell 5.1.'
}
$checks=[Collections.Generic.List[string]]::new()
function Check { param([bool]$OK,[string]$Name) if(-not $OK){throw $Name};$checks.Add($Name) }
function Reject { param([scriptblock]$Code,[string]$Name) $caught=$false;try{& $Code}catch{$caught=$true};Check $caught $Name }
$path=Join-Path $PSScriptRoot 'read-quarantine-pre-v1020.ps1'
$errors=$null;$tokens=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($path,[ref]$tokens,[ref]$errors)
Check (@($errors).Count -eq 0) 'PS5.1 syntax'
foreach($fn in $ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst]},$true)) {
    . ([scriptblock]::Create($fn.Extent.Text))
}
$allowed=@('Assert-QPlain','Assert-QRelative','Get-QHash','Open-QPinned','Read-QText','Get-QContract',
 'Get-QTree','Compare-QTree','Find-QReferences','Get-QSystemReferences','Get-QFileReferences',
 'Set-StrictMode','Write-Host','Get-CimInstance','Get-ScheduledTask','New-Object','Where-Object',
 'Sort-Object','Join-Path','ConvertFrom-Json','ConvertTo-Json','Compare-Object','ForEach-Object')
$cmds=@($ast.FindAll({param($n) $n -is [Management.Automation.Language.CommandAst]},$true) | ForEach-Object {$_.GetCommandName()} | Where-Object {$null -ne $_})
Check (@($cmds | Where-Object {$_ -notin $allowed}).Count -eq 0) 'Read/report command allowlist'
$members=@($ast.FindAll({param($n) $n -is [Management.Automation.Language.InvokeMemberExpressionAst]},$true) | ForEach-Object {$_.Member.Extent.Text})
Check (@($members | Where-Object {$_ -match '^(Delete|Move|Copy|CreateDirectory|Write|WriteAll.*|Save|Run|Exec|Kill|GetResponse|Resolve)$'}).Count -eq 0) 'No write/delete/launch/network members'
$source=[IO.File]::ReadAllText($path)
Check ($source.Contains('deletion_approved=$false')) 'No deletion approval result'
Check ($source -notmatch '(?i)Invoke-Expression|Start-Process|Stop-Process|Remove-Item|Move-Item|Copy-Item') 'No mutation commands'
foreach($bad in @('..\x','a\..\b','a\\b','C:\x','x:stream','a/x','a\NUL.txt','a\x.','a\x ','a\*.txt')) {
    Reject { Assert-QRelative $bad } ('Reject relative '+$bad)
}
Assert-QRelative 'nested\entry.txt';Check $true 'Regular relative accepted'
Reject {Assert-QPlain '\\server\share\file'} 'UNC absolute rejected'
Reject {Assert-QPlain 'C:\Windows\..\Windows'} 'Noncanonical absolute rejected'
Reject {Assert-QPlain ('C:\'+('x'*257))} 'Over 259 characters rejected'
$fixture=Join-Path $PSScriptRoot 'fixtures\quarantine'
Assert-QPlain $fixture;Check $true 'Fixture ancestry plain'
function New-Manifest {
    $rows=@(foreach($relative in @('entry.txt','nested\entry.txt')) {
        $f=Join-Path $fixture $relative
        [pscustomobject]@{relative_path=$relative;length=[long]([IO.FileInfo]::new($f).Length);sha256=(Get-FileHash -LiteralPath $f).Hash}
    })
    return [pscustomobject]@{top_level_items=@('entry.txt','nested');files=$rows;file_count=2;total_bytes=[long](($rows|Measure-Object length -Sum).Sum);critical_keep=@('keep')}
}
$manifest=New-Manifest;$contract=Get-QContract $manifest
Check ($contract.files.Count -eq 2 -and $contract.dirs.Contains('nested')) 'Contract builds file/directory map'
$badManifest=New-Manifest;$badManifest.top_level_items+=@('ENTRY.txt');Reject {Get-QContract $badManifest} 'Case-insensitive duplicate top rejected'
$badManifest=New-Manifest;$badManifest.files+=@($badManifest.files[0]);Reject {Get-QContract $badManifest} 'Duplicate file rejected'
$badManifest=New-Manifest;$badManifest.files[0].relative_path='..\outside';Reject {Get-QContract $badManifest} 'Manifest path escape rejected'
$badManifest=New-Manifest;$badManifest.files[0].length=-1;Reject {Get-QContract $badManifest} 'Negative size rejected'
$badManifest=New-Manifest;$badManifest.files[0].length=1.5;Reject {Get-QContract $badManifest} 'Fractional size rejected'
$badManifest=New-Manifest;$badManifest.files[0].sha256='BAD';Reject {Get-QContract $badManifest} 'Malformed hash rejected'
$badManifest=New-Manifest;$badManifest.total_bytes++;Reject {Get-QContract $badManifest} 'Wrong total rejected'
$badManifest=New-Manifest;$badManifest.critical_keep=@('nested');Reject {Get-QContract $badManifest} 'Protected top overlap rejected'
$badManifest=New-Manifest;$badManifest.top_level_items+=@('ghost');Reject {Get-QContract $badManifest} 'Unrepresented top rejected'
$badManifest=New-Manifest;$badManifest.files[0].relative_path='nested';Reject {Get-QContract $badManifest} 'File ancestor conflict rejected'
$pins=[Collections.Generic.List[IDisposable]]::new()
try {
    $row=$manifest.files[0];$file=Join-Path $fixture $row.relative_path
    $stream=Open-QPinned $file $row.length $row.sha256 $pins
    Check ($pins.Count -eq 1 -and (Read-QText $stream) -match 'synthetic') 'Pinned read and UTF8 text'
    Reject {Open-QPinned $file ($row.length+1) $row.sha256 $pins} 'Wrong length rejected'
    Reject {Open-QPinned $file $row.length ('A'*64) $pins} 'Wrong hash rejected'
    Check ($pins.Count -eq 1) 'Failed pins not retained'
    $tree=Get-QTree $fixture
    Check ($tree.complete -and @($tree.rows).Count -eq 3) 'Fixture recursive enumeration'
    $compare=Compare-QTree $tree $contract @()
    Check ($compare.missing.Count -eq 0 -and $compare.unlisted.Count -eq 0) 'Exact inventory match'
    $limited=Get-QTree $fixture -MaxEntries 1
    Check (-not $limited.complete -and @($limited.issues).Count -gt 0) 'Entry limit reports partial'
    $shallow=Get-QTree $fixture -MaxDepth 0
    Check (-not $shallow.complete -and @($shallow.issues | Where-Object kind -eq 'DEPTH_NOT_INSPECTED').Count -eq 1) 'Depth limit reported'
    $absent=Get-QTree (Join-Path $fixture 'nonexistent')
    Check (-not $absent.complete -and $absent.issues.Count -eq 1) 'Missing root is not empty success'
    $extra=[pscustomobject]@{rows=@($tree.rows)+@([pscustomobject]@{relative='unexpected';directory=$false})}
    Check ((Compare-QTree $extra $contract @()).unlisted[0].kind -ceq 'EXTRA_FILE') 'Unexpected file reported'
    $empty=[pscustomobject]@{rows=@($tree.rows)+@([pscustomobject]@{relative='empty';directory=$true})}
    Check ((Compare-QTree $empty $contract @()).unlisted[0].kind -ceq 'DIRECTORY_NOT_DESCRIBED_BY_MANIFEST') 'Unknown empty directory not called new'
    $missing=[pscustomobject]@{rows=@($tree.rows | Where-Object relative -ne 'entry.txt')}
    Check ((Compare-QTree $missing $contract @()).missing.Count -eq 1) 'Missing manifest file reported'
} finally {foreach($pin in $pins){$pin.Dispose()}}
Check (@(Find-QReferences 'C:/old/NESTED/file SECRET_TOKEN' @('nested')).Count -eq 1) 'Literal case insensitive reference'
Check ((@(Find-QReferences 'secret-password before named.ps1 after' @('named.ps1')) -join '') -ceq 'named.ps1') 'No text/secret excerpts returned'
Check (@(Find-QReferences $null @('needle')).Count -eq 0) 'Null reference text safe'
Check (@(Find-QReferences 'file[1].ps1' @('file[1].ps1')).Count -eq 1) 'Regex characters treated literally'
Check (@(Find-QReferences 'unrelated' @('needle')).Count -eq 0) 'No match empty array'

# Mock external providers; never query server or local machine task/process state.
function Get-CimInstance {
    param($ClassName,$OperationTimeoutSec,$ErrorAction)
    if($ClassName -eq 'Win32_Process'){return [pscustomobject]@{ProcessId=123;ExecutablePath='C:\nested\app.exe';CommandLine='SECRET --run nested'}}
    if($ClassName -eq 'Win32_Service'){throw 'synthetic access denied'}
    return [pscustomobject]@{Name='fixture-startup';Command='C:\nested\app.exe';Location='registry'}
}
function Get-ScheduledTask {
    param($ErrorAction)
    return [pscustomobject]@{TaskPath='\Fixture\';TaskName='test';Actions=@([pscustomobject]@{Execute='C:\nested\app.exe';Arguments='SECRET';WorkingDirectory='C:\'},[pscustomobject]@{ClassId='fixture'})}
}
$refs=Get-QSystemReferences @('nested')
Check (@($refs.hits).Count -eq 4) 'Mock process/startup/task references'
Check (@($refs.coverage | Where-Object status -eq 'QUERY_ERROR_PARTIAL').Count -eq 1) 'Provider failure visible'
Check (($refs.coverage | Where-Object scope -eq 'scheduled_tasks').non_exec_or_missing_action_fields -eq 1) 'Non-exec task action unresolved'
Check (($refs | ConvertTo-Json -Depth 8) -notmatch 'SECRET') 'Provider output redacts command contents'
$fileRefs=Get-QFileReferences @('synthetic') @([pscustomobject]@{path=$fixture;depth=1;kind='text'})
Check ($fileRefs.hits.Count -eq 2 -and $fileRefs.coverage[0].checked_files -eq 2) 'Text reference scan only fixtures'
Check (($fileRefs | ConvertTo-Json -Depth 8) -notmatch 'synthetic nested file') 'No file content excerpts'
if ($EvidenceDirectory -ne '') {
    # User-transferred metadata only; do not resolve any server path declared inside it.
    $specs=@(
        @('quarantine_manifest_before_move.json',198366L,'F918CAF4ABCC65124E86F50D2DD79DFCC962ECC221FD8E0997DB2402FE468752'),
        @('quarantine_verification_after_move.json',656L,'4CB03191D3E8816A713EA4A65D6EC03FDAC6FB94606E06B62B7F4EB1D9893D14'),
        @('quarantine_verification_after_move_R1_1.json',1628L,'4D6A6984ED3B1E2AEEEA58C9C8403FC0E3543F649EBE296E5BB2DCB671C20671'))
    $documents=@{};$metadataPins=[Collections.Generic.List[IDisposable]]::new()
    try {
        foreach($spec in $specs) {
            $stream=Open-QPinned (Join-Path $EvidenceDirectory $spec[0]) $spec[1] $spec[2] $metadataPins
            $documents[$spec[0]]=ConvertFrom-Json -InputObject (Read-QText $stream)
            Check $true ('Uploaded metadata bytes '+$spec[0])
        }
        $realContract=Get-QContract $documents[$specs[0][0]]
        Check ($realContract.files.Count -eq 558 -and $realContract.tops.Count -eq 136 -and $realContract.bytes -eq 1077165719L) 'Actual manifest contract under PS5.1'
        Check ($documents[$specs[2][0]].source_manifest_sha256 -ceq $specs[0][2] -and $documents[$specs[2][0]].superseded_verification_sha256 -ceq $specs[1][2]) 'Actual corrected receipt binding under PS5.1'
    } finally {foreach($pin in $metadataPins){$pin.Dispose()}}
}
[pscustomobject]@{result='QUARANTINE_READ_ONLY_TEST_PASS';assertions=$checks.Count;checks=$checks.ToArray();powershell=$PSVersionTable.PSVersion.ToString();server_main_executed=$false;real_system_providers_queried=$false;limitations=@('No live COM shortcut test','No hostile ancestor race or access-denied filesystem fixture','No server files or 1.08 GB server hash pass executed')} | ConvertTo-Json -Depth 6
