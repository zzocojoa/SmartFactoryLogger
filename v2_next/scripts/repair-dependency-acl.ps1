[CmdletBinding(SupportsShouldProcess,ConfirmImpact='High')]
param([Parameter(Mandatory)][string]$ExpectedIndexSha256)
# Only four disposable rehearsal roots. Owner, group, parents, keepers and server are unchanged.
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$parseErrors=$null;$tokens=$null
$ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot 'remove-dependency-cleanup.ps1'),[ref]$tokens,[ref]$parseErrors)
if($parseErrors.Count){throw 'Shared helper syntax invalid'}
foreach($name in @('PlainPath','ChildPath','StreamHash','AssertTrustedAcl','SaveIndex','CheckTree')){
    $function=$ast.Find({param($n)$n-is[Management.Automation.Language.FunctionDefinitionAst]-and$n.Name-ceq$name},$true)
    if($null-eq$function){throw 'Required shared function missing'}
    . ([scriptblock]::Create($function.Extent.Text))
}
$script:dependencyScriptRoot=$PSScriptRoot
function CheckUsage {
    $result=(& (Join-Path $script:dependencyScriptRoot 'read-dependency-use.ps1'))|ConvertFrom-Json -AsHashtable
    if($result.matches.Count){throw 'Registered or running reference found'}
    return $result
}
function RestrictedDacl([string]$Sddl,[string[]]$Trusted) {
    $raw=[Security.AccessControl.RawSecurityDescriptor]::new($Sddl)
    for($i=$raw.DiscretionaryAcl.Count-1;$i-ge 0;$i--){
        $ace=$raw.DiscretionaryAcl[$i]
        if($ace-isnot[Security.AccessControl.CommonAce]){throw 'Unsupported ACE type'}
        if($ace.AceQualifier-eq[Security.AccessControl.AceQualifier]::AccessAllowed-and$ace.SecurityIdentifier.Value-cnotin$Trusted-and($ace.AccessMask-band 0xD0156)-ne 0){$raw.DiscretionaryAcl.RemoveAce($i);continue}
        $ace.AceFlags=$ace.AceFlags-band(-bnot[Security.AccessControl.AceFlags]::Inherited)
    }
    $raw.SetFlags($raw.ControlFlags-bor[Security.AccessControl.ControlFlags]::DiscretionaryAclProtected)
    $acl=[Security.AccessControl.DirectorySecurity]::new()
    $acl.SetSecurityDescriptorSddlForm($raw.GetSddlForm([Security.AccessControl.AccessControlSections]::Access),[Security.AccessControl.AccessControlSections]::Access)
    return $acl
}
function RuleKeys($Acl,[string[]]$Trusted,[bool]$Filter,[bool]$MakeExplicit) {
    $keys=@(foreach($rule in $Acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])){
        if($Filter-and$rule.AccessControlType-eq'Allow'-and$rule.IdentityReference.Value-cnotin$Trusted-and([int]$rule.FileSystemRights-band 0xD0156)-ne 0){continue}
        $inherited=if($MakeExplicit){$false}else{$rule.IsInherited}
        '{0}|{1}|{2}|{3}|{4}|{5}' -f $rule.IdentityReference.Value,[int]$rule.AccessControlType,[int]$rule.FileSystemRights,[int]$rule.InheritanceFlags,[int]$rule.PropagationFlags,$inherited
    })
    return (($keys|Sort-Object)-join';')
}
function AssertInheritedOnly($Acl) {
    if($Acl.AreAccessRulesProtected-or@($Acl.GetAccessRules($true,$false,[Security.Principal.SecurityIdentifier])).Count){throw 'Protected or explicit descendant ACL requires separate review'}
}
function AccessSddl($Acl){return $Acl.GetSecurityDescriptorSddlForm([Security.AccessControl.AccessControlSections]::Access)}
function OwnerGroup($Acl){return $Acl.GetSecurityDescriptorSddlForm([Security.AccessControl.AccessControlSections]::Owner-bor[Security.AccessControl.AccessControlSections]::Group)}

