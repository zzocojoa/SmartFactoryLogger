[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$EvidenceDirectory)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($PSVersionTable.PSEdition -cne 'Desktop' -or $PSVersionTable.PSVersion.ToString() -notlike '5.1.*' -or -not [Environment]::Is64BitProcess){throw 'Use native Windows PowerShell 5.1 x64.'}
$checks=[Collections.Generic.List[string]]::new()
function Check {param([bool]$Ok,[string]$Name) if(-not $Ok){throw $Name};$checks.Add($Name)}
function Reject {param([scriptblock]$Code,[string]$Name) $caught=$false;try{& $Code}catch{$caught=$true};Check $caught $Name}
function CopyObject {param([object]$Value) return ConvertFrom-Json -InputObject ($Value|ConvertTo-Json -Depth 30)}
foreach($name in @('read-quarantine-pre-v1020.ps1','cleanup-archive-core.ps1','cleanup-v1019-release-pair.ps1')){
    $tokens=$null;$errors=$null;$ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot $name),[ref]$tokens,[ref]$errors)
    Check (@($errors).Count -eq 0) ($name+' native parse')
    foreach($fn in $ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst]},$true)){. ([scriptblock]::Create($fn.Extent.Text))}
}
Initialize-CleanupNative
$manifestPath=Join-Path $EvidenceDirectory 'quarantine_manifest_before_move.json'
$receiptPath=Join-Path $EvidenceDirectory 'cleanup.jsonl'
Check ((Get-FileHash -LiteralPath $manifestPath).Hash -ceq 'F918CAF4ABCC65124E86F50D2DD79DFCC962ECC221FD8E0997DB2402FE468752') 'External manifest hash'
Check ((Get-FileHash -LiteralPath $receiptPath).Hash -ceq '79A9C3534C2CB4DB56C865391516152582FB4A8006EE97F265889D766561EBD5') 'External completed receipt hash'
$manifest=Get-Content -LiteralPath $manifestPath -Raw|ConvertFrom-Json
$events=@(Get-Content -LiteralPath $receiptPath|ForEach-Object {ConvertFrom-Json -InputObject $_})
$left='release_private_unsigned_v1_0_19_0c1ad4f_20260810_R1'
$right='release_private_unsigned_v1_0_19_0c1ad4f_20260810_R2_clean'
$plan=Get-ReleasePairPlan $manifest $left $right
Assert-ReviewedReleasePair $plan;Check $true 'Exact reviewed direction and two unique JSON pins'
Check ($plan.files.Count -eq 22 -and $plan.bytes -eq 157989430L) '22 identical files and exact bytes'
Check ($plan.left_files -eq 23 -and $plan.right_files -eq 23) '23 files per side'
Reject {Get-ReleasePairPlan $manifest $left $left.ToUpperInvariant()} 'Same root case alias rejected'
Reject {Get-ReleasePairPlan $manifest '..\escape' $right} 'Traversal rejected'
$bad=CopyObject $manifest
($bad.files|Where-Object relative_path -CEQ $plan.files[0].retained_relative_path).sha256=('0'*64)
Reject {Get-ReleasePairPlan $bad $left $right} 'Same suffix different hash rejected'
$bad=CopyObject $manifest
($bad.files|Where-Object relative_path -CEQ $plan.files[0].retained_relative_path).length+=1
Reject {Get-ReleasePairPlan $bad $left $right} 'Different length rejected'
$bad=CopyObject $plan;$bad.left_unique[0].sha256=('0'*64)
Reject {Assert-ReviewedReleasePair $bad} 'Changed unique JSON rejected'
Reject {Assert-ReviewedReleasePair (Get-ReleasePairPlan $manifest $right $left)} 'Reversed direction rejected'
$contract=Get-PostCleanupContract $manifest $events
Check ($contract.files.Count -eq 470) 'Reviewed journal reconstructs 470 remaining files'
foreach($row in $plan.files){Check ($contract.files.ContainsKey($row.relative_path) -and $contract.files.ContainsKey($row.retained_relative_path)) ('Prior deletion does not intersect '+$row.relative_path)}
Reject {Get-PostCleanupContract $manifest @($events[0..216])} 'Truncated receipt rejected'
foreach($mode in @('hold','unpaired','duplicate','wrong-hash','wrong-count','wrong-root')){
    $bad=CopyObject $events
    switch($mode){
        hold {$bad[-1].event='HOLD'}
        unpaired {$bad[1].event='DELETED'}
        duplicate {$bad[3]=$bad[1]}
        wrong-hash {$bad[1].file.sha256=('0'*64)}
        wrong-count {$bad[-1].deleted_files=87}
        wrong-root {$bad[0].root='C:\wrong'}
    }
    Reject {Get-PostCleanupContract $manifest $bad} ('Receipt rejects '+$mode)
}
$invContract=[pscustomobject]@{files=@{'d\a.bin'=[pscustomobject]@{length=3}};dirs=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)}
$null=$invContract.dirs.Add('d')
$tree=[pscustomobject]@{complete=$true;rows=@([pscustomobject]@{relative='d';directory=$true;length=0},[pscustomobject]@{relative='d\a.bin';directory=$false;length=3},[pscustomobject]@{relative='receipt.json';directory=$false;length=2})}
Assert-ReleasePairInventory $tree $invContract @('receipt.json');Check $true 'Complete inventory accepted'
$bad=CopyObject $tree;$bad.rows[1].length=4
Reject {Assert-ReleasePairInventory $bad $invContract @('receipt.json')} 'Other file length change rejected BEFORE delete'
$bad=CopyObject $tree;$bad.rows=@($bad.rows[1..2])
Reject {Assert-ReleasePairInventory $bad $invContract @('receipt.json')} 'Missing directory rejected'
$bad=CopyObject $tree;$bad.rows=@($bad.rows[0..1])
Reject {Assert-ReleasePairInventory $bad $invContract @('receipt.json')} 'Missing metadata rejected'
$bad=CopyObject $tree;$bad.complete=$false
Reject {Assert-ReleasePairInventory $bad $invContract @('receipt.json')} 'Incomplete enumeration rejected'
$workspace=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$fixture=Join-Path $workspace ('.tmp\release-pair-tests-'+[Guid]::NewGuid().ToString('N'))
if(-not $fixture.StartsWith($workspace+'\.tmp\',[StringComparison]::OrdinalIgnoreCase)){throw 'Fixture outside workspace.'}
Assert-QPlain ([IO.Path]::GetDirectoryName($fixture));$null=[IO.Directory]::CreateDirectory($fixture)
function NewFixtureFile {
    param([string]$Path,[string]$Text)
    $null=[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($Path));$s=[IO.File]::Open($Path,'CreateNew','Write','None')
    try{$b=[Text.UTF8Encoding]::new($false).GetBytes($Text);$s.Write($b,0,$b.Length)}finally{$s.Dispose()}
}
foreach($mode in @('success','locked-last','changed-last','changed-keep','ads-last','ads-keep','closed-journal')){
    $root=Join-Path $fixture $mode;$null=[IO.Directory]::CreateDirectory($root)
    $rows=@();$streams=@{};$ids=@{};$all=[Collections.Generic.List[IDisposable]]::new();$guards=@{}
    $confirmed=[Collections.Generic.List[object]]::new();$count=$(if($mode -ceq 'success'){22}else{3})
    try{
        for($i=1;$i -le $count;$i++){
            $rel='R1\kit\'+$i+'.txt';$retained='R2\kit\'+$i+'.txt'
            NewFixtureFile (Join-Path $root $rel) ('fixture-'+$i);NewFixtureFile (Join-Path $root $retained) ('fixture-'+$i)
            $s=[IO.File]::Open((Join-Path $root $rel),'Open','Read','Read')
            try{$rows+=[pscustomobject]@{relative_path=$rel;retained_relative_path=$retained;length=$s.Length;sha256=(Get-QHash $s)}}finally{$s.Dispose()}
        }
        NewFixtureFile ($root+'\R1\kit\unique.json') '{"side":"R1"}'
        NewFixtureFile ($root+'\R2\kit\unique.json') '{"side":"R2"}'
        $last=Join-Path $root $rows[-1].relative_path;$lastKeep=Join-Path $root $rows[-1].retained_relative_path
        if($mode -ceq 'changed-last'){[IO.File]::WriteAllText($last,'changed')}
        if($mode -ceq 'changed-keep'){[IO.File]::WriteAllText($lastKeep,'changed')}
        if($mode -ceq 'ads-last'){Set-Content -LiteralPath $last -Stream 'private' -Value 'not-retained'}
        if($mode -ceq 'ads-keep'){Set-Content -LiteralPath $lastKeep -Stream 'private' -Value 'not-retained'}
        foreach($row in $rows){foreach($name in @($row.relative_path,$row.retained_relative_path)){
            $path=Join-Path $root $name;Open-CleanupDirectoryGuard ([IO.Path]::GetDirectoryName($path)) $guards
            $s=[SflCleanupNativeV1]::OpenFile($path,$false);$all.Add($s);$streams[$name]=$s
            $ids[$name]=[SflCleanupNativeV1]::Identity($s.SafeFileHandle,$path,$false)
        }}
        if($mode -ceq 'locked-last'){$all.Add([IO.File]::Open($last,'Open','Read','Read'))}
        $jPath=$root+'\journal.jsonl';$journal=[IO.File]::Open($jPath,'CreateNew','Write','Read');$all.Add($journal)
        if($mode -ceq 'closed-journal'){$journal.Dispose()}
        $p=[pscustomobject]@{files=$rows}
        if($mode -ceq 'success'){
            Invoke-ReleasePairDeletion $root $p $streams $ids $journal $confirmed
            Check ($confirmed.Count -eq 22) '22 synthetic deletions confirmed'
            foreach($row in $rows){Check (-not [IO.File]::Exists((Join-Path $root $row.relative_path)) -and (Get-QHash $streams[$row.retained_relative_path]) -ceq $row.sha256) ('Retained copy and deleted source '+$row.relative_path)}
            Check ([IO.File]::Exists($root+'\R1\kit\unique.json') -and [IO.File]::Exists($root+'\R2\kit\unique.json')) 'Both unique JSONs remain'
            Check ([IO.Directory]::Exists($root+'\R1\kit') -and [IO.Directory]::Exists($root+'\R2\kit')) 'Both directory trees remain'
            $journal.Dispose();$records=@(Get-Content -LiteralPath $jPath|ForEach-Object {ConvertFrom-Json -InputObject $_})
            Check ($records.Count -eq 44) '22 durable intents and deletion receipts'
            for($i=0;$i -lt $records.Count;$i+=2){Check ($records[$i].event -ceq 'DELETE_INTENT' -and $records[$i+1].event -ceq 'DELETED' -and $records[$i].file.relative_path -ceq $records[$i+1].relative_path -and $records[$i].file.retained_relative_path.StartsWith('R2\')) ('Intent recovery mapping '+$i)}
        }else{
            Reject {Invoke-ReleasePairDeletion $root $p $streams $ids $journal $confirmed} ('Stopped '+$mode)
            Check ($confirmed.Count -eq 0 -and @($rows|Where-Object {-not [IO.File]::Exists((Join-Path $root $_.relative_path))}).Count -eq 0) ('No deletion before all checks '+$mode)
        }
    }finally{foreach($s in $all){$s.Dispose()};foreach($g in $guards.Values){$g.handle.Dispose()}}
}
$main=[IO.File]::ReadAllText((Join-Path $PSScriptRoot 'cleanup-v1019-release-pair.ps1'))
Check ($main -notmatch 'Remove-Item|Stop-Process|Start-Process|Invoke-RestMethod|Invoke-WebRequest|DeleteEmptyDirectory|Directory\]::Delete') 'No recursive/directory deletion, restart or API calls'
Check ($main.Contains('[switch]$Execute') -and $main.Contains('if(-not $Execute)')) 'Default plan only'
Check (-not $main.Contains('historicalReferences') -and $main.Contains('Retained text references R1; preserve all pair copies pending review.')) 'Unique JSON references are not silently exempted'
[pscustomobject]@{result='RELEASE_PAIR_SYNTHETIC_TEST_PASS';assertions=$checks.Count;fixture=$fixture;checks=$checks.ToArray();server_execution_performed=$false} | ConvertTo-Json -Depth 5
