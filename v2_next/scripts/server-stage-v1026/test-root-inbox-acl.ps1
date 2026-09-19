[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Helper,[Parameter(Mandatory=$true)][string]$OutputRoot,[string]$Launcher)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($PSVersionTable.PSEdition -cne 'Desktop' -or $PSVersionTable.PSVersion.ToString() -notlike '5.1.*' -or -not [Environment]::Is64BitProcess){throw 'Native x64 PS5.1 tests required.'}
$checks=[Collections.Generic.List[string]]::new()
function Check {param([bool]$Ok,[string]$Name) if(-not $Ok){throw ('TEST: '+$Name)};$checks.Add($Name)}
function Reject {param([scriptblock]$Code,[string]$Name) $caught=$false;try{& $Code}catch{$caught=$true};Check $caught $Name}
$tokens=$null;$errors=$null;$ast=[Management.Automation.Language.Parser]::ParseFile($Helper,[ref]$tokens,[ref]$errors)
Check ($errors.Count -eq 0) 'Helper native parser'
foreach($fn in $ast.FindAll({param($n)$n -is [Management.Automation.Language.FunctionDefinitionAst]},$true)){. ([scriptblock]::Create($fn.Extent.Text))}
InitializeAclGuard
function MemoryFacts {
    param([string]$Sddl)
    $a=[Security.AccessControl.DirectorySecurity]::new();$a.SetSecurityDescriptorSddlForm($Sddl)
    $raw=[Security.AccessControl.RawSecurityDescriptor]::new($a.GetSecurityDescriptorBinaryForm(),0)
    [pscustomobject]@{directory=$true;acl=$a;owner=$a.GetOwner([Security.Principal.SecurityIdentifier]).Value;protected=$a.AreAccessRulesProtected;canonical=$a.AreAccessRulesCanonical;raw_count=$raw.DiscretionaryAcl.Count;rules=@($a.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))}
}
$serverUser='S-1-5-21-2762931165-1280404403-2847611662-1001'
$three='(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FA;;;'+$serverUser+')'
$rootSddl='O:BAG:BAD:P'+$three
$inboxSddl='O:'+$serverUser+'G:BAD:AI'+$three.Replace('OICI;','OICIID;')
$f=MemoryFacts $rootSddl
AssertAclShape $f 'S-1-5-32-544' @('S-1-5-18','S-1-5-32-544',$serverUser) $true $false
Check $true 'Exact reported root shape accepted in memory'
$f=MemoryFacts $inboxSddl
AssertAclShape $f $serverUser @('S-1-5-18','S-1-5-32-544',$serverUser) $false $true
ProtectInboxAclInMemory $f.acl
$sections=[Security.AccessControl.AccessControlSections]'Access,Owner,Group'
$protectedInbox=$f.acl.GetSecurityDescriptorSddlForm($sections)
AssertAclShape (MemoryFacts $protectedInbox) $serverUser @('S-1-5-18','S-1-5-32-544',$serverUser) $true $false
Check $true 'Exact reported inbox becomes protected with all rights and owner preserved'
foreach($mode in @('extra','deny','inherited-root','unprotected-root','wrong-owner','missing-admin','read-only','inherit-only')){
    $bad=$rootSddl
    switch($mode){
        extra {$bad+='(A;;FR;;;WD)'}
        deny {$bad=$bad.Replace('(A;','(D;')}
        inherited-root {$bad=$bad.Replace('OICI;','OICIID;')}
        unprotected-root {$bad=$bad.Replace('D:P','D:')}
        wrong-owner {$bad=$bad.Replace('O:BA','O:SY')}
        missing-admin {$bad=$bad.Replace('(A;OICI;FA;;;BA)','')}
        read-only {$bad=$bad.Replace('FA;;;'+$serverUser,'FR;;;'+$serverUser)}
        inherit-only {$bad=$bad.Replace('OICI;','OICIIO;')}
    }
    Reject {AssertAclShape (MemoryFacts $bad) 'S-1-5-32-544' @('S-1-5-18','S-1-5-32-544',$serverUser) $true $false} ('Reject root '+$mode)
}
$duplicate=MemoryFacts $rootSddl;$duplicate.rules+=,$duplicate.rules[2];$duplicate.raw_count=4
Reject {AssertAclShape $duplicate 'S-1-5-32-544' @('S-1-5-18','S-1-5-32-544',$serverUser) $true $false} 'Duplicate rule fact rejected'
Reject {AssertAclShape (MemoryFacts $rootSddl) $serverUser @('S-1-5-18','S-1-5-32-544',$serverUser) $false $true} 'Wrong inbox shape rejected'
AssertDescriptor $rootSddl ($rootSddl.Replace('D:P','D:PAI'));Check $true 'OS automatic-inheritance flag addition only accepted'
Reject {AssertDescriptor $rootSddl ($rootSddl.Replace('G:BA','G:SY'))} 'Group change rejected'
Reject {AssertDescriptor $rootSddl ($rootSddl.Replace('FA;;;BA','FR;;;BA'))} 'Rights change rejected'
Reject {AssertDescriptor ($rootSddl.Replace('D:P','D:PAI')) $rootSddl} 'AI flag removal rejected'