if($PSVersionTable.PSVersion.Major-lt 7-or[Environment]::MachineName-cne'DESKTOP-SS5CURC'){throw 'Fixed development host and PowerShell 7 required'}
if(-not$WhatIfPreference){
    $principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
    if(-not$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'This host Set-Acl requires an administrator PowerShell session. No ACL/registry changes performed.'}
}
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'));$registry=Join-Path $repo 'verification-files.local.json'
[void](PlainPath $registry)
if((Get-FileHash -LiteralPath $registry).Hash-cne$ExpectedIndexSha256){throw 'Registry hash differs'}
$index=[IO.File]::ReadAllText($registry)|ConvertFrom-Json -AsHashtable
if($index.host-cne[Environment]::MachineName-or$index.workspace-cne$repo){throw 'Registry host/workspace differs'}
$plan=@($index.audits|Where-Object id -ceq '31bd411f-0c64-469c-91ed-f5c3acae335f')
$hold=@($index.audits|Where-Object id -ceq '6f4737da-d677-4cb1-b919-d79f48bd991d')
if($plan.Count-ne 1-or$hold.Count-ne 1){throw 'Exact approved records missing'}
$plan=$plan[0];$hold=$hold[0]
if($hold.state-cne'HOLD_ACL_TRUST_UNRESOLVED'-or$plan.Contains('cleanup')-or@($index.audits|Where-Object kind -ceq 'DESKTOP_DEPENDENCY_ACL_REPAIR').Count){throw 'Previous repair/removal attempted; no automatic retry'}
$run=Join-Path $repo '.tmp\dep-428c970f-1f0e-4127-802c-7b4ba9d621c0'
$rootMap=[ordered]@{'test-node'=(Join-Path $run 'node\node_modules');'test-frontend'=(Join-Path $run 'frontend\node_modules');'test-python'=(Join-Path $run 'venv');'test-node-cache'=(Join-Path $run 'temp\node-compile-cache')}
$trusted=@('S-1-5-18','S-1-5-32-544',[Security.Principal.WindowsIdentity]::GetCurrent().User.Value)
$roots=@($plan.roots|Where-Object {$rootMap.Contains($_.id)})
if($roots.Count-ne 4-or$plan.keep_root-cne$run){throw 'Repair scope differs'}
$rows=[Collections.Generic.List[object]]::new();$byRoot=@{}
foreach($root in $roots){
    if($root.root-cne$rootMap[$root.id]){throw 'Repair root differs'}
    $expectedFiles=[Collections.Generic.List[string]]::new();$expectedDirs=[Collections.Generic.List[string]]::new()
    foreach($relative in $root.directories){$path=if($relative){ChildPath $root.root $relative}else{$root.root};$expectedDirs.Add($path);$rows.Add(@{root_id=$root.id;relative=$relative;directory=$true;path=$path})}
    foreach($file in $plan.files){if($file.root_id-ceq$root.id){$path=ChildPath $root.root $file.relative;$expectedFiles.Add($path);$rows.Add(@{root_id=$root.id;relative=$file.relative;directory=$false;path=$path})}}
    CheckTree $root.root $expectedFiles.ToArray() $expectedDirs.ToArray()
    $byRoot[$root.id]=@{files=$expectedFiles.ToArray();directories=$expectedDirs.ToArray()}
}
if($rows.Count-ne 82283){throw 'Approved descendant count differs'}
$sddls=[Collections.Generic.List[string]]::new();$pool=@{};$records=[Collections.Generic.List[object]]::new();$outside=[Collections.Generic.List[object]]::new()
$clock=[Diagnostics.Stopwatch]::StartNew();$last=0;$begun=$false;$completed=$false;$version=$ExpectedIndexSha256
function RepairProgress([string]$Phase,[int]$Count){if($clock.Elapsed.TotalSeconds-$script:last-ge 25){Write-Host "[ACL] $Phase count=$Count elapsed=$($clock.Elapsed.ToString('hh\:mm\:ss'))";$script:last=$clock.Elapsed.TotalSeconds}}
function Publish {
    $index.updated_at=[DateTimeOffset]::Now.ToString('o')
    [void](SaveIndex $index $registry $script:version)
    $script:version=(Get-FileHash -LiteralPath $registry).Hash
}
try {
    Write-Host '[1/4] Read all current descendant ACLs and unchanged outside boundaries. No ACL changes yet.'
    $usageBefore=CheckUsage
    foreach($row in $rows){
        [void](PlainPath $row.path);$acl=Get-Acl -LiteralPath $row.path
        if($acl.GetOwner([Security.Principal.SecurityIdentifier]).Value-cnotin$trusted){throw 'Unexpected owner; no ownership changes authorized'}
        AssertInheritedOnly $acl
        $sddl=$acl.Sddl
        if(-not$pool.ContainsKey($sddl)){$pool[$sddl]=$sddls.Count;$sddls.Add($sddl)}
        $records.Add(@{root_id=$row.root_id;relative=$row.relative;directory=$row.directory;sddl_id=$pool[$sddl]})
        RepairProgress 'acl-backup-inventory' $records.Count
    }
    # Every retained file, its ancestors inside the rehearsal root, and old roots stay unchanged.
    $boundaryPaths=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach($keep in $plan.keep_files){
        $path=ChildPath $run $keep.relative;[void]$boundaryPaths.Add($path)
        $parent=[IO.Path]::GetDirectoryName($path)
        while($parent.StartsWith($run,[StringComparison]::OrdinalIgnoreCase)){
            [void]$boundaryPaths.Add($parent);if($parent-ieq$run){break};$parent=[IO.Path]::GetDirectoryName($parent)
        }
    }
    foreach($root in $roots){[void]$boundaryPaths.Add([IO.Path]::GetDirectoryName($root.root))}
    foreach($root in $plan.roots){if(-not$rootMap.Contains($root.id)){[void]$boundaryPaths.Add($root.root)}}
    [void]$boundaryPaths.Add($repo);[void]$boundaryPaths.Add([IO.Path]::GetDirectoryName($run))
    foreach($path in $boundaryPaths){[void](PlainPath $path);$outside.Add(@{path=$path;sddl=(Get-Acl -LiteralPath $path).Sddl})}
    $proposed=@{}
    foreach($root in $roots){
        $before=Get-Acl -LiteralPath $root.root
        $prior=@($hold.snapshot.roots|Where-Object id -ceq $root.id)
        if($prior.Count-ne 1-or$prior[0].path-cne$root.root-or$prior[0].sddl-cne$before.Sddl-or$prior[0].outside_writers.Count-ne 11){throw 'Root differs from reviewed HOLD snapshot'}
        $pinned=@($records|Where-Object {$_.root_id-ceq$root.id-and$_.relative-ceq''})
        if($pinned.Count-ne 1-or$before.Sddl-cne$sddls[$pinned[0].sddl_id]){throw 'Root ACL drifted before backup'}
        $proposed[$root.id]=RestrictedDacl $before.Sddl $trusted
        if((AccessSddl $proposed[$root.id])-ceq(AccessSddl $before)){throw 'Unexpected no-op ACL repair'}
    }
    # Explicitly prove no hard-linked candidate can propagate an ACL change outside these paths.
    $linkCheck=& node (Join-Path $PSScriptRoot 'check-dependency-links.cjs')
    if($LASTEXITCODE-ne 0){throw 'Hard-link / tree check failed'}
    $linkCheck=$linkCheck|ConvertFrom-Json -AsHashtable
    $usagePrewrite=CheckUsage
    if((Get-FileHash -LiteralPath $registry).Hash-cne$version){throw 'Concurrent registry update'}
    Write-Host "[VERIFIED] 4 roots / $($records.Count) original ACL records; $($outside.Count) preserved boundary records."
    if(-not$PSCmdlet.ShouldProcess('Four exact rehearsal dependency roots','Back up ACLs in registry, protect root DACLs, remove only untrusted write ACEs and verify inherited descendants')){return}
    $repair=@{id=[Guid]::NewGuid().ToString();kind='DESKTOP_DEPENDENCY_ACL_REPAIR';plan_id=$plan.id;hold_id=$hold.id;state='APPLYING';at=[DateTimeOffset]::Now.ToString('o');authority='User approved backup and limited ACL repair of these four rehearsal roots and subsequent approved cleanup on 2026-09-16.';original_registry_sha256=$version;backup_records=@($records.ToArray());sddl_pool=@($sddls.ToArray());outside_boundaries=@($outside.ToArray());roots=@($roots|ForEach-Object {@{id=$_.id;path=$_.root;proposed_access_sddl=(AccessSddl $proposed[$_.id])}});root_requests=@();verified_roots=@();direct_acl_writes=0;inherited_entries_verified=0;deleted_files=0;remote_server_operations=0;owner_group_changes=0;usage_before=$usageBefore;usage_prewrite=$usagePrewrite;hard_link_check=$linkCheck;error=$null;rollback='Original Owner/Group/DACL for every in-scope entry are indexed in backup_records/sddl_pool. Restore DACLs only in a separately reviewed operation; no automatic rollback. Parent/project/keeper ACLs are unchanged.'}
    $event=@{kind=$repair.kind;audit_id=$repair.id;at=$repair.at;state='APPLYING';acl_writes=0;deleted_files=0;deleted_bytes=0;remote_server_operations=0}
    $index.audits=@($index.audits)+$repair;$index.history=@($index.history)+$event
    Publish;$begun=$true
    Write-Host '[2/4] Durable ACL backup published. Apply only the four root DACL changes.'
    foreach($root in $roots){
        $repair.root_requests+= $root.id;Publish
        [void](PlainPath $root.root);$before=Get-Acl -LiteralPath $root.root
        $pinned=@($records|Where-Object {$_.root_id-ceq$root.id-and$_.relative-ceq''})[0]
        if($before.Sddl-cne$sddls[$pinned.sddl_id]){throw 'Root ACL changed before mutation'}
        Set-Acl -LiteralPath $root.root -AclObject $proposed[$root.id] -Confirm:$false
        $repair.direct_acl_writes++
        $after=Get-Acl -LiteralPath $root.root
        if(-not$after.AreAccessRulesProtected-or(RuleKeys $after $trusted $false $false)-cne(RuleKeys $before $trusted $true $true)-or(OwnerGroup $after)-cne(OwnerGroup $before)){throw 'Root ACL postcondition failed'}
        AssertTrustedAcl $after;$repair.verified_roots+= $root.id;Publish
    }
    Write-Host '[3/4] Verify every descendant ACL, exact membership, and all outside boundaries.'
    for($i=0;$i-lt$rows.Count;$i++){
        $row=$rows[$i];[void](PlainPath $row.path);$after=Get-Acl -LiteralPath $row.path
        $original=if($row.directory){[Security.AccessControl.DirectorySecurity]::new()}else{[Security.AccessControl.FileSecurity]::new()}
        $original.SetSecurityDescriptorSddlForm($sddls[$records[$i].sddl_id])
        if((OwnerGroup $after)-cne(OwnerGroup $original)){throw 'Owner or group changed'}
        if($row.relative){AssertInheritedOnly $after}
        if((RuleKeys $after $trusted $false $false)-cne(RuleKeys $original $trusted $true (-not[bool]$row.relative))){throw 'Exact retained ACE set differs'}
        AssertTrustedAcl $after;$repair.inherited_entries_verified++;RepairProgress 'acl-postcheck' $repair.inherited_entries_verified
    }
    foreach($root in $roots){CheckTree $root.root $byRoot[$root.id].files $byRoot[$root.id].directories}
    $contentAfter=& node (Join-Path $PSScriptRoot 'check-dependency-links.cjs')
    if($LASTEXITCODE-ne 0){throw 'Post-repair content or hard-link check failed'}
    $repair.content_postcheck=$contentAfter|ConvertFrom-Json -AsHashtable
    $repair.concurrency_limitation='Single operator, no concurrent package work required. Parent ACLs are unchanged and may permit DeleteChild; path checks and file hashes are not protection against an adversarial parent replacement race.'
    foreach($boundary in $outside){[void](PlainPath $boundary.path);if((Get-Acl -LiteralPath $boundary.path).Sddl-cne$boundary.sddl){throw 'Outside ACL changed'}}
    $hold.original_state=$hold.state;$hold.state='RESOLVED_BY_SCOPED_ACL_REPAIR';$hold.resolution_audit_id=$repair.id
    $repair.state='COMPLETE';$event.state='COMPLETE';$event.acl_writes=$repair.direct_acl_writes;$repair.completed_at=[DateTimeOffset]::Now.ToString('o')
    Publish;$completed=$true
    Write-Host '[4/4] ACL repair complete. File deletion has not started; run the separate deletion preflight next.'
    @{state=$repair.state;id=$repair.id;direct_acl_writes=$repair.direct_acl_writes;inherited_entries_verified=$repair.inherited_entries_verified;outside_records=$outside.Count;deleted_files=0;index_sha256=$version}|ConvertTo-Json -Compress
}catch{
    if($begun-and-not$completed){$repair.state='PARTIAL_STOPPED';$repair.error=$_.Exception.Message;$repair.actual_changes_uncertain=($repair.root_requests.Count-gt$repair.verified_roots.Count);$repair.write_count_meaning='Successfully returned root writes only; a requested but unverified root may have partially changed.';$event.state=$repair.state;$event.acl_writes=$repair.direct_acl_writes;Publish}
    Write-Host '[HOLD] Preserve ACL backup and current state. No automatic retry, rollback or deletion.' -ForegroundColor Yellow
    throw
}
