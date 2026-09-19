[CmdletBinding()]
param([switch]$Execute)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

function Require { param([bool]$Condition,[string]$Code) if(-not $Condition){throw ('ROOT_INBOX_ACL:'+ $Code)} }
function PlainAclPath {
    param([string]$Path)
    Require ($Path -match '^[A-Za-z]:\\' -and $Path.Substring(2).IndexOf(':') -lt 0 -and $Path.Length -le 240) 'path-format'
    Require ([IO.Path]::GetFullPath($Path).TrimEnd('\') -ieq $Path.TrimEnd('\')) 'path-canonical'
    $node=[IO.FileInfo]::new($Path)
    while($null -ne $node){
        Require (([IO.File]::GetAttributes($node.FullName) -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'reparse-path'
        if($node -is [IO.FileInfo]){$node=$node.Directory}else{$node=$node.Parent}
    }
}
function InitializeAclGuard {
    Require (-not ('SflRootInboxGuardV1' -as [type])) 'fresh-powershell-required'
    Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Text;
using System.ComponentModel;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class SflRootInboxGuardV1 {
    [StructLayout(LayoutKind.Sequential)] struct Info {
        public uint Attr; public System.Runtime.InteropServices.ComTypes.FILETIME Created,Accessed,Written;
        public uint Volume,SizeHigh,SizeLow,Links,IndexHigh,IndexLow;
    }
    [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)]
    static extern SafeFileHandle CreateFileW(string p,uint a,uint share,IntPtr s,uint c,uint f,IntPtr t);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool GetFileInformationByHandle(SafeFileHandle h,out Info i);
    [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)]
    static extern uint GetFinalPathNameByHandleW(SafeFileHandle h,StringBuilder p,uint n,uint f);
    public static string Identity(SafeFileHandle h,string path,bool directory) {
        Info i; if(!GetFileInformationByHandle(h,out i)) throw new Win32Exception(Marshal.GetLastWin32Error());
        if((i.Attr&0x400)!=0 || ((i.Attr&0x10)!=0)!=directory || (!directory && i.Links!=1)) throw new IOException("Unsafe object type or links.");
        var b=new StringBuilder(1024); uint n=GetFinalPathNameByHandleW(h,b,1024,0);
        if(n==0 || n>=1024) throw new IOException("Handle path unavailable.");
        string actual=b.ToString(); if(actual.StartsWith(@"\\?\")) actual=actual.Substring(4);
        if(!String.Equals(actual.TrimEnd('\\'),Path.GetFullPath(path).TrimEnd('\\'),StringComparison.OrdinalIgnoreCase)) throw new IOException("Handle path changed.");
        return i.Volume.ToString("X8")+":"+i.IndexHigh.ToString("X8")+i.IndexLow.ToString("X8");
    }
    public static SafeFileHandle Open(string path,bool directory) {
        // Metadata-only access, share read/write, deny delete/rename while held.
        var h=CreateFileW(path,0,3,IntPtr.Zero,3,0x02200000,IntPtr.Zero);
        if(h.IsInvalid){h.Dispose();throw new Win32Exception(Marshal.GetLastWin32Error());}
        try{Identity(h,path,directory);return h;}catch{h.Dispose();throw;}
    }
}
'@
}
function GuardAclPath {
    param([string]$Path,[bool]$Directory,[hashtable]$Context)
    Require ($Context.clock.Elapsed.TotalSeconds -lt 120) 'metadata-time-budget'
    PlainAclPath $Path
    $parent=[IO.Directory]::GetParent($Path)
    if($null -ne $parent -and -not $Context.guards.ContainsKey($parent.FullName)){GuardAclPath $parent.FullName $true $Context}
    if(-not $Context.guards.ContainsKey($Path)){
        $handle=[SflRootInboxGuardV1]::Open($Path,$Directory)
        $Context.guards[$Path]=[pscustomobject]@{handle=$handle;id=[SflRootInboxGuardV1]::Identity($handle,$Path,$Directory)}
    }
    Require ([SflRootInboxGuardV1]::Identity($Context.guards[$Path].handle,$Path,$Directory) -ceq $Context.guards[$Path].id) 'object-identity-changed'
}
function AclFacts {
    param([string]$Path)
    PlainAclPath $Path
    $dir=[IO.Directory]::Exists($Path)
    $sections=[Security.AccessControl.AccessControlSections]'Access,Owner,Group'
    $acl=if($dir){[IO.Directory]::GetAccessControl($Path,$sections)}else{[IO.File]::GetAccessControl($Path,$sections)}
    $raw=[Security.AccessControl.RawSecurityDescriptor]::new($acl.GetSecurityDescriptorBinaryForm(),0)
    [pscustomobject]@{path=$Path;directory=$dir;acl=$acl;sddl=$acl.GetSecurityDescriptorSddlForm($sections);
        owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value;protected=$acl.AreAccessRulesProtected;
        canonical=$acl.AreAccessRulesCanonical;raw_count=$(if($null -eq $raw.DiscretionaryAcl){-1}else{$raw.DiscretionaryAcl.Count});
        rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))}
}
function AssertAclShape {
    param([object]$Facts,[string]$Owner,[string[]]$Sids,[bool]$Protected,[bool]$Inherited)
    Require ($Facts.directory -and $Facts.owner -ceq $Owner -and $Facts.protected -eq $Protected -and $Facts.canonical -and $Facts.raw_count -eq $Sids.Count -and $Facts.rules.Count -eq $Sids.Count) 'acl-shape'
    $seen=@{}
    foreach($rule in $Facts.rules){
        $sid=$rule.IdentityReference.Value
        Require ($sid -cin $Sids -and -not $seen.ContainsKey($sid) -and $rule.AccessControlType -eq 'Allow' -and [int]$rule.FileSystemRights -eq 2032127 -and $rule.IsInherited -eq $Inherited -and [int]$rule.InheritanceFlags -eq 3 -and [int]$rule.PropagationFlags -eq 0) 'acl-rule'
        $seen[$sid]=$true
    }
}
function AssertDescriptor {
    param([string]$Expected,[string]$Actual)
    $a=[Security.AccessControl.RawSecurityDescriptor]::new($Expected)
    $b=[Security.AccessControl.RawSecurityDescriptor]::new($Actual)
    $flagsA=[int]$a.ControlFlags;$flagsB=[int]$b.ControlFlags
    Require ($flagsB -eq $flagsA -or $flagsB -eq ($flagsA -bor 1024)) 'descriptor-flags'
    $a.SetFlags([Security.AccessControl.ControlFlags]($flagsA -bor 1024))
    $b.SetFlags([Security.AccessControl.ControlFlags]($flagsB -bor 1024))
    $sections=[Security.AccessControl.AccessControlSections]'Access,Owner,Group'
    Require ($a.GetSddlForm($sections) -ceq $b.GetSddlForm($sections)) 'descriptor-changed'
}
function SnapshotAclBoundary {
    param([string]$Root,[hashtable]$Context)
    $paths=[Collections.Generic.List[string]]::new();$paths.Add($Root)
    $children=@([IO.Directory]::EnumerateFileSystemEntries($Root)|Select-Object -First 6)
    Require ($children.Count -eq 5) 'root-child-count'
    $wanted=@('backups','inbox','inventory','runs','tmp');$seen=@{}
    foreach($path in $children){
        $name=[IO.Path]::GetFileName($path)
        Require ($name -cin $wanted -and -not $seen.ContainsKey($name) -and [IO.Directory]::Exists($path)) 'root-child-set'
        $seen[$name]=$true;$paths.Add($path)
    }
    $queue=[Collections.Generic.Queue[object]]::new();$queue.Enqueue(@(($Root+'\inbox'),0))
    while($queue.Count -gt 0){
        $entry=$queue.Dequeue();$parent=[string]$entry[0];$depth=[int]$entry[1]
        GuardAclPath $parent $true $Context
        foreach($path in [IO.Directory]::EnumerateFileSystemEntries($parent)){
            Require ($paths.Count -lt 5006 -and $depth -lt 32) 'inbox-inventory-budget'
            Require ($path.StartsWith($Root+'\inbox\',[StringComparison]::OrdinalIgnoreCase)) 'inbox-boundary'
            $dir=[IO.Directory]::Exists($path);GuardAclPath $path $dir $Context
            $paths.Add($path);if($dir){$queue.Enqueue(@($path,($depth+1)))}
        }
    }
    $snapshot=@{}
    foreach($path in $paths){
        $facts=AclFacts $path;GuardAclPath $path $facts.directory $Context
        if([IO.Path]::GetDirectoryName($path) -ieq $Root -and $path -ine ($Root+'\inbox')){Require $facts.protected 'other-child-not-protected'}
        $snapshot[$path]=[pscustomobject]@{path=$path;directory=$facts.directory;identity=$Context.guards[$path].id;sddl=$facts.sddl}
    }
    return ,$snapshot
}
function AssertSnapshot {
    param([hashtable]$Expected,[hashtable]$Actual)
    Require ($Expected.Count -eq $Actual.Count) 'boundary-count-changed'
    foreach($path in $Expected.Keys){
        Require ($Actual.ContainsKey($path) -and $Expected[$path].identity -ceq $Actual[$path].identity -and $Expected[$path].directory -eq $Actual[$path].directory) 'boundary-membership-changed'
        AssertDescriptor $Expected[$path].sddl $Actual[$path].sddl
    }
}
function HashAclStream {
    param([IO.Stream]$Stream)
    $sha=[Security.Cryptography.SHA256]::Create()
    try{$Stream.Position=0;[BitConverter]::ToString($sha.ComputeHash($Stream)).Replace('-','')}finally{$sha.Dispose()}
}
function WriteAclRecord {
    param([IO.FileStream]$Stream,[object]$Record)
    $bytes=[Text.UTF8Encoding]::new($false).GetBytes(($Record|ConvertTo-Json -Depth 12 -Compress)+"`n")
    $Stream.Write($bytes,0,$bytes.Length);$Stream.Flush($true)
}
function WriteAclNew {
    param([string]$Path,[byte[]]$Bytes)
    $s=[IO.File]::Open($Path,'CreateNew','Write','None')
    try{$s.Write($Bytes,0,$Bytes.Length);$s.Flush($true)}finally{$s.Dispose()}
}
function SaveAclDirectory {
    param([string]$Path,[Security.AccessControl.DirectorySecurity]$Acl)
    [IO.Directory]::SetAccessControl($Path,$Acl)
}
function ProtectInboxAclInMemory {
    param([Security.AccessControl.DirectorySecurity]$Acl)
    # Copy the already validated inherited rules into explicit rules IN MEMORY.
    # No empty/intermediate DACL is ever persisted. Keep owner/group untouched.
    $rules=@($Acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    $Acl.SetAccessRuleProtection($true,$false)
    foreach($r in $rules){
        $Acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($r.IdentityReference,$r.FileSystemRights,$r.InheritanceFlags,$r.PropagationFlags,$r.AccessControlType))
    }
}
function InvokeRootInboxPlan {
    param([string]$Root,[string]$AdminSid,[string]$OperatorSid,[hashtable]$Expected,[hashtable]$Context,[IO.FileStream]$Journal,[IO.Stream]$Backup,[string]$BackupHash,[Collections.Generic.List[string]]$Attempted,[Collections.Generic.List[string]]$Returned)
    $sections=[Security.AccessControl.AccessControlSections]'Access,Owner,Group'
    foreach($path in @(($Root+'\inbox'),$Root)){
        Require ((HashAclStream $Backup) -ceq $BackupHash) 'backup-changed'
        AssertSnapshot $Expected (SnapshotAclBoundary $Root $Context)
        $facts=AclFacts $path
        if($path -ceq ($Root+'\inbox')){
            AssertAclShape $facts $OperatorSid @('S-1-5-18',$AdminSid,$OperatorSid) $false $true
            ProtectInboxAclInMemory $facts.acl
            $action='PRESERVE_INBOX_RULES_AND_PROTECT'
        }else{
            AssertAclShape $facts $AdminSid @('S-1-5-18',$AdminSid,$OperatorSid) $true $false
            AssertAclShape (AclFacts ($Root+'\inbox')) $OperatorSid @('S-1-5-18',$AdminSid,$OperatorSid) $true $false
            $remove=@($facts.acl.GetAccessRules($true,$false,[Security.Principal.SecurityIdentifier])|Where-Object {$_.IdentityReference.Value -ceq $OperatorSid})
            Require ($remove.Count -eq 1) 'root-extra-rule-count'
            $facts.acl.RemoveAccessRuleSpecific($remove[0]);$action='REMOVE_ROOT_OPERATOR_RULE_ONLY'
        }
        $planned=$facts.acl.GetSecurityDescriptorSddlForm($sections)
        WriteAclRecord $Journal ([ordered]@{event='INTENT';at=[DateTimeOffset]::Now.ToString('o');path=$path;action=$action;before_sddl=$Expected[$path].sddl;planned_sddl=$planned})
        AssertSnapshot $Expected (SnapshotAclBoundary $Root $Context)
        Require ((HashAclStream $Backup) -ceq $BackupHash) 'backup-changed-before-write'
        $Attempted.Add($path)
        SaveAclDirectory $path $facts.acl
        $Returned.Add($path)
        $after=AclFacts $path
        AssertDescriptor $planned $after.sddl
        if($path -ceq ($Root+'\inbox')){AssertAclShape $after $OperatorSid @('S-1-5-18',$AdminSid,$OperatorSid) $true $false}
        else{AssertAclShape $after $AdminSid @('S-1-5-18',$AdminSid) $true $false}
        $Expected[$path].sddl=$after.sddl
        AssertSnapshot $Expected (SnapshotAclBoundary $Root $Context)
        WriteAclRecord $Journal ([ordered]@{event='VERIFIED';at=[DateTimeOffset]::Now.ToString('o');path=$path;after_sddl=$after.sddl})
    }
}

# Server entry point. Tests import function ASTs only; this section is never run locally.
$root='C:\ProgramData\SFLOps'
$adminSid='S-1-5-32-544'
$operatorSid='S-1-5-21-2762931165-1280404403-2847611662-1001'
$context=@{guards=@{};clock=[Diagnostics.Stopwatch]::StartNew()}
$attempted=[Collections.Generic.List[string]]::new();$returned=[Collections.Generic.List[string]]::new()
$journal=$null;$backup=$null;$out=$null;$phase='host-check'
$priorPath=$env:PATH;$priorModules=$env:PSModulePath
try{
    $native=[IO.Path]::Combine([Environment]::SystemDirectory,'WindowsPowerShell\v1.0\powershell.exe')
    $id=[Security.Principal.WindowsIdentity]::GetCurrent();$principal=[Security.Principal.WindowsPrincipal]::new($id)
    Require ([Environment]::Is64BitProcess -and $PSVersionTable.PSEdition -ceq 'Desktop' -and $PSVersionTable.PSVersion.ToString() -like '5.1.*' -and [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName -ieq $native -and $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) 'native-admin-ps51'
    Require ($id.User.Value -ceq $operatorSid) 'server-operator'
    Require ([IO.DriveInfo]::new('C:\').DriveFormat -ceq 'NTFS') 'ntfs-required'
    $env:PATH=[Environment]::SystemDirectory+';'+[IO.Path]::GetDirectoryName($native)
    $env:PSModulePath=[IO.Path]::GetDirectoryName($native)+'\Modules'
    InitializeAclGuard
    $phase='preflight';Write-Host '[1/5] Recheck exact root/inbox ACLs and inbox metadata. No app/API calls.'
    $expected=SnapshotAclBoundary $root $context
    AssertAclShape (AclFacts $root) $adminSid @('S-1-5-18',$adminSid,$operatorSid) $true $false
    AssertAclShape (AclFacts ($root+'\inbox')) $operatorSid @('S-1-5-18',$adminSid,$operatorSid) $false $true
    AssertAclShape (AclFacts ($root+'\tmp')) $adminSid @('S-1-5-18',$adminSid) $true $false
    if(-not $Execute){Write-Host '[PLAN ONLY] Exact two-folder plan validated; no target ACL changes.';return}
    $phase='backup';Write-Host '[2/5] Save original Owner/Group/DACL records before changing either target.'
    $out=$root+'\tmp\root-inbox-acl-'+[Guid]::NewGuid().ToString('N')
    Require (-not [IO.File]::Exists($out) -and -not [IO.Directory]::Exists($out)) 'output-exists'
    $private=[Security.AccessControl.DirectorySecurity]::new();$private.SetAccessRuleProtection($true,$false)
    $private.SetOwner([Security.Principal.SecurityIdentifier]::new($adminSid))
    foreach($sid in @('S-1-5-18',$adminSid)){$private.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($sid),'FullControl','ContainerInherit,ObjectInherit','None','Allow'))}
    [void][IO.Directory]::CreateDirectory($out,$private)
    GuardAclPath $out $true $context;AssertAclShape (AclFacts $out) $adminSid @('S-1-5-18',$adminSid) $true $false
    $bytes=[Text.UTF8Encoding]::new($false).GetBytes(([ordered]@{schema='root-inbox-acl-backup-v1';at=[DateTimeOffset]::Now.ToString('o');authorization='USER_APPROVED_INBOX_PRESERVATION_THEN_ROOT_OPERATOR_ACE_REMOVAL';targets=@(($root+'\inbox'),$root);records=@($expected.Values|Sort-Object path);scope='Owner,Group,DACL; no file contents or SACL'}|ConvertTo-Json -Depth 8))
    $backupPath=$out+'\before-acl.json';WriteAclNew $backupPath $bytes
    $backup=[IO.File]::Open($backupPath,'Open','Read','Read');$backupHash=HashAclStream $backup
    $memory=[IO.MemoryStream]::new($bytes,$false)
    try{Require ($backupHash -ceq (HashAclStream $memory)) 'backup-readback'}finally{$memory.Dispose()}
    WriteAclNew ($backupPath+'.sha256.txt') ([Text.Encoding]::ASCII.GetBytes($backupHash+"`n"))
    Write-Host ('[BACKUP] '+$backupPath);Write-Host ('[SHA256] '+$backupHash)
    $journal=[IO.File]::Open(($out+'\journal.jsonl'),'CreateNew','Write','Read')
    WriteAclRecord $journal ([ordered]@{event='PLAN';backup_sha256=$backupHash;boundary_count=$expected.Count})
    $phase='two-acl-writes';Write-Host '[3/5] Protect inbox preserving all three rules, then remove only the root operator rule.'
    InvokeRootInboxPlan $root $adminSid $operatorSid $expected $context $journal $backup $backupHash $attempted $returned
    $phase='final-verification';Write-Host '[4/5] Verify target ACLs and unchanged inbox descendants/protected children.'
    Require ($attempted.Count -eq 2 -and $returned.Count -eq 2) 'write-count'
    AssertSnapshot $expected (SnapshotAclBoundary $root $context)
    Require ((HashAclStream $backup) -ceq $backupHash) 'final-backup-hash'
    $result=[ordered]@{result='SFLOPS_ROOT_INBOX_ACL_REPAIR_PASS';at=[DateTimeOffset]::Now.ToString('o');acl_writes=2;inbox_rules_preserved=$true;root_operator_rule_removed=$true;boundary_records=$expected.Count;backup_sha256=$backupHash;receipt_directory=$out;app_operations=0;files_deleted=0;automatic_rollback=$false;installed_tree_check_started=$false}
    WriteAclRecord $journal ([ordered]@{event='COMPLETE';summary=$result})
    WriteAclNew ($out+'\result.json') ([Text.UTF8Encoding]::new($false).GetBytes(($result|ConvertTo-Json -Depth 5)))
    Write-Host '[5/5] COMPLETE. Keep evidence. Return the short summary; do not rerun automatically.'
    $result|ConvertTo-Json -Depth 5
}catch{
    $reason='unexpected-error';if($_.Exception.Message -cmatch '^ROOT_INBOX_ACL:([a-z0-9-]+)$'){$reason=$Matches[1]}
    if($null -ne $journal){try{WriteAclRecord $journal ([ordered]@{event='HOLD';phase=$phase;reason=$reason;attempted=$attempted.ToArray();returned=$returned.ToArray();automatic_rollback=$false})}catch{Write-Host '[WARNING] HOLD journal unavailable; keep earlier intents.'}}
    Write-Host ('[HOLD] phase='+$phase+' reason='+$reason+' attempted='+$attempted.Count+' returned='+$returned.Count)
    if($null -ne $out){Write-Host ('[PRESERVE] '+$out)}
    throw 'ROOT_INBOX_ACL_HOLD: Preserve output. No automatic retry, cleanup, rollback, app restart or installation.'
}finally{
    if($null -ne $journal){$journal.Dispose()};if($null -ne $backup){$backup.Dispose()}
    foreach($guard in $context.guards.Values){$guard.handle.Dispose()}
    $env:PATH=$priorPath;$env:PSModulePath=$priorModules
}
