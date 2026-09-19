[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($PSVersionTable.PSEdition -cne 'Desktop' -or $PSVersionTable.PSVersion.ToString() -notlike '5.1.*' -or -not [Environment]::Is64BitProcess){throw 'Native PS5.1 x64 required.'}
$checks=[Collections.Generic.List[string]]::new()
function Check {param([bool]$Ok,[string]$Name) if(-not $Ok){throw $Name};$checks.Add($Name)}
function Reject {param([scriptblock]$Code,[string]$Name) $caught=$false;try{& $Code}catch{$caught=$true};Check $caught $Name}
function CopyObject {param([object]$Value) return ConvertFrom-Json -InputObject ($Value|ConvertTo-Json -Depth 20)}
foreach($name in @('read-quarantine-pre-v1020.ps1','cleanup-archive-core.ps1','repair-sflops-acl.ps1')){
    $t=$null;$e=$null;$ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot $name),[ref]$t,[ref]$e)
    Check (@($e).Count -eq 0) ($name+' native parse')
    foreach($fn in $ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst]},$true)){. ([scriptblock]::Create($fn.Extent.Text))}
}
Initialize-CleanupNative
$extra='S-1-5-21-2762931165-1280404403-2847611662-1001'
$valid=[pscustomobject]@{path='synthetic-memory';directory=$true;owner_sid='S-1-5-32-544';protected=$true;canonical=$true;raw_ace_count=3;
    rules=@(foreach($sid in @('S-1-5-18','S-1-5-32-544',$extra)){[pscustomobject]@{sid=$sid;type='Allow';rights=2032127;inherited=$false;inheritance=3;propagation=0}})}