# Filesystem fixtures never use server paths. Only the owner expectation in the
# validator is adapted, since this non-elevated developer cannot set a foreign owner.
$devSid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
Check ($devSid -cne $serverUser) 'Developer and server SID are distinct'
$originalShape=(Get-Command AssertAclShape).ScriptBlock
function AssertAclShape {
    param([object]$Facts,[string]$Owner,[string[]]$Sids,[bool]$Protected,[bool]$Inherited)
    if($Owner -ceq $serverUser){$Owner=$devSid}
    & $originalShape $Facts $Owner $Sids $Protected $Inherited
}
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$fixture=[IO.Path]::GetFullPath($OutputRoot)
Check ($fixture.StartsWith($repo+'\artifacts\',[StringComparison]::OrdinalIgnoreCase) -and -not [IO.Directory]::Exists($fixture) -and -not [IO.File]::Exists($fixture)) 'Fresh fixture strictly inside artifacts'
[void][IO.Directory]::CreateDirectory($fixture)
function FixturePrivate {
    param([string]$Path,[switch]$Extra)
    $a=[Security.AccessControl.DirectorySecurity]::new();$a.SetOwner([Security.Principal.SecurityIdentifier]::new($devSid));$a.SetAccessRuleProtection($true,$false)
    $sids=@('S-1-5-18',$devSid);if($Extra){$sids+=,$serverUser}
    foreach($sid in $sids){$a.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($sid),'FullControl','ContainerInherit,ObjectInherit','None','Allow'))}
    [void][IO.Directory]::CreateDirectory($Path,$a)
}
$writer=(Get-Command WriteAclRecord).ScriptBlock;$aclWriter=(Get-Command SaveAclDirectory).ScriptBlock
foreach($mode in @('success','protected-inbox','extra-root-child','unprotected-runs','inbox-junction','inbox-hardlink','budget','closed-journal','backup-hash-mismatch','new-inbox-entry-at-intent','root-drift-at-intent','second-write-failure','post-first-verification-failure')){
    $root=$fixture+'\'+$mode;FixturePrivate $root -Extra
    foreach($name in @('backups','inventory','runs','tmp')){FixturePrivate ($root+'\'+$name)}
    [void][IO.Directory]::CreateDirectory($root+'\inbox\nested\deep')
    [IO.File]::WriteAllText(($root+'\inbox\transfer.txt'),'untouched transfer fixture')
    [IO.File]::WriteAllText(($root+'\inbox\nested\deep\data.txt'),'untouched nested fixture')
    FixturePrivate ($root+'\inbox\protected-child')
    $ctx=@{guards=@{};clock=[Diagnostics.Stopwatch]::StartNew()}
    $attempted=[Collections.Generic.List[string]]::new();$returned=[Collections.Generic.List[string]]::new();$journal=$null;$backup=$null
    try{
        if($mode -ceq 'extra-root-child'){[IO.File]::WriteAllText(($root+'\extra.txt'),'unexpected')}
        if($mode -ceq 'unprotected-runs'){$a=[IO.Directory]::GetAccessControl($root+'\runs');$a.SetAccessRuleProtection($false,$true);[IO.Directory]::SetAccessControl(($root+'\runs'),$a)}
        if($mode -ceq 'inbox-junction'){$null=New-Item -ItemType Junction -Path ($root+'\inbox\junction') -Target ($root+'\tmp')}
        if($mode -ceq 'inbox-hardlink'){$null=New-Item -ItemType HardLink -Path ($root+'\inbox\linked.txt') -Target ($root+'\inbox\transfer.txt')}
        if($mode -ceq 'budget'){$ctx.clock=[pscustomobject]@{Elapsed=[TimeSpan]::FromSeconds(121)}}
        if($mode -cin @('extra-root-child','unprotected-runs','inbox-junction','inbox-hardlink','budget')){
            Reject {SnapshotAclBoundary $root $ctx} ('Preflight rejects '+$mode)
            Check ($attempted.Count -eq 0) ('No writes for '+$mode);continue
        }
        $expected=SnapshotAclBoundary $root $ctx
        $beforeRoot=$expected[$root].sddl;$beforeInbox=$expected[$root+'\inbox'].sddl
        $original=ConvertFrom-Json -InputObject ($expected|ConvertTo-Json -Depth 5)
        $hashBefore=(Get-FileHash -LiteralPath ($root+'\inbox\transfer.txt') -Algorithm SHA256).Hash
        $backupBytes=[Text.UTF8Encoding]::new($false).GetBytes(($expected.Values|ConvertTo-Json -Depth 5))
        WriteAclNew ($root+'\tmp\before.json') $backupBytes
        Reject {WriteAclNew ($root+'\tmp\before.json') $backupBytes} ('No evidence overwrite '+$mode)
        $backup=[IO.File]::Open(($root+'\tmp\before.json'),'Open','Read','Read');$hash=HashAclStream $backup
        if($mode -ceq 'backup-hash-mismatch'){$hash='0'*64}
        $journal=[IO.File]::Open(($root+'\tmp\journal.jsonl'),'CreateNew','Write','Read')
        if($mode -ceq 'protected-inbox'){$a=[IO.Directory]::GetAccessControl($root+'\inbox');$a.SetAccessRuleProtection($true,$true);[IO.Directory]::SetAccessControl(($root+'\inbox'),$a)}
        if($mode -ceq 'closed-journal'){$journal.Dispose()}
        if($mode -ceq 'new-inbox-entry-at-intent'){
            function WriteAclRecord {param([IO.FileStream]$Stream,[object]$Record)
                & $writer $Stream $Record
                if($Record.event -ceq 'INTENT'){[IO.File]::WriteAllText(($root+'\inbox\late.txt'),'concurrent upload')}
            }
        }
        if($mode -ceq 'root-drift-at-intent'){
            function WriteAclRecord {param([IO.FileStream]$Stream,[object]$Record)
                & $writer $Stream $Record
                if($Record.event -ceq 'INTENT'){$a=[IO.Directory]::GetAccessControl($root);$a.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new('Everyone','Read','Allow'));[IO.Directory]::SetAccessControl($root,$a)}
            }
        }
        if($mode -ceq 'second-write-failure'){
            function SaveAclDirectory {param([string]$Path,[Security.AccessControl.DirectorySecurity]$Acl)
                if($Path -ceq $root){throw 'Synthetic second write refusal'};& $aclWriter $Path $Acl
            }
        }
        if($mode -ceq 'post-first-verification-failure'){
            function WriteAclRecord {param([IO.FileStream]$Stream,[object]$Record)
                if($Record.event -ceq 'VERIFIED'){throw 'Synthetic verification journal failure'};& $writer $Stream $Record
            }
        }
        if($mode -ceq 'success'){
            InvokeRootInboxPlan $root $devSid $serverUser $expected $ctx $journal $backup $hash $attempted $returned
            Check ($attempted.Count -eq 2 -and $returned.Count -eq 2) 'Exactly inbox then root ACL writes'
            Check ($returned[0] -ceq ($root+'\inbox') -and $returned[1] -ceq $root) 'Write ordering correct'
            AssertAclShape (AclFacts $root) $devSid @('S-1-5-18',$devSid) $true $false
            AssertAclShape (AclFacts ($root+'\inbox')) $serverUser @('S-1-5-18',$devSid,$serverUser) $true $false
            Check $true 'Root removes only extra rule; inbox retains all three'
            $actual=SnapshotAclBoundary $root $ctx
            foreach($p in $original.PSObject.Properties){if($p.Name -cnotin @($root,($root+'\inbox'))){AssertDescriptor $p.Value.sddl $actual[$p.Name].sddl;Check $true ('Unchanged ACL '+$p.Name.Substring($root.Length))}}
            Check ((Get-FileHash -LiteralPath ($root+'\inbox\transfer.txt') -Algorithm SHA256).Hash -ceq $hashBefore) 'Transfer file bytes unchanged'
            Check ((HashAclStream $backup) -ceq $hash) 'Original backup remains bound'
            Reject {InvokeRootInboxPlan $root $devSid $serverUser $expected $ctx $journal $backup $hash $attempted $returned} 'Completed plan cannot run twice'
            Check ($returned.Count -eq 2) 'No third ACL write on rerun'
            $journal.Dispose();$events=@(Get-Content -LiteralPath ($root+'\tmp\journal.jsonl')|ForEach-Object {$_|ConvertFrom-Json})
            Check ($events.Count -eq 4 -and $events[0].event -ceq 'INTENT' -and $events[1].event -ceq 'VERIFIED' -and $events[2].event -ceq 'INTENT' -and $events[3].event -ceq 'VERIFIED') 'Durable intents precede both writes'
        }else{
            Reject {InvokeRootInboxPlan $root $devSid $serverUser $expected $ctx $journal $backup $hash $attempted $returned} ('Plan stops '+$mode)
            if($mode -cin @('second-write-failure','post-first-verification-failure')){
                Check ($returned.Count -eq 1 -and $attempted.Count -eq $(if($mode -ceq 'second-write-failure'){2}else{1})) ('Partial change counted '+$mode)
                Check ((AclFacts $root).sddl -ceq $beforeRoot) ('Root unchanged '+$mode)
                Check ((AclFacts ($root+'\inbox')).protected) ('Inbox stays protected; no rollback '+$mode)
            }else{Check ($attempted.Count -eq 0 -and $returned.Count -eq 0) ('Zero writes '+$mode)}
        }
    }finally{
        Set-Item -LiteralPath Function:\WriteAclRecord -Value $writer;Set-Item -LiteralPath Function:\SaveAclDirectory -Value $aclWriter
        if($null -ne $journal){$journal.Dispose()};if($null -ne $backup){$backup.Dispose()}
        foreach($g in $ctx.guards.Values){$g.handle.Dispose()}
    }
}
$text=[IO.File]::ReadAllText($Helper)
Check ($text -notmatch 'Remove-Item|Move-Item|Stop-Process|Start-Process|Invoke-RestMethod|Invoke-WebRequest|icacls|takeown|SetFileInformationByHandle|::Delete\(') 'No deletion, process operations, HTTP or recursive ACL reset'
Check ([regex]::Matches($text,'\[IO.Directory\]::SetAccessControl').Count -eq 1) 'One ACL write call site'
Check ($text.Contains("`$root='C:\ProgramData\SFLOps'") -and $text.Contains("if(-not `$Execute)")) 'Fixed production root and explicit execution switch'
Check ($text.Contains("`$operatorSid='$serverUser'")) 'Fixed operator SID'
if(-not [string]::IsNullOrEmpty($Launcher)){
    $launchText=[IO.File]::ReadAllText($Launcher)
    $null=[Management.Automation.Language.Parser]::ParseInput($launchText,[ref]$tokens,[ref]$errors)
    Check ($errors.Count -eq 0) 'Launcher native PS5.1 parse'
    $dummy=$fixture+'\launcher-fixture.ps1'
    WriteAclNew $dummy ([Text.Encoding]::ASCII.GetBytes('param([switch]$Execute) if(-not $Execute){throw "Missing switch"}; "PINNED_LAUNCHER_TEST_PASS"'))
    $dummyHash=(Get-FileHash -LiteralPath $dummy -Algorithm SHA256).Hash
    $dummyLength=(Get-Item -LiteralPath $dummy).Length
    $helperHash=(Get-FileHash -LiteralPath $Helper -Algorithm SHA256).Hash
    $helperLength=(Get-Item -LiteralPath $Helper).Length
    $testLaunch=$launchText.Replace('C:\Users\user\Desktop\SmartFactory\repair-sflops-root-inbox-r1.ps1',$dummy).Replace($helperHash,$dummyHash).Replace(('$length = '+$helperLength),('$length = '+$dummyLength))
    $pass=@(& ([scriptblock]::Create($testLaunch)))
    Check ($pass.Count -eq 1 -and $pass[0] -ceq 'PINNED_LAUNCHER_TEST_PASS') 'Launcher executes exact held bytes with Execute switch'
    Reject {& ([scriptblock]::Create($testLaunch.Replace($dummyHash,('0'*64))))} 'Launcher rejects mismatched external hash'
    Reject {& ([scriptblock]::Create($testLaunch.Replace(('$length = '+$dummyLength),'$length = 1')))} 'Launcher rejects mismatched length'
}
$report=[ordered]@{result='ROOT_INBOX_ACL_LOCAL_TEST_PASS';assertions=$checks.Count;checks=$checks.ToArray();helper_sha256=(Get-FileHash -LiteralPath $Helper -Algorithm SHA256).Hash;fixture_root=$fixture;production_shapes_tested_in_memory=$true;filesystem_owner_expectation_adapted_for_nonadmin_fixture=$true;server_execution_performed=$false;admin_server_integration_tested=$false}
WriteAclNew ($fixture+'\validation.json') ([Text.UTF8Encoding]::new($false).GetBytes(($report|ConvertTo-Json -Depth 5)))
[pscustomobject]$report|Select-Object result,assertions,server_execution_performed,admin_server_integration_tested|ConvertTo-Json
