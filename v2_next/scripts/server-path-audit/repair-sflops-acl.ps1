[CmdletBinding()]
param([switch]$Execute)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

function Get-RepairAclFacts {
    param([string]$Path)
    Assert-QPlain $Path
    $directory=[IO.Directory]::Exists($Path)
    $sections=[Security.AccessControl.AccessControlSections]'Access,Owner,Group'
    $acl=if($directory){[IO.Directory]::GetAccessControl($Path,$sections)}else{[IO.File]::GetAccessControl($Path,$sections)}
    $rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    $raw=[Security.AccessControl.RawSecurityDescriptor]::new($acl.GetSecurityDescriptorBinaryForm(),0)
    return [pscustomobject]@{path=$Path;directory=$directory;acl=$acl;
        sddl=$acl.GetSecurityDescriptorSddlForm($sections);owner_sid=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value;
        group_sid=$acl.GetGroup([Security.Principal.SecurityIdentifier]).Value;protected=$acl.AreAccessRulesProtected;
        canonical=$acl.AreAccessRulesCanonical;raw_ace_count=$(if($null -eq $raw.DiscretionaryAcl){-1}else{$raw.DiscretionaryAcl.Count});
        rules=@($rules|ForEach-Object {[pscustomobject]@{sid=$_.IdentityReference.Value;type=[string]$_.AccessControlType;
            rights=[int]$_.FileSystemRights;inherited=$_.IsInherited;inheritance=[int]$_.InheritanceFlags;propagation=[int]$_.PropagationFlags}})}
}

function ConvertTo-RepairRecord {
    param([object]$Facts)
    return [pscustomobject]@{path=$Facts.path;directory=$Facts.directory;sddl=$Facts.sddl;owner_sid=$Facts.owner_sid;
        group_sid=$Facts.group_sid;protected=$Facts.protected;canonical=$Facts.canonical;raw_ace_count=$Facts.raw_ace_count;rules=$Facts.rules}
}

function Assert-RepairAclShape {
    param([object]$Facts,[string]$ExtraSid,[switch]$IncludeExtra)
    $allowed=@('S-1-5-18','S-1-5-32-544');if($IncludeExtra){$allowed+=,$ExtraSid}
    if(-not $Facts.directory -or $Facts.owner_sid -cne 'S-1-5-32-544' -or -not $Facts.protected -or
        -not $Facts.canonical -or $Facts.rules.Count -ne $allowed.Count -or $Facts.raw_ace_count -ne $allowed.Count){throw ('ACL shape differs: '+$Facts.path)}
    $seen=@{}
    foreach($rule in $Facts.rules){
        if($rule.sid -cnotin $allowed -or $seen.ContainsKey($rule.sid) -or $rule.type -cne 'Allow' -or
            $rule.rights -ne 2032127 -or $rule.inherited -or $rule.inheritance -ne 3 -or $rule.propagation -ne 0){throw ('Unexpected ACL rule: '+$Facts.path)}
        $seen[$rule.sid]=$true
    }
}

function Get-RepairBoundary {
    param([string[]]$Targets,[hashtable]$Guards,[Collections.Generic.List[IDisposable]]$Pins,[hashtable]$FileIds)
    $result=@{}
    foreach($target in $Targets){
        Assert-QPlain $target
        $children=@([IO.Directory]::GetFileSystemEntries($target))
        if($children.Count -gt 200){throw ('Too many direct children: '+$target)}
        foreach($path in $children){
            Assert-QPlain $path
            $directory=[IO.Directory]::Exists($path)
            if($directory){Open-CleanupDirectoryGuard $path $Guards;$id=[SflCleanupNativeV1]::Identity($Guards[$path].handle,$path,$true)}
            else{
                if(-not $FileIds.ContainsKey($path)){
                    $s=[SflCleanupNativeV1]::OpenFile($path,$false);$Pins.Add($s)
                    $FileIds[$path]=[pscustomobject]@{stream=$s;id=[SflCleanupNativeV1]::Identity($s.SafeFileHandle,$path,$false)}
                }
                $id=[SflCleanupNativeV1]::Identity($FileIds[$path].stream.SafeFileHandle,$path,$false)
                if($id -cne $FileIds[$path].id){throw 'Child file identity changed.'}
            }
            $facts=Get-RepairAclFacts $path
            if($facts.directory -ne $directory -or -not $facts.protected){throw ('Unprotected/changed child would be affected; no ACL repair: '+$path)}
            $result[$path]=[pscustomobject]@{path=$path;identity=$id;acl=(ConvertTo-RepairRecord $facts)}
        }
    }
    return ,$result
}