Assert-RepairAclShape $valid $extra -IncludeExtra;Check $true 'Production exact three-ACE shape accepted'
$two=CopyObject $valid;$two.rules=@($two.rules[0..1]);$two.raw_ace_count=2
Assert-RepairAclShape $two $extra;Check $true 'Production exact two-ACE result accepted'
$descriptor='O:BAG:BAD:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)'
Assert-RepairPersistedDescriptor $descriptor $descriptor;Check $true 'Exact descriptor accepted'
Assert-RepairPersistedDescriptor $descriptor ($descriptor.Replace('D:P','D:PAI'));Check $true 'Only Windows DACL AI addition accepted'
Reject {Assert-RepairPersistedDescriptor ($descriptor.Replace('D:P','D:PAI')) $descriptor} 'AI flag removal rejected'
Reject {Assert-RepairPersistedDescriptor $descriptor ($descriptor.Replace('G:BA','G:SY'))} 'Unexpected group change rejected'
Reject {Assert-RepairPersistedDescriptor $descriptor ($descriptor.Replace('D:P','D:'))} 'Protection flag removal rejected'
Reject {Assert-RepairPersistedDescriptor $descriptor ($descriptor.Replace('FA;;;BA','FR;;;BA'))} 'Admin rights change rejected'
foreach($mode in @('owner','unprotected','deny','read-only','inherited','inherit-only','noncanonical','unknown-ace','wrong-sid','duplicate','missing-admin')){
    $bad=CopyObject $valid
    switch($mode){
        owner {$bad.owner_sid=$extra}
        unprotected {$bad.protected=$false}
        deny {$bad.rules[2].type='Deny'}
        read-only {$bad.rules[2].rights=131209}
        inherited {$bad.rules[2].inherited=$true}
        inherit-only {$bad.rules[2].propagation=2}
        noncanonical {$bad.canonical=$false}
        unknown-ace {$bad.raw_ace_count=4}
        wrong-sid {$bad.rules[2].sid='S-1-1-0'}
        duplicate {$bad.rules[1].sid='S-1-5-18'}
        missing-admin {$bad.rules=@($bad.rules[0],$bad.rules[2]);$bad.raw_ace_count=2}
    }
    Reject {Assert-RepairAclShape $bad $extra -IncludeExtra} ('Production ACL rejects '+$mode)
}
# Native filesystem tests are confined to small NEW developer-owned fixtures.
# This non-elevated host cannot create Administrators-owned fixtures. Replace ONLY
# that SID in the test validator, not in the production file or mutation function.
$testOwner=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$productionAssert=(Get-Command Assert-RepairAclShape).ScriptBlock
$testAssert=$productionAssert.ToString().Replace('S-1-5-32-544',$testOwner)
Set-Item -LiteralPath Function:\Assert-RepairAclShape -Value ([scriptblock]::Create($testAssert))
$workspace=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$fixture=Join-Path $workspace ('.tmp\acl-repair-tests-'+[Guid]::NewGuid().ToString('N'))
if(-not $fixture.StartsWith($workspace+'\.tmp\',[StringComparison]::OrdinalIgnoreCase)){throw 'Fixture scope mismatch.'}
Assert-QPlain ([IO.Path]::GetDirectoryName($fixture));$null=[IO.Directory]::CreateDirectory($fixture)
function TestDirectory {
    param([string]$Path,[switch]$WithExtra)
    $acl=[Security.AccessControl.DirectorySecurity]::new();$acl.SetAccessRuleProtection($true,$false)
    $acl.SetOwner([Security.Principal.SecurityIdentifier]::new($testOwner))
    $sids=@('S-1-5-18',$testOwner);if($WithExtra){$sids+=,$extra}
    foreach($sid in $sids){$acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($sid),'FullControl','ContainerInherit,ObjectInherit','None','Allow'))}
    $null=[IO.Directory]::CreateDirectory($Path,$acl)
}
$originalWriter=(Get-Command Write-CleanupRecord).ScriptBlock
$originalAclWriter=(Get-Command Write-RepairDirectoryAcl).ScriptBlock
foreach($mode in @('success','unprotected-child','unprotected-file','new-child','changed-target','child-group-drift','closed-journal','intent-new-child','intent-target-drift','second-intent-failure','second-write-failure','post-write-journal-failure')){
    $root=Join-Path $fixture $mode;TestDirectory $root -WithExtra
    TestDirectory ($root+'\inventory') -WithExtra;TestDirectory ($root+'\tmp');TestDirectory ($root+'\inventory\old-receipt')
    $targets=@(($root+'\inventory'),$root);$guards=@{};$fileIds=@{};$pins=[Collections.Generic.List[IDisposable]]::new()
    $attempted=[Collections.Generic.List[string]]::new();$confirmed=[Collections.Generic.List[string]]::new()
    $journal=$null
    try{
        foreach($path in $targets){Open-CleanupDirectoryGuard $path $guards}
        $expected=@{};foreach($path in $targets){$facts=Get-RepairAclFacts $path;Assert-RepairAclShape $facts $extra -IncludeExtra;$expected[$path]=ConvertTo-RepairRecord $facts}
        $beforeRoot=$expected[$root].sddl;$beforeInventory=$expected[$root+'\inventory'].sddl
        $child=$root+'\inventory\old-receipt';$childBefore=(Get-RepairAclFacts $child).sddl
        $boundary=Get-RepairBoundary $targets $guards $pins $fileIds
        if($mode -ceq 'unprotected-child'){
            $a=[IO.Directory]::GetAccessControl($child);$a.SetAccessRuleProtection($false,$true);[IO.Directory]::SetAccessControl($child,$a)
            Reject {Get-RepairBoundary $targets $guards $pins $fileIds} 'Unprotected existing child blocks repair'
            Check ((Get-RepairAclFacts $root).sddl -ceq $beforeRoot -and (Get-RepairAclFacts ($root+'\inventory')).sddl -ceq $beforeInventory) 'No parent change on unprotected child'
            continue
        }
        if($mode -ceq 'unprotected-file'){
            [IO.File]::WriteAllText(($root+'\direct.txt'),'fixture only')
            Reject {Get-RepairBoundary $targets $guards $pins $fileIds} 'Unprotected direct FILE blocks repair'
            Check ((Get-RepairAclFacts $root).sddl -ceq $beforeRoot) 'Parent unchanged on unprotected file'
            continue
        }
        if($mode -ceq 'new-child'){TestDirectory ($root+'\new')}
        if($mode -ceq 'changed-target'){
            $a=[IO.Directory]::GetAccessControl($root);$a.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new('S-1-1-0'),'Read','None','None','Allow'));[IO.Directory]::SetAccessControl($root,$a)
        }
        if($mode -ceq 'child-group-drift'){$boundary[$child].acl.sddl+=' '} # Strict comparison includes owner/group/control flags.
        $journal=[IO.File]::Open(($root+'\tmp\journal.jsonl'),'CreateNew','Write','Read')
        if($mode -ceq 'closed-journal'){$journal.Dispose()}
        if($mode -ceq 'intent-new-child'){
            function Write-CleanupRecord {param([IO.FileStream]$Journal,[object]$Record)
                & $originalWriter $Journal $Record
                if($Record.event -ceq 'ACL_CHANGE_INTENT'){TestDirectory ($root+'\late-child')}
            }
        }
        if($mode -ceq 'intent-target-drift'){
            function Write-CleanupRecord {param([IO.FileStream]$Journal,[object]$Record)
                & $originalWriter $Journal $Record
                if($Record.event -ceq 'ACL_CHANGE_INTENT'){
                    $a=[IO.Directory]::GetAccessControl($root);$a.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new('S-1-1-0'),'Read','None','None','Allow'));[IO.Directory]::SetAccessControl($root,$a)
                }
            }
        }
        if($mode -ceq 'second-intent-failure'){
            function Write-CleanupRecord {param([IO.FileStream]$Journal,[object]$Record)
                if($Record.event -ceq 'ACL_CHANGE_INTENT' -and $Record.path -ceq $root){throw 'synthetic second-intent failure'}
                & $originalWriter $Journal $Record
            }
        }
        if($mode -ceq 'post-write-journal-failure'){
            function Write-CleanupRecord {param([IO.FileStream]$Journal,[object]$Record)
                if($Record.event -ceq 'ACL_CHANGE_VERIFIED'){throw 'synthetic post-write journal failure'}
                & $originalWriter $Journal $Record
            }
        }
        if($mode -ceq 'second-write-failure'){
            function Write-RepairDirectoryAcl {param([string]$Path,[Security.AccessControl.DirectorySecurity]$Acl)
                if($Path -ceq $root){throw [UnauthorizedAccessException]::new('synthetic second write refusal')}
                & $originalAclWriter $Path $Acl
            }
        }
        if($mode -ceq 'success'){
            Invoke-RepairAclPlan $targets $extra $expected $boundary $guards $pins $fileIds $journal $attempted $confirmed
            Check ($attempted.Count -eq 2 -and $confirmed.Count -eq 2) 'Exactly two native DACL writes'
            foreach($path in $targets){Assert-RepairAclShape (Get-RepairAclFacts $path) $extra;Check $true ('Two preserved ACEs '+[IO.Path]::GetFileName($path))}
            Check ((Get-RepairAclFacts $child).sddl -ceq $childBefore) 'Protected child owner/group/DACL unchanged'
            Assert-RepairTargetsSame $targets $expected $guards;Check $true 'Final target SDDL and identities match'
            $journal.Dispose();$events=@(Get-Content -LiteralPath ($root+'\tmp\journal.jsonl')|ForEach-Object {ConvertFrom-Json -InputObject $_})
            Check ($events.Count -eq 4 -and $events[0].event -ceq 'ACL_CHANGE_INTENT' -and $events[1].event -ceq 'ACL_CHANGE_VERIFIED' -and $events[2].event -ceq 'ACL_CHANGE_INTENT' -and $events[3].event -ceq 'ACL_CHANGE_VERIFIED') 'Durable intent before each change'
            $expected[$root].sddl+=' '
            Reject {Assert-RepairTargetsSame $targets $expected $guards} 'Final root descriptor drift rejected'
        }else{
            Reject {Invoke-RepairAclPlan $targets $extra $expected $boundary $guards $pins $fileIds $journal $attempted $confirmed} ('Repair stops '+$mode)
            if($mode -cin @('second-intent-failure','second-write-failure','post-write-journal-failure')){
                $wantedAttempts=if($mode -ceq 'second-write-failure'){2}else{1}
                Check ($attempted.Count -eq $wantedAttempts -and $confirmed.Count -eq 1) ('One completed write retained in count '+$mode)
                Check ((Get-RepairAclFacts $root).sddl -ceq $beforeRoot) ('Second target unchanged '+$mode)
                Assert-RepairAclShape (Get-RepairAclFacts ($root+'\inventory')) $extra
                Check $true ('First repair is not automatically rolled back '+$mode)
            }else{Check ($attempted.Count -eq 0 -and $confirmed.Count -eq 0) ('Zero writes '+$mode)}
        }
    }finally{
        Set-Item -LiteralPath Function:\Write-CleanupRecord -Value $originalWriter
        Set-Item -LiteralPath Function:\Write-RepairDirectoryAcl -Value $originalAclWriter
        if($null -ne $journal){$journal.Dispose()};foreach($s in $pins){$s.Dispose()};foreach($g in $guards.Values){$g.handle.Dispose()}
    }
}
Set-Item -LiteralPath Function:\Assert-RepairAclShape -Value $productionAssert
$main=[IO.File]::ReadAllText((Join-Path $PSScriptRoot 'repair-sflops-acl.ps1'))
Check ($main -notmatch 'Remove-CleanupVerifiedFile|DeleteEmptyDirectory|Remove-Item|Stop-Process|Start-Process|Invoke-RestMethod|Invoke-WebRequest|icacls|takeown') 'No deletion/process/API/recursive ACL tools'
Check ($main.Contains('$targets=@(($root+''\inventory''),$root)') -and $main.Contains('if(-not $Execute)')) 'Fixed two targets and default plan-only'
Check (@([regex]::Matches($main,'\[IO.Directory\]::SetAccessControl')).Count -eq 1) 'One reviewed mutation call site'
[pscustomobject]@{result='SFLOPS_ACL_REPAIR_TEST_PASS';assertions=$checks.Count;checks=$checks.ToArray();fixture=$fixture;
    server_execution_performed=$false;native_fixture_owner='CURRENT_DEVELOPER_SID_TEST_ONLY';production_admin_acl_shape_tested_in_memory=$true;
    elevated_server_host_integration_tested=$false}|ConvertTo-Json -Depth 5
