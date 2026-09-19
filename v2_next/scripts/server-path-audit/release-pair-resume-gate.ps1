# Function-only gate inserted into the hash-verified existing release-pair launcher.
# No deletion, ACL mutation, process launch or source writes in this file.
function Assert-ResumeAclRecords {
    param([object[]]$Events,[object]$Backup,[string[]]$Targets,[string]$BackupHash)
    if($Events.Count -ne 6){throw 'ACL journal event count differs.'}
    $order=@('PLAN','ACL_CHANGE_INTENT','ACL_CHANGE_VERIFIED','ACL_CHANGE_INTENT','ACL_CHANGE_VERIFIED','COMPLETE')
    for($i=0;$i -lt 6;$i++){if($Events[$i].event -cne $order[$i]){throw 'ACL journal is not complete.'}}
    if($Events[0].backup_sha256 -cne $BackupHash -or $Events[5].backup_sha256 -cne $BackupHash -or
        $Events[5].result -cne 'SFLOPS_EXACT_TWO_FOLDER_ACL_REPAIR_PASS' -or $Events[5].acl_write_returned_success -ne 2 -or
        $Events[5].original_files_deleted -ne 0 -or $Events[5].cleanup_retried -ne $false -or
        $Events[5].recursive_acl_reset_performed -ne $false -or $Events[5].app_restart_performed -ne $false -or
        $Backup.schema_version -cne 'sflops-exact-two-acl-repair-v1' -or $Backup.targets.Count -ne 2){throw 'ACL completion binding differs.'}
    $expected=@{}
    for($i=0;$i -lt 2;$i++){
        $path=$Targets[$i];$intent=$Events[1+2*$i];$verified=$Events[2+2*$i]
        if($intent.path -cne $path -or $verified.path -cne $path){throw 'ACL repaired target order differs.'}
        $before=@($Backup.targets|Where-Object path -CEQ $path)
        if($before.Count -ne 1 -or $intent.before_sddl -cne $before[0].sddl -or [string]::IsNullOrWhiteSpace($verified.after_sddl)){throw 'ACL backup/intent mismatch.'}
        $expected[$path]=$verified.after_sddl
    }
    return ,$expected
}

function Get-ResumePrivateSddl {
    param([string]$Path)
    Assert-QPlain $Path
    if(-not [IO.Directory]::Exists($Path)){throw 'Required protected directory missing.'}
    $parts=[Security.AccessControl.AccessControlSections]'Access,Owner,Group'
    $acl=[IO.Directory]::GetAccessControl($Path,$parts)
    $rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    $raw=[Security.AccessControl.RawSecurityDescriptor]::new($acl.GetSecurityDescriptorBinaryForm(),0)
    if($acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -cne 'S-1-5-32-544' -or
        -not $acl.AreAccessRulesProtected -or -not $acl.AreAccessRulesCanonical -or $rules.Count -ne 2 -or
        $null -eq $raw.DiscretionaryAcl -or $raw.DiscretionaryAcl.Count -ne 2){throw ('Private ACL shape differs: '+$Path)}
    $seen=@{}
    foreach($r in $rules){
        $sid=$r.IdentityReference.Value
        if($sid -cnotin @('S-1-5-18','S-1-5-32-544') -or $seen.ContainsKey($sid) -or
            $r.AccessControlType -ne 'Allow' -or [int]$r.FileSystemRights -ne 2032127 -or $r.IsInherited -or
            [int]$r.InheritanceFlags -ne 3 -or [int]$r.PropagationFlags -ne 0){throw ('Private ACL rule differs: '+$Path)}
        $seen[$sid]=$true
    }
    return $acl.GetSecurityDescriptorSddlForm($parts)
}

function Invoke-ReleasePairResumeGate {
    param([Collections.Generic.List[IDisposable]]$Pins,[hashtable]$Guards)
    $base='C:\ProgramData\SFLOps';$audit=$base+'\tmp\acl-repair-72d495ebd11e41eda80603d9093a2cfe'
    $targets=@(($base+'\inventory'),$base);$backupHash='90EE9F49517AF299AB7A0DBA38053C3B80806DF6E7C662BA765FA754260D9CAD'
    foreach($path in @($base,($base+'\tmp'),($base+'\inventory'),$audit)){Open-CleanupDirectoryGuard $path $Guards;$null=Get-ResumePrivateSddl $path}
    $data=@{}
    foreach($spec in @(@('before-acl.json',$backupHash),@('acl-repair.jsonl','507678162C3521D2F7909137A92308C2C1F48EACA380865CE97B5C7D8C387C57'))){
        $path=Join-Path $audit $spec[0];Assert-QPlain $path
        $s=[SflCleanupNativeV1]::OpenFile($path,$false);$Pins.Add($s)
        if($s.Length -gt 2MB -or $s.Length -le 0 -or (Get-QHash $s) -cne $spec[1]){throw ('ACL evidence hash/size mismatch: '+$spec[0])}
        $data[$spec[0]]=Read-QText $s
    }
    $backup=ConvertFrom-Json -InputObject $data['before-acl.json']
    $events=@($data['acl-repair.jsonl'].Split([char]10)|Where-Object {-not [string]::IsNullOrWhiteSpace($_)}|ForEach-Object {ConvertFrom-Json -InputObject $_})
    $expected=Assert-ResumeAclRecords $events $backup $targets $backupHash
    foreach($path in $targets){if((Get-ResumePrivateSddl $path) -cne $expected[$path]){throw 'Current ACL differs from completed repair.'}}
    Write-Host '[RESUME GATE PASS] Exact ACL backup/journal and current protected ACLs verified. No ACL changes.'
}