function Assert-RepairBoundarySame {
    param([hashtable]$Expected,[hashtable]$Actual)
    if($Actual.Count -ne $Expected.Count){throw 'Direct child inventory changed.'}
    foreach($path in $Expected.Keys){
        if(-not $Actual.ContainsKey($path) -or $Actual[$path].identity -cne $Expected[$path].identity -or
            $Actual[$path].acl.sddl -cne $Expected[$path].acl.sddl -or $Actual[$path].acl.directory -ne $Expected[$path].acl.directory){throw ('Child identity/ACL changed: '+$path)}
    }
}

function Assert-RepairTargetsSame {
    param([string[]]$Targets,[hashtable]$Expected,[hashtable]$Guards)
    foreach($path in $Targets){
        $now=Get-RepairAclFacts $path
        if($now.sddl -cne $Expected[$path].sddl){throw ('Target ACL changed since recorded state: '+$path)}
        if([SflCleanupNativeV1]::Identity($Guards[$path].handle,$path,$true) -cne $Guards[$path].identity){throw 'Target identity changed.'}
    }
}

function Assert-RepairPersistedDescriptor {
    param([string]$Expected,[string]$Actual)
    # Windows may set SE_DACL_AUTO_INHERITED when persisting a protected DACL.
    # Accept ONLY that documented 0->1 flag transition, not any ACE/owner/group change.
    $a=[Security.AccessControl.RawSecurityDescriptor]::new($Expected)
    $b=[Security.AccessControl.RawSecurityDescriptor]::new($Actual)
    $flagsA=[int]$a.ControlFlags;$flagsB=[int]$b.ControlFlags
    if($flagsB -ne $flagsA -and $flagsB -ne ($flagsA -bor 1024)){throw 'Unexpected descriptor control flag change.'}
    $a.SetFlags([Security.AccessControl.ControlFlags]($flagsA -bor 1024))
    $b.SetFlags([Security.AccessControl.ControlFlags]($flagsB -bor 1024))
    $sections=[Security.AccessControl.AccessControlSections]'Access,Owner,Group'
    if($a.GetSddlForm($sections) -cne $b.GetSddlForm($sections)){throw 'Persisted descriptor differs beyond Windows auto-inherited flag.'}
}

function Write-RepairDirectoryAcl {
    param([string]$Path,[Security.AccessControl.DirectorySecurity]$Acl)
    [IO.Directory]::SetAccessControl($Path,$Acl)
}

function Invoke-RepairAclPlan {
    param([string[]]$Targets,[string]$ExtraSid,[hashtable]$Expected,[hashtable]$Boundary,
        [hashtable]$Guards,[Collections.Generic.List[IDisposable]]$Pins,[hashtable]$FileIds,[IO.FileStream]$Journal,
        [Collections.Generic.List[string]]$Attempted,[Collections.Generic.List[string]]$Confirmed)
    foreach($path in $Targets){
        Assert-RepairTargetsSame $Targets $Expected $Guards
        Assert-RepairBoundarySame $Boundary (Get-RepairBoundary $Targets $Guards $Pins $FileIds)
        $before=Get-RepairAclFacts $path;Assert-RepairAclShape $before $ExtraSid -IncludeExtra
        if($before.sddl -cne $Expected[$path].sddl){throw 'Target changed immediately before repair.'}
        $acl=$before.acl
        $remove=@($acl.GetAccessRules($true,$false,[Security.Principal.SecurityIdentifier])|Where-Object {$_.IdentityReference.Value -ceq $ExtraSid})
        if($remove.Count -ne 1){throw 'Expected exactly one explicit extra rule.'}
        # Change only this DACL rule; no owner, group, SACL or inheritance rewrite.
        $acl.RemoveAccessRuleSpecific($remove[0])
        $afterSddl=$acl.GetSecurityDescriptorSddlForm([Security.AccessControl.AccessControlSections]'Access,Owner,Group')
        Write-CleanupRecord $Journal ([pscustomobject]@{event='ACL_CHANGE_INTENT';at=[DateTimeOffset]::Now.ToString('o');
            path=$path;before_sddl=$before.sddl;expected_after_sddl=$afterSddl;removed_sid=$ExtraSid;
            descriptor_policy='exact-removal-allow-only-dacl-auto-inherited-flag-addition'})
        Assert-RepairTargetsSame $Targets $Expected $Guards
        Assert-RepairBoundarySame $Boundary (Get-RepairBoundary $Targets $Guards $Pins $FileIds)
        $Attempted.Add($path)
        Write-RepairDirectoryAcl $path $acl
        # Count the returned write BEFORE post-read or journal operations that can fail.
        $Confirmed.Add($path)
        $after=Get-RepairAclFacts $path;Assert-RepairAclShape $after $ExtraSid
        Assert-RepairPersistedDescriptor $afterSddl $after.sddl
        if($after.owner_sid -cne $before.owner_sid -or $after.group_sid -cne $before.group_sid){throw 'Owner/group changed.'}
        $Expected[$path]=ConvertTo-RepairRecord $after
        if($Boundary.ContainsKey($path)){$Boundary[$path].acl=ConvertTo-RepairRecord $after}
        Assert-RepairTargetsSame $Targets $Expected $Guards
        Assert-RepairBoundarySame $Boundary (Get-RepairBoundary $Targets $Guards $Pins $FileIds)
        Write-CleanupRecord $Journal ([pscustomobject]@{event='ACL_CHANGE_VERIFIED';at=[DateTimeOffset]::Now.ToString('o');path=$path;after_sddl=$after.sddl})
        Write-Host ('[ACL VERIFIED] '+$path)
    }
}

$native=[IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
$principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if(-not [Environment]::Is64BitProcess -or $PSVersionTable.PSEdition -cne 'Desktop' -or
    $PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1 -or
    [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName -ine $native -or
    -not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Use native administrator x64 Windows PowerShell 5.1.'}
$savedAclPath=$env:PATH;$savedAclModules=$env:PSModulePath
$pins=[Collections.Generic.List[IDisposable]]::new();$guards=@{};$fileIds=@{};$archive=$null;$journal=$null;$output=''
$attempted=[Collections.Generic.List[string]]::new();$confirmed=[Collections.Generic.List[string]]::new()
$root='C:\ProgramData\SFLOps';$tmp=$root+'\tmp'
$targets=@(($root+'\inventory'),$root)
$extraSid='S-1-5-21-2762931165-1280404403-2847611662-1001'
try{
    $env:PATH=[Environment]::SystemDirectory+';'+[IO.Path]::GetDirectoryName($native)
    $env:PSModulePath=[IO.Path]::GetDirectoryName($native)+'\Modules'
    Write-Host '[1/5] Verify previously transferred ZIP; load pinned functions only. No cleanup or installer execution.'
    $zipPath='C:\Users\user\Desktop\SmartFactory\v1019-release-pair-cleanup-ready-r1.zip'
    $zip=[IO.File]::Open($zipPath,'Open','Read','Read');$pins.Add($zip)
    $sha=[Security.Cryptography.SHA256]::Create();try{$hash=[BitConverter]::ToString($sha.ComputeHash($zip)).Replace('-','')}finally{$sha.Dispose()}
    if($zip.Length -ne 22604 -or $hash -cne '62CCE5F9B9E020FE859ABEA2977EAF366A0945C5C402B2839632C00A952065F3'){throw 'Existing ZIP hash/length differs.'}
    Add-Type -AssemblyName System.IO.Compression
    $zip.Position=0;$archive=[IO.Compression.ZipArchive]::new($zip,'Read',$true)
    if($archive.Entries.Count -ne 4){throw 'Existing ZIP entry count differs.'}
    foreach($spec in @(@('read-quarantine-pre-v1020.ps1',24114,'EBEB041A42D0FC2232ADCDDA13547C8151209C22E8D85F1B1B1D70D7021A1765'),
        @('cleanup-archive-core.ps1',14130,'CD9F2387581C52FA9A26EC6E217909919F472CB5DF9853C2E96A2A368FF40A28'))){
        $entry=@($archive.Entries|Where-Object FullName -CEQ $spec[0])
        if($entry.Count -ne 1 -or $entry[0].Length -ne $spec[1]){throw 'Dependency entry mismatch.'}
        $source=$entry[0].Open();$buffer=[IO.MemoryStream]::new()
        try{
            $chunk=New-Object byte[] 8192
            while(($read=$source.Read($chunk,0,$chunk.Length)) -gt 0){if($buffer.Length+$read -gt $spec[1]){throw 'Dependency expansion limit.'};$buffer.Write($chunk,0,$read)}
            $sha=[Security.Cryptography.SHA256]::Create();try{$hash=[BitConverter]::ToString($sha.ComputeHash($buffer.ToArray())).Replace('-','')}finally{$sha.Dispose()}
            if($buffer.Length -ne $spec[1] -or $hash -cne $spec[2]){throw 'Dependency hash mismatch.'}
            $code=[Text.UTF8Encoding]::new($false,$true).GetString($buffer.ToArray())
            $t=$null;$e=$null;$ast=[Management.Automation.Language.Parser]::ParseInput($code,[ref]$t,[ref]$e)
            if(@($e).Count -ne 0){throw 'Dependency parse failed.'}
            foreach($fn in $ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst]},$true)){. ([scriptblock]::Create($fn.Extent.Text))}
        }finally{$source.Dispose();$buffer.Dispose()}
    }
    Initialize-CleanupNative
    Assert-QPlain $zipPath
    if([IO.DriveInfo]::new('C:\').DriveFormat -cne 'NTFS'){throw 'Local NTFS required.'}
    Write-Host '[2/5] Check exact two changed ACLs and protected child boundaries. No recursive ACL reset.'
    foreach($path in @($root,$tmp,($root+'\inventory'))){Open-CleanupDirectoryGuard $path $guards}
    $expected=@{};foreach($path in $targets){$facts=Get-RepairAclFacts $path;Assert-RepairAclShape $facts $extraSid -IncludeExtra;$expected[$path]=ConvertTo-RepairRecord $facts}
    Assert-RepairAclShape (Get-RepairAclFacts $tmp) $extraSid
    $boundary=Get-RepairBoundary $targets $guards $pins $fileIds
    if(-not $Execute){[pscustomobject]@{result='SFLOPS_ACL_REPAIR_PLAN_ONLY';targets=@($expected.Values);protected_direct_children=$boundary.Count;acl_changes_made=$false}|ConvertTo-Json -Depth 8;return}
    Write-Host '[3/5] Save and read-lock original Owner/Group/DACL records under protected tmp before any ACL change.'
    $output=$tmp+'\acl-repair-'+[Guid]::NewGuid().ToString('N')
    if([IO.Directory]::Exists($output) -or [IO.File]::Exists($output)){throw 'New receipt path collision.'}
    New-CleanupPrivateDirectory $output;Open-CleanupDirectoryGuard $output $guards
    $before=[pscustomobject]@{schema_version='sflops-exact-two-acl-repair-v1';created_at=[DateTimeOffset]::Now.ToString('o');
        targets=@($expected.Values);boundary=@($boundary.Values);removed_sid=$extraSid;authorization='USER_APPROVED_EXACT_TWO_FOLDER_EXTRA_ACE_REMOVAL';
        backup_scope='Owner,Group,DACL only; SACL not read or changed';
        limitation='No recursive reset, content deletion, cleanup retry, application operation, or automatic rollback. Existing open handles are not revoked.'}
    $backupPath=$output+'\before-acl.json';$bytes=[Text.UTF8Encoding]::new($false).GetBytes(($before|ConvertTo-Json -Depth 10))
    $s=[IO.File]::Open($backupPath,'CreateNew','Write','Read');try{$s.Write($bytes,0,$bytes.Length);$s.Flush($true)}finally{$s.Dispose()}
    $backup=[IO.File]::Open($backupPath,'Open','Read','Read');$pins.Add($backup);$backupHash=Get-QHash $backup
    $sha=[Security.Cryptography.SHA256]::Create();try{$intended=[BitConverter]::ToString($sha.ComputeHash($bytes)).Replace('-','')}finally{$sha.Dispose()}
    if($backupHash -cne $intended){throw 'ACL backup readback mismatch.'}
    $s=[IO.File]::Open(($backupPath+'.sha256.txt'),'CreateNew','Write','Read');try{$bytes=[Text.Encoding]::ASCII.GetBytes($backupHash+"`n");$s.Write($bytes,0,$bytes.Length);$s.Flush($true)}finally{$s.Dispose()}
    Write-Host ('[BACKUP] '+$backupPath);Write-Host ('[BACKUP SHA256] '+$backupHash)
    $journal=[IO.File]::Open(($output+'\acl-repair.jsonl'),'CreateNew','Write','Read')
    Write-CleanupRecord $journal ([pscustomobject]@{event='PLAN';at=[DateTimeOffset]::Now.ToString('o');backup_sha256=$backupHash;targets=$targets;removed_sid=$extraSid})
    Write-Host '[4/5] Remove only the one reviewed extra Allow ACE from inventory, then SFLOps. Keep administrator/SYSTEM entries.'
    Invoke-RepairAclPlan $targets $extraSid $expected $boundary $guards $pins $fileIds $journal $attempted $confirmed
    Write-Host '[5/5] Verify exact resulting ACLs, unchanged child boundaries and original backup bytes. Do not restart cleanup.'
    foreach($path in @($root,($root+'\inventory'),$tmp)){Assert-RepairAclShape (Get-RepairAclFacts $path) $extraSid}
    Assert-RepairTargetsSame $targets $expected $guards
    Assert-RepairBoundarySame $boundary (Get-RepairBoundary $targets $guards $pins $fileIds)
    if($confirmed.Count -ne 2 -or $attempted.Count -ne 2){throw 'Unexpected ACL change count.'}
    if((Get-QHash $backup) -cne $backupHash){throw 'Original ACL backup changed.'}
    $result=[pscustomobject]@{event='COMPLETE';result='SFLOPS_EXACT_TWO_FOLDER_ACL_REPAIR_PASS';at=[DateTimeOffset]::Now.ToString('o');
        acl_write_returned_success=$confirmed.Count;verified_targets=$targets;protected_child_boundary_count=$boundary.Count;backup_path=$backupPath;backup_sha256=$backupHash;
        receipt_directory=$output;recursive_acl_reset_performed=$false;original_files_deleted=0;cleanup_retried=$false;app_restart_performed=$false;
        limitation='Only future ACL access checks changed. Existing opened handles are not revoked. This is not an evidence-integrity re-audit.'}
    Write-CleanupRecord $journal $result;$journal.Dispose();$journal=$null
    $s=[IO.File]::Open(($output+'\acl-repair.jsonl'),'Open','Read','Read');try{Write-Host ('[JOURNAL SHA256] '+(Get-QHash $s))}finally{$s.Dispose()}
    $result|ConvertTo-Json -Depth 6
}catch{
    if($null -ne $journal){try{Write-CleanupRecord $journal ([pscustomobject]@{event='HOLD';at=[DateTimeOffset]::Now.ToString('o');
        attempted_paths=$attempted.ToArray();write_returned_success_paths=$confirmed.ToArray();automatic_rollback_performed=$false})}catch{Write-Host '[WARNING] HOLD journal write failed; preserve prior intents.'}}
    Write-Host ('[HOLD] No retry/rollback/deletion. ACL writes attempted='+$attempted.Count+' returned_success='+$confirmed.Count+' receipt='+$output)
    throw
}finally{
    if($null -ne $journal){$journal.Dispose()};if($null -ne $archive){$archive.Dispose()}
    foreach($s in $pins){$s.Dispose()};foreach($g in $guards.Values){$g.handle.Dispose()}
    $env:PATH=$savedAclPath;$env:PSModulePath=$savedAclModules
}
